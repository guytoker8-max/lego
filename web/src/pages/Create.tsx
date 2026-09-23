import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError, type Job } from '../api';
import { useConfig } from '../config';
import { Arrow, Back, Camera, CATEGORY_ICONS, Check, Info, Upload, X } from '../components/icons';

type Step = 'upload' | 'subject' | 'size';
const STEPS: { key: Step; label: string }[] = [
  { key: 'upload', label: 'Upload' },
  { key: 'subject', label: 'Subject' },
  { key: 'size', label: 'Size' },
];
const ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ANGLES = ['front', 'side', 'back', 'top'];

interface Picked {
  file: File;
  url: string;
}

export function Stepper({ current, done }: { current: string; done: string[] }) {
  return (
    <ol className="stepper" aria-label="Progress">
      {[...STEPS, { key: 'preview', label: 'Preview' }].map((s, i) => (
        <li
          key={s.key}
          className={`stepper__item ${current === s.key ? 'is-active' : ''} ${done.includes(s.key) ? 'is-done' : ''}`}
          aria-current={current === s.key ? 'step' : undefined}
        >
          <i>{done.includes(s.key) ? <Check size={14} /> : i + 1}</i>
          <span>{s.label}</span>
        </li>
      ))}
    </ol>
  );
}

export default function Create() {
  const config = useConfig();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('upload');
  const [picked, setPicked] = useState<Picked[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [uploadedKey, setUploadedKey] = useState('');
  const [category, setCategory] = useState('');
  const [size, setSize] = useState('standard');
  const [width, setWidth] = useState(20);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [over, setOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);

  const maxPhotos = config?.max_photos ?? 4;
  const maxMb = config?.max_upload_mb ?? 12;
  const isTouch = useMemo(() => typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches, []);

  useEffect(() => () => picked.forEach((p) => URL.revokeObjectURL(p.url)), []); // eslint-disable-line

  const add = useCallback(
    (list: FileList | File[] | null) => {
      if (!list) return;
      setError('');
      const incoming = Array.from(list);
      const next: Picked[] = [];
      for (const f of incoming) {
        const okType = TYPES.includes(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name);
        if (!okType) {
          setError(`${f.name} isn't a JPG, PNG or WEBP image.`);
          continue;
        }
        if (f.size > maxMb * 1024 * 1024) {
          setError(`${f.name} is larger than ${maxMb} MB.`);
          continue;
        }
        next.push({ file: f, url: URL.createObjectURL(f) });
      }
      setPicked((cur) => {
        const merged = [...cur, ...next];
        if (merged.length > maxPhotos) {
          setError(`Up to ${maxPhotos} photos, please. We kept the first ${maxPhotos}.`);
          merged.slice(maxPhotos).forEach((p) => URL.revokeObjectURL(p.url));
        }
        return merged.slice(0, maxPhotos);
      });
    },
    [maxMb, maxPhotos],
  );

  const remove = (i: number) =>
    setPicked((cur) => {
      URL.revokeObjectURL(cur[i].url);
      return cur.filter((_, k) => k !== i);
    });

  const photosKey = picked.map((p) => `${p.file.name}:${p.file.size}:${p.file.lastModified}`).join('|');

  const continueFromUpload = async () => {
    if (!picked.length) return;
    if (job && uploadedKey === photosKey) {
      setStep('subject');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const j = await api.upload(picked.map((p) => p.file));
      setJob(j);
      setUploadedKey(photosKey);
      setStep('subject');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Upload failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    if (!job) return;
    setBusy(true);
    setError('');
    try {
      await api.build(job.id, {
        category,
        size,
        ...(size === 'custom' ? { width_cm: width } : {}),
        ...(picked.length > 1 ? { angles: ANGLES.slice(0, picked.length) } : {}),
      });
      navigate(`/build/${job.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
      setBusy(false);
    }
  };

  const done = STEPS.slice(0, STEPS.findIndex((s) => s.key === step)).map((s) => s.key);

  return (
    <div className="wrap flowpage">
      <Stepper current={step} done={done} />

      {step === 'upload' && (
        <section className="panel">
          <div className="panel__title">
            <h2>Upload your photo</h2>
            <p className="muted">JPG, PNG or WEBP, up to {maxMb} MB each. You can add up to {maxPhotos}.</p>
          </div>

          <div
            className={`drop ${over ? 'is-over' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => fileInput.current?.click()}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInput.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              add(e.dataTransfer.files);
            }}
          >
            <div className="drop__icon"><Upload size={30} /></div>
            <b style={{ fontSize: 18 }}>{isTouch ? 'Add your photos' : 'Drag your photos here'}</b>
            <span className="muted small">{isTouch ? 'From your library or the camera' : 'or choose them from your computer'}</span>
            <div className="drop__btns" onClick={(e) => e.stopPropagation()}>
              <button className="btn btn--sm" type="button" onClick={() => fileInput.current?.click()}>
                <Upload size={18} /> Choose photos
              </button>
              {isTouch && (
                <button className="btn btn--ghost btn--sm" type="button" onClick={() => cameraInput.current?.click()}>
                  <Camera size={18} /> Take a photo
                </button>
              )}
            </div>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                add(e.target.files);
                e.target.value = '';
              }}
            />
            <input
              ref={cameraInput}
              type="file"
              accept="image/*"
              capture="environment"
              hidden
              onChange={(e) => {
                add(e.target.files);
                e.target.value = '';
              }}
            />
          </div>

          <div className="hint">
            <Info size={18} />
            <span>
              For the most accurate model, upload photos from different angles. Put the front view first, then a
              side view. A plain background and good light help a lot.
            </span>
          </div>

          {picked.length > 0 && (
            <div className="thumbs">
              {picked.map((p, i) => (
                <div className="thumb" key={p.url}>
                  <img src={p.url} alt={`Photo ${i + 1}`} />
                  <small>{i === 0 ? 'Front' : ANGLES[i][0].toUpperCase() + ANGLES[i].slice(1)}</small>
                  <button type="button" onClick={() => remove(i)} aria-label={`Remove photo ${i + 1}`}>
                    <X size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && <p className="notice notice--error" style={{ marginTop: 16 }}>{error}</p>}

          <div className="panel__actions">
            <span className="muted small">{picked.length ? `${picked.length} of ${maxPhotos} photos` : ''}</span>
            <button className="btn btn--primary btn--lg" disabled={!picked.length || busy} onClick={continueFromUpload}>
              {busy ? <span className="spinner" /> : null}
              Continue <Arrow size={20} />
            </button>
          </div>
        </section>
      )}

      {step === 'subject' && (
        <section className="panel">
          <div className="panel__title">
            <h2>What are you turning into a brick set?</h2>
            <p className="muted">This tells us how to rebuild the parts the photo can't show, like the back of a pet or the depth of a house.</p>
          </div>
          <div className="choices" role="radiogroup" aria-label="Subject">
            {(config?.categories ?? []).map((c) => {
              const Icon = CATEGORY_ICONS[c.key] ?? CATEGORY_ICONS.other;
              return (
                <button
                  key={c.key}
                  type="button"
                  role="radio"
                  aria-checked={category === c.key}
                  className={`choice ${category === c.key ? 'is-selected' : ''}`}
                  onClick={() => setCategory(c.key)}
                >
                  <span className="choice__icon"><Icon size={24} /></span>
                  <b>{c.label}</b>
                  <span className="choice__check"><Check size={14} /></span>
                </button>
              );
            })}
          </div>
          <div className="panel__actions">
            <button className="btn btn--ghost" onClick={() => setStep('upload')}><Back size={18} /> Back</button>
            <button className="btn btn--primary btn--lg" disabled={!category} onClick={() => setStep('size')}>
              Continue <Arrow size={20} />
            </button>
          </div>
        </section>
      )}

      {step === 'size' && (
        <section className="panel">
          <div className="panel__title">
            <h2>How big should it be?</h2>
            <p className="muted">The piece counts are limits we build within. You'll see the exact size, pieces and price before you order, and you can change size afterwards.</p>
          </div>
          <div className="choices choices--sizes" role="radiogroup" aria-label="Size">
            {(config?.sizes ?? []).map((s) => (
              <button
                key={s.key}
                type="button"
                role="radio"
                aria-checked={size === s.key}
                className={`choice ${size === s.key ? 'is-selected' : ''}`}
                onClick={() => setSize(s.key)}
              >
                <b>{s.label.toUpperCase()}</b>
                <ul>
                  {s.blurb.map((b) => <li key={b}>{b}</li>)}
                </ul>
                {s.max_pieces ? <span className="stat">Up to {s.max_pieces.toLocaleString()} pieces</span> : null}
                <span className="choice__check"><Check size={14} /></span>
              </button>
            ))}
          </div>

          {size === 'custom' && (
            <div style={{ marginTop: 22 }}>
              <b>Approximate width</b>
              <div className="widths" role="radiogroup" aria-label="Width">
                {(config?.custom_widths_cm ?? []).map((w) => (
                  <button
                    key={w.width_cm}
                    type="button"
                    role="radio"
                    aria-checked={width === w.width_cm}
                    className={`pill ${width === w.width_cm ? 'is-selected' : ''}`}
                    onClick={() => setWidth(w.width_cm)}
                  >
                    {w.width_cm} cm
                  </button>
                ))}
              </div>
              <p className="muted small" style={{ marginTop: 10 }}>
                Up to {(config?.custom_widths_cm.find((w) => w.width_cm === width)?.max_pieces ?? 0).toLocaleString()} pieces.
                Bricks come in 8 mm steps, so the real width is measured from the finished model and may differ slightly.
              </p>
            </div>
          )}

          {error && <p className="notice notice--error" style={{ marginTop: 16 }}>{error}</p>}

          <div className="panel__actions">
            <button className="btn btn--ghost" onClick={() => setStep('subject')}><Back size={18} /> Back</button>
            <button className="btn btn--primary btn--lg" disabled={busy} onClick={start}>
              {busy ? <span className="spinner" /> : null}
              Build my set <Arrow size={20} />
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
