import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { api, ApiError, cm, money, type Design, type Geometry, type Step } from '../api';
import BrickViewer from '../components/BrickViewer';
import { Arrow, Check, Doc, Info, Shield } from '../components/icons';
import { useConfig } from '../config';

type Tab = 'parts' | 'steps' | 'checks' | 'size';

export default function DesignPage() {
  const { id = '' } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const config = useConfig();
  const [design, setDesign] = useState<Design | null>(null);
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [tab, setTab] = useState<Tab>('parts');
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [resizeTo, setResizeTo] = useState<{ size: string; width?: number } | null>(null);

  useEffect(() => {
    let alive = true;
    setDesign(null);
    setGeo(null);
    setSteps(null);
    Promise.all([api.design(id), api.geometry(id)]).then(
      ([d, g]) => {
        if (!alive) return;
        // The two were fetched separately; if the model changed in between,
        // showing them together would be showing two different sets.
        if (d.fingerprint !== g.fingerprint) {
          setError('This design changed while loading. Please refresh.');
          return;
        }
        setDesign(d);
        setGeo(g);
      },
      (e) => alive && setError(e instanceof ApiError && e.status === 404 ? "We couldn't find that design." : 'Something went wrong loading this design.'),
    );
    return () => {
      alive = false;
    };
  }, [id]);

  useEffect(() => {
    if (tab !== 'steps' || steps) return;
    api.steps(id).then((r) => {
      if (design && r.fingerprint !== design.fingerprint) {
        setError('The instructions and the model disagree. Please refresh.');
        return;
      }
      setSteps(r.steps);
      setStep(1);
    }, () => setSteps([]));
  }, [tab, steps, id, design]);

  const byColor = useMemo(() => {
    if (!design) return [];
    const groups = new Map<string, { hex: string; count: number }>();
    design.parts.forEach((p) => {
      const g = groups.get(p.color_name) ?? { hex: p.color_hex, count: 0 };
      g.count += p.quantity;
      groups.set(p.color_name, g);
    });
    return Array.from(groups.entries()).sort((a, b) => b[1].count - a[1].count);
  }, [design]);

  if (error) {
    return (
      <div className="wrap page-center">
        <h2>{error}</h2>
        <Link to="/create" className="btn btn--primary">Create a set</Link>
      </div>
    );
  }
  if (!design || !geo) {
    return (
      <div className="wrap design">
        <div className="stage-box skeleton" />
        <div className="stack">
          <div className="skeleton" style={{ height: 60 }} />
          <div className="skeleton" style={{ height: 160 }} />
          <div className="skeleton" style={{ height: 120 }} />
        </div>
      </div>
    );
  }

  const s = design.summary;
  const approved = design.approval.approved;
  const symbol = design.price.symbol;

  const approve = async () => {
    setBusy(true);
    setActionError('');
    try {
      await api.approve(design.id, design.fingerprint);
      setDesign({ ...design, approval: { approved: true, stale: false, at: Date.now() / 1000 } });
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Could not approve. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const resize = async () => {
    if (!resizeTo) return;
    setBusy(true);
    setActionError('');
    try {
      const job = await api.resize(design.id, {
        size: resizeTo.size,
        ...(resizeTo.size === 'custom' ? { width_cm: resizeTo.width ?? 20 } : {}),
      });
      navigate(`/build/${job.id}`);
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Could not start the rebuild.');
      setBusy(false);
    }
  };

  const currentStep = steps?.[step - 1];

  return (
    <div className="wrap">
      <div className="design">
        <div className="design__stage">
          <div className="stage-box">
            <BrickViewer geometry={geo} step={tab === 'steps' && steps?.length ? step : null} />
            {design.web.photos?.length ? (
              <div className="stage-box__photos">
                {design.web.photos.slice(0, 3).map((p) => (
                  <img key={p.url} src={p.url} alt="The photo this set was built from" />
                ))}
              </div>
            ) : null}
            <span className="stage-box__hint">Drag to turn · pinch or scroll to zoom</span>
          </div>
        </div>

        <aside className="summary">
          <div className="summary__name">
            <span className="eyebrow">{design.example ? 'Example set' : 'Your design'}</span>
            <h2>{design.name}</h2>
            <p className="muted small">
              Every piece in this preview is a real brick on the parts list below. What you approve is exactly what
              we pack.
            </p>
          </div>

          <div className="stats">
            <div className="stat-box"><b>{s.piece_count.toLocaleString()}</b><span>pieces</span></div>
            <div className="stat-box">
              <b>{cm(design.dimensions_cm.width)}</b>
              <span>wide × {cm(design.dimensions_cm.height)} tall × {cm(design.dimensions_cm.depth)} deep</span>
            </div>
            <div className="stat-box"><b>{s.color_count}</b><span>colours · {design.distinct_parts} brick types</span></div>
            <div className="stat-box"><b>{s.build_time.label}</b><span>to build · {s.difficulty.toLowerCase()}</span></div>
          </div>

          <div className="price-card">
            <div className="price-card__total">
              <span className="muted">Set price</span>
              <b>{money(design.price.set_price, symbol)}</b>
            </div>
            <div className="price-lines">
              <div><span>Includes VAT</span><span>{money(design.price.vat, symbol)}</span></div>
              <div>
                <span>Shipping</span>
                <span>from {money(Math.min(...design.price.shipping_options.map((o) => o.cost)), symbol)}</span>
              </div>
              <div><span>Packed and shipped within</span><span>about {design.price.production_days} days</span></div>
            </div>

            {design.approval.stale && (
              <div className="notice notice--warn"><Info size={18} /> This design changed after you approved it. Please check it and approve again.</div>
            )}
            {search.get('checkout') === 'cancelled' && (
              <div className="notice"><Info size={18} /> Payment was cancelled. Nothing was charged.</div>
            )}
            {actionError && <div className="notice notice--error">{actionError}</div>}

            {approved ? (
              <>
                <div className="approved"><Check size={18} /> You approved this design</div>
                <Link to={`/checkout/${design.id}`} className="btn btn--primary btn--lg btn--block">
                  Order this set <Arrow size={20} />
                </Link>
              </>
            ) : (
              <>
                <button className="btn btn--primary btn--lg btn--block" onClick={approve} disabled={busy}>
                  {busy ? <span className="spinner" /> : <Check size={20} />} Approve this design
                </button>
                <p className="tiny muted center">
                  Approving locks in these exact {s.piece_count.toLocaleString()} pieces. You can still change the size first.
                </p>
              </>
            )}
          </div>
        </aside>
      </div>

      <section className="section" style={{ paddingTop: 40 }}>
        <div className="tabs" role="tablist">
          {(
            [
              ['parts', `Parts (${design.parts.length})`],
              ['steps', `Instructions (${s.step_count})`],
              ['checks', 'Stability checks'],
              ['size', 'Change size'],
            ] as [Tab, string][]
          ).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'is-active' : ''}`} onClick={() => setTab(k)}>
              {label}
            </button>
          ))}
        </div>

        <div className="tabpanel" role="tabpanel">
          {tab === 'parts' && (
            <>
              <div className="parts-head">
                <div className="stack" style={{ gap: 4 }}>
                  <h3>Exactly what's in the box</h3>
                  <p className="muted small">
                    {s.piece_count.toLocaleString()} LEGO-compatible pieces in {design.parts.length} part and colour
                    combinations, counted from the model itself.
                  </p>
                </div>
                <div className="small muted" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {byColor.slice(0, 6).map(([name, g]) => (
                    <span key={name}><span className="swatch" style={{ background: g.hex }} />{name} {g.count}</span>
                  ))}
                </div>
              </div>
              <div className="parts">
                {design.parts.map((p) => (
                  <div className="part" key={`${p.design_id}-${p.color_id}`}>
                    <img src={p.image} alt="" loading="lazy" />
                    <b>{p.quantity}×</b>
                    <span>
                      {p.color_name}
                      <br />
                      {p.name} · {p.design_id}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {tab === 'steps' && (
            <div className="steps">
              {!steps ? (
                <div className="skeleton" style={{ height: 80 }} />
              ) : steps.length === 0 ? (
                <p className="muted">Instructions aren't available for this design.</p>
              ) : (
                <>
                  <div className="spread">
                    <h3>Step {step} of {steps.length}</h3>
                    <a className="btn btn--ghost btn--sm" href={design.booklet} target="_blank" rel="noreferrer">
                      <Doc size={18} /> Printable booklet (PDF)
                    </a>
                  </div>
                  <div className="steps__bar">
                    <button className="btn btn--ghost btn--sm" disabled={step <= 1} onClick={() => setStep(step - 1)} aria-label="Previous step">‹</button>
                    <input type="range" min={1} max={steps.length} value={step} onChange={(e) => setStep(Number(e.target.value))} aria-label="Step" />
                    <button className="btn btn--ghost btn--sm" disabled={step >= steps.length} onClick={() => setStep(step + 1)} aria-label="Next step">›</button>
                  </div>
                  {currentStep && (
                    <>
                      <p className="muted small">
                        {currentStep.title}. Add these {currentStep.piece_count} pieces (highlighted in the preview):
                      </p>
                      <div className="steps__adds">
                        {currentStep.add.map((a) => (
                          <span className="steps__add" key={`${a.part_id}-${a.color_id}`}>
                            <img src={`/api/catalog/parts/${a.part_id}/image.svg?color=${a.color_id}`} alt="" />
                            {a.quantity}× {a.color_name} {a.part_name}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}

          {tab === 'checks' && (
            <div className="checks">
              <div className="check"><Shield /><div><b>Every piece is a real part</b><span>Only standard bricks, plates and tiles from our catalogue, in colours that are actually made.</span></div></div>
              <div className="check"><Shield /><div><b>Every piece is held</b><span>Each brick clips onto studs below it; nothing is merely resting against a neighbour.</span></div></div>
              <div className="check"><Shield /><div><b>It can be built in order</b><span>Each step only adds pieces onto ones already placed, from the bottom up.</span></div></div>
              <div className="check"><Shield /><div><b>It balances</b><span>The centre of mass sits over the base, so the finished model stands on its own.</span></div></div>
              {design.checks.repairs.length > 0 && (
                <div className="check">
                  <Info />
                  <div>
                    <b>What we adjusted to make it stand</b>
                    <span>{design.checks.repairs.join(' ')} These support pieces are included in the parts list and price.</span>
                  </div>
                </div>
              )}
              {design.checks.warnings.map((w) => (
                <div className="check" key={w}><Info style={{ color: '#9a6b00' }} /><div><span>{w}</span></div></div>
              ))}
            </div>
          )}

          {tab === 'size' && (
            <div className="stack" style={{ gap: 16 }}>
              {!design.can_resize ? (
                <p className="muted">
                  {design.example
                    ? 'Example sets come in one size. Create your own set from a photo to choose any size.'
                    : "The original photos for this design are no longer available, so it can't be rebuilt at another size."}
                </p>
              ) : (
                <>
                  <p className="muted">
                    A new size is rebuilt from your photos, not stretched, so the piece count, price and instructions
                    are all recalculated. Your current design stays available.
                  </p>
                  <div className="choices choices--sizes">
                    {(config?.sizes ?? []).map((o) => (
                      <button
                        key={o.key}
                        type="button"
                        className={`choice ${resizeTo?.size === o.key ? 'is-selected' : ''}`}
                        onClick={() => setResizeTo({ size: o.key, width: resizeTo?.width ?? 20 })}
                      >
                        <b>{o.label}</b>
                        {o.max_pieces ? <span className="stat">Up to {o.max_pieces.toLocaleString()} pieces</span> : <span className="stat">10 to 40 cm wide</span>}
                        {design.web.size === o.key ? <span className="tag">Current</span> : null}
                        <span className="choice__check"><Check size={14} /></span>
                      </button>
                    ))}
                  </div>
                  {resizeTo?.size === 'custom' && (
                    <div className="widths">
                      {(config?.custom_widths_cm ?? []).map((w) => (
                        <button key={w.width_cm} className={`pill ${resizeTo.width === w.width_cm ? 'is-selected' : ''}`} onClick={() => setResizeTo({ size: 'custom', width: w.width_cm })}>
                          {w.width_cm} cm
                        </button>
                      ))}
                    </div>
                  )}
                  <div>
                    <button className="btn btn--primary" disabled={!resizeTo || busy} onClick={resize}>
                      Rebuild at this size <Arrow size={18} />
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
