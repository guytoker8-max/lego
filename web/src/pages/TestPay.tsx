import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { api, ApiError, money, type Order } from '../api';

/** Stands in for the payment provider's page while none is connected. */
export default function TestPay() {
  const { orderId = '' } = useParams();
  const [search] = useSearchParams();
  const token = search.get('token') ?? '';
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.order(orderId, token).then(setOrder, () => setError("We couldn't find that order."));
  }, [orderId, token]);

  const pay = async () => {
    setBusy(true);
    try {
      await api.testPay(orderId, token);
      navigate(`/order/${orderId}?token=${encodeURIComponent(token)}`, { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Test payment failed.');
      setBusy(false);
    }
  };

  if (error) return <div className="wrap page-center"><h2>{error}</h2><Link className="btn" to="/">Home</Link></div>;
  if (!order) return <div className="wrap page-center"><div className="spinner spinner--dark" /></div>;

  return (
    <div className="wrap" style={{ maxWidth: 560, paddingTop: 40 }}>
      <div className="panel stack" style={{ gap: 18 }}>
        <div className="testmode">
          <b>Test payment page.</b> This stands in for the payment provider until one is connected. No card is asked
          for and nothing is charged.
        </div>
        <h2>{order.design.name}</h2>
        <div className="price-lines">
          <div><span>Pieces</span><span>{order.piece_count.toLocaleString()}</span></div>
          <div><span>Deliver to</span><span>{order.ship_to.city}, {order.ship_to.country}</span></div>
          <div><b>Total</b><b>{money(order.price.total, order.price.symbol)}</b></div>
        </div>
        <button className="btn btn--primary btn--lg btn--block" onClick={pay} disabled={busy}>
          {busy ? <span className="spinner" /> : null} Complete test payment
        </button>
        <Link className="btn btn--ghost btn--block" to={`/design/${order.model_id}?checkout=cancelled`}>Cancel</Link>
      </div>
    </div>
  );
}
