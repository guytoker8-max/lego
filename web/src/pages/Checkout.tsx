import { useEffect, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';

import { api, ApiError, money, type Design } from '../api';
import { Arrow, Info, Lock } from '../components/icons';
import { useConfig } from '../config';

const COUNTRY_NAMES: Record<string, string> = {
  IL: 'Israel', US: 'United States', GB: 'United Kingdom', DE: 'Germany', FR: 'France',
  NL: 'Netherlands', CA: 'Canada', AU: 'Australia', IT: 'Italy', ES: 'Spain',
};

export default function Checkout() {
  const { id = '' } = useParams();
  const config = useConfig();
  const [design, setDesign] = useState<Design | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [shipping, setShipping] = useState('standard');
  const [form, setForm] = useState({
    email: '', name: '', phone: '', line1: '', line2: '', city: '', postal_code: '', country: '',
  });

  useEffect(() => {
    api.design(id).then(setDesign, () => setError("We couldn't find that design."));
  }, [id]);

  useEffect(() => {
    if (config && !form.country) setForm((f) => ({ ...f, country: config.ship_countries[0] ?? 'IL' }));
  }, [config, form.country]);

  if (error && !design) {
    return <div className="wrap page-center"><h2>{error}</h2><Link className="btn" to="/">Home</Link></div>;
  }
  if (!design) return <div className="wrap page-center"><div className="spinner spinner--dark" /></div>;

  if (!design.approval.approved) {
    return (
      <div className="wrap page-center">
        <h2>Approve your design first</h2>
        <p className="muted">We only make sets you've checked and approved.</p>
        <Link className="btn btn--primary" to={`/design/${id}`}>Review the design</Link>
      </div>
    );
  }

  const opt = design.price.shipping_options.find((o) => o.key === shipping) ?? design.price.shipping_options[0];
  const total = design.price.set_price + (opt?.cost ?? 0);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const r = await api.checkout({
        model_id: design.id,
        email: form.email,
        name: form.name,
        phone: form.phone,
        shipping,
        address: { line1: form.line1, line2: form.line2, city: form.city, postal_code: form.postal_code, country: form.country },
      });
      try {
        sessionStorage.setItem(`order:${r.order_id}`, r.token);
      } catch {
        /* private mode: the link still carries the token */
      }
      window.location.assign(r.redirect_url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Nothing was charged.');
      setBusy(false);
    }
  };

  const testMode = config?.payments.provider === 'test';

  return (
    <div className="wrap checkout">
      <form className="panel form" onSubmit={submit}>
        <h2>Checkout</h2>
        {testMode && (
          <div className="testmode small">
            <b>Test mode.</b> No payment provider is connected yet, so no card is taken and nothing is charged. The
            order is created and sent to fulfilment exactly as a real one would be.
          </div>
        )}
        <fieldset>
          <legend>Contact</legend>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="email" required value={form.email} onChange={set('email')} />
          </div>
          <div className="field">
            <label htmlFor="phone">Phone (for the courier)</label>
            <input id="phone" type="tel" autoComplete="tel" value={form.phone} onChange={set('phone')} />
          </div>
        </fieldset>
        <fieldset>
          <legend>Delivery address</legend>
          <div className="field">
            <label htmlFor="name">Full name</label>
            <input id="name" autoComplete="name" required value={form.name} onChange={set('name')} />
          </div>
          <div className="field">
            <label htmlFor="line1">Street address</label>
            <input id="line1" autoComplete="address-line1" required value={form.line1} onChange={set('line1')} />
          </div>
          <div className="field">
            <label htmlFor="line2">Apartment, floor (optional)</label>
            <input id="line2" autoComplete="address-line2" value={form.line2} onChange={set('line2')} />
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="city">City</label>
              <input id="city" autoComplete="address-level2" required value={form.city} onChange={set('city')} />
            </div>
            <div className="field">
              <label htmlFor="postal">Postcode</label>
              <input id="postal" autoComplete="postal-code" required value={form.postal_code} onChange={set('postal_code')} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="country">Country</label>
            <select id="country" autoComplete="country" value={form.country} onChange={set('country')}>
              {(config?.ship_countries ?? ['IL']).map((c) => (
                <option key={c} value={c}>{COUNTRY_NAMES[c] ?? c}</option>
              ))}
            </select>
          </div>
        </fieldset>
        <fieldset>
          <legend>Shipping</legend>
          {design.price.shipping_options.map((o) => (
            <label className="radio" key={o.key}>
              <input type="radio" name="shipping" value={o.key} checked={shipping === o.key} onChange={() => setShipping(o.key)} />
              <div><b>{o.label}</b><br /><span>{o.days} after packing</span></div>
              <em>{money(o.cost, design.price.symbol)}</em>
            </label>
          ))}
        </fieldset>
        {error && <div className="notice notice--error"><Info size={18} /> {error}</div>}
        <button className="btn btn--primary btn--lg btn--block" disabled={busy}>
          {busy ? <span className="spinner" /> : <Lock size={18} />} {testMode ? 'Continue to test payment' : 'Continue to secure payment'} <Arrow size={18} />
        </button>
        <p className="secure"><Lock size={14} /> Card details are entered on our payment provider's page, never on this site.</p>
      </form>

      <aside className="order-card">
        <div className="order-card__head">
          <img src={design.thumbnail} alt="" />
          <div>
            <b>{design.name}</b>
            <p className="muted small">{design.summary.piece_count.toLocaleString()} pieces · printed instructions</p>
          </div>
        </div>
        <hr className="divider" />
        <div className="price-lines">
          <div><span>Brick set</span><span>{money(design.price.set_price, design.price.symbol)}</span></div>
          <div className="muted small"><span>incl. VAT</span><span>{money(design.price.vat, design.price.symbol)}</span></div>
          <div><span>Shipping ({opt?.label})</span><span>{money(opt?.cost, design.price.symbol)}</span></div>
        </div>
        <hr className="divider" />
        <div className="price-card__total"><b style={{ fontSize: 18 }}>Total</b><b>{money(total, design.price.symbol)}</b></div>
        <p className="tiny muted">The total is recalculated on our side from the approved parts list before you pay.</p>
      </aside>
    </div>
  );
}
