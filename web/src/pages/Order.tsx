import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { api, money, type Order } from '../api';
import { Check, Doc, Info, Truck } from '../components/icons';

const fmt = (t: number) => new Date(t * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export default function OrderPage() {
  const { id = '' } = useParams();
  const [search] = useSearchParams();
  const sessionId = search.get('session_id') ?? undefined;
  let token = search.get('token') ?? '';
  try {
    token = token || sessionStorage.getItem(`order:${id}`) || '';
  } catch {
    /* ignore */
  }
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    let tries = 0;
    const load = () =>
      api.order(id, token, sessionId).then(
        (o) => {
          if (!alive) return;
          setOrder(o);
          // Right after paying, the provider's confirmation can take a few
          // seconds to arrive; keep asking for a short while.
          if (o.status === 'awaiting_payment' && tries++ < 20) timer = window.setTimeout(load, 3000);
        },
        () => alive && setError("We couldn't find that order. Check the link in your confirmation."),
      );
    load();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [id, token, sessionId]);

  if (error) return <div className="wrap page-center"><h2>{error}</h2><Link className="btn" to="/">Home</Link></div>;
  if (!order) return <div className="wrap page-center"><div className="spinner spinner--dark" /></div>;

  const paid = order.status !== 'awaiting_payment' && order.status !== 'cancelled';
  const timeline = [
    { key: 'paid', label: 'Payment received', done: paid },
    ...order.steps.map((s) => ({ key: s.key, label: s.key === 'confirmed' ? 'Sent to our packing partner' : s.label, done: s.done })),
  ];
  const current = timeline.findIndex((t) => !t.done);

  return (
    <div className="wrap checkout">
      <section className="panel stack" style={{ gap: 20 }}>
        <div className="stack" style={{ gap: 6 }}>
          <span className="eyebrow">Order {order.id.slice(0, 8).toUpperCase()}</span>
          <h2>
            {order.status === 'awaiting_payment'
              ? 'Waiting for payment confirmation'
              : order.status === 'cancelled'
                ? 'This order was cancelled'
                : order.status === 'delivered'
                  ? 'Delivered. Happy building!'
                  : 'Thank you, your set is on its way'}
          </h2>
          <p className="muted">
            {order.status === 'awaiting_payment'
              ? "As soon as the payment provider confirms, we'll send your parts list to be packed."
              : `We'll email ${order.email} as your order moves along. Bookmark this page to check on it any time.`}
          </p>
        </div>
        {order.payment.test_mode && (
          <div className="testmode small"><b>Test order.</b> Placed in test mode; no money was taken.</div>
        )}
        {order.status !== 'cancelled' && (
          <ol className="timeline">
            {timeline.map((t, i) => (
              <li key={t.key} className={`${t.done ? 'is-done' : ''} ${i === current ? 'is-current' : ''}`}>
                <span className="timeline__dot">{t.done ? <Check size={15} /> : null}</span>
                <div>
                  <b>{t.label}</b>
                  {t.key === 'shipped' && order.tracking?.number ? (
                    <span>
                      {order.tracking.carrier} · {order.tracking.url ? <a href={order.tracking.url} target="_blank" rel="noreferrer">{order.tracking.number}</a> : order.tracking.number}
                    </span>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
        {order.tracking?.number && (
          <div className="notice"><Truck size={18} /> Tracking: {order.tracking.carrier} {order.tracking.number}</div>
        )}
      </section>

      <aside className="order-card">
        <div className="order-card__head">
          <img src={order.design.thumbnail} alt="" />
          <div>
            <b>{order.design.name}</b>
            <p className="muted small">{order.piece_count.toLocaleString()} pieces</p>
          </div>
        </div>
        <hr className="divider" />
        <div className="price-lines">
          <div><span>Brick set</span><span>{money(order.price.set_price, order.price.symbol)}</span></div>
          <div><span>Shipping</span><span>{money(order.price.breakdown.shipping, order.price.symbol)}</span></div>
          <div><b>Total</b><b>{money(order.price.total, order.price.symbol)}</b></div>
        </div>
        <hr className="divider" />
        <div className="small">
          <b>Delivering to</b>
          <p className="muted">
            {order.ship_to.name}<br />
            {order.ship_to.line1}{order.ship_to.line2 ? `, ${order.ship_to.line2}` : ''}<br />
            {order.ship_to.postal_code} {order.ship_to.city}, {order.ship_to.country}
          </p>
        </div>
        <Link className="btn btn--ghost btn--block" to={`/design/${order.design.id}`}>View your design</Link>
        <a className="btn btn--ghost btn--block" href={`/api/store/designs/${order.design.id}/booklet.pdf`} target="_blank" rel="noreferrer">
          <Doc size={18} /> Instructions (PDF)
        </a>
        <p className="tiny muted"><Info size={12} /> Placed {fmt(order.created_at)}</p>
      </aside>
    </div>
  );
}
