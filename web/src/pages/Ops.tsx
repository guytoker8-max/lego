import { useCallback, useEffect, useState } from 'react';

import { admin, ApiError, money } from '../api';

/**
 * Operations: the orders, what each supplier has been sent, and a button for
 * each step a supplier reports back. Protected by BRICKSNAP_ADMIN_TOKEN; the
 * token is kept for this browser tab only.
 */

const PO_STATUSES = ['received', 'in_production', 'packed', 'shipped', 'delivered', 'cancelled', 'rejected'];

interface PO {
  reference: string;
  supplier: string;
  order_id: string;
  status: string;
  created_at: number;
  piece_count: number;
  ship_to?: Record<string, string>;
  blind_ship: boolean;
  booklet_url: string;
  tracking?: { carrier: string; number: string };
}

interface Supplier {
  key: string;
  name: string;
  configured: boolean;
  active: boolean;
  capabilities: Record<string, unknown>;
}

const yesNo = (v: unknown) => (v === true ? 'Yes' : v === false ? 'No' : 'Unknown');

export default function Ops() {
  const [token, setToken] = useState(() => {
    try {
      return sessionStorage.getItem('ops-token') ?? '';
    } catch {
      return '';
    }
  });
  const [draft, setDraft] = useState('');
  const [orders, setOrders] = useState<any[]>([]);
  const [pos, setPos] = useState<PO[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [o, p, s] = await Promise.all([
        admin.get<{ orders: any[] }>('/api/admin/orders', token),
        admin.get<{ purchase_orders: PO[] }>('/api/admin/purchase-orders', token),
        admin.get<{ suppliers: Supplier[] }>('/api/admin/suppliers', token),
      ]);
      setOrders(o.orders);
      setPos(p.purchase_orders);
      setSuppliers(s.suppliers);
      setError('');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load.');
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const advance = async (ref: string, status: string) => {
    let body: Record<string, string> = { status };
    if (status === 'shipped') {
      const number = window.prompt('Tracking number?') ?? '';
      const carrier = window.prompt('Carrier?', 'Israel Post') ?? '';
      body = { ...body, tracking_number: number, carrier };
    }
    try {
      await admin.post(`/api/admin/purchase-orders/${ref}/status`, token, body);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed.');
    }
  };

  const downloadCsv = async (ref: string) => {
    const res = await fetch(`/api/admin/purchase-orders/${ref}.csv`, { headers: { 'X-Admin-Token': token } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${ref}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!token) {
    return (
      <div className="wrap" style={{ maxWidth: 440, paddingTop: 48 }}>
        <form
          className="panel form"
          onSubmit={(e) => {
            e.preventDefault();
            try {
              sessionStorage.setItem('ops-token', draft);
            } catch {
              /* ignore */
            }
            setToken(draft);
          }}
        >
          <h2>Operations</h2>
          <div className="field">
            <label htmlFor="t">Operations token</label>
            <input id="t" type="password" value={draft} onChange={(e) => setDraft(e.target.value)} />
          </div>
          <button className="btn btn--primary">Open</button>
        </form>
      </div>
    );
  }

  return (
    <div className="wrap stack" style={{ gap: 28, paddingTop: 32 }}>
      <div className="spread">
        <h2>Operations</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn--ghost btn--sm" onClick={load}>Refresh</button>
          <button className="btn btn--ghost btn--sm" onClick={() => { sessionStorage.removeItem('ops-token'); setToken(''); }}>Sign out</button>
        </div>
      </div>
      {error && <div className="notice notice--error">{error}</div>}

      <section className="stack">
        <h3>Supplier purchase orders</h3>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Reference</th><th>Supplier</th><th>Status</th><th>Pieces</th><th>Ship to</th><th>Move to</th><th></th></tr></thead>
            <tbody>
              {pos.map((p) => (
                <tr key={p.reference}>
                  <td><b>{p.reference}</b><br /><span className="tiny muted">{new Date(p.created_at * 1000).toLocaleString()}</span></td>
                  <td>{p.supplier}{p.blind_ship ? <><br /><span className="tiny muted">blind ship</span></> : null}</td>
                  <td><span className="badge">{p.status}</span>{p.tracking?.number ? <><br /><span className="tiny">{p.tracking.carrier} {p.tracking.number}</span></> : null}</td>
                  <td>{p.piece_count}</td>
                  <td className="small">{p.ship_to ? `${p.ship_to.name}, ${p.ship_to.city} ${p.ship_to.country}` : '—'}</td>
                  <td>
                    <select value="" onChange={(e) => e.target.value && advance(p.reference, e.target.value)}>
                      <option value="">Choose…</option>
                      {PO_STATUSES.filter((s) => s !== p.status).map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="small">
                    <button className="link" onClick={() => downloadCsv(p.reference)}>CSV</button>{' · '}
                    <a href={p.booklet_url} target="_blank" rel="noreferrer">Booklet</a>
                  </td>
                </tr>
              ))}
              {!pos.length && <tr><td colSpan={7} className="muted">No purchase orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="stack">
        <h3>Customer orders</h3>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Order</th><th>Status</th><th>Customer</th><th>Total</th><th>Payment</th><th>Supplier</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td><b>{o.id.slice(0, 8).toUpperCase()}</b><br /><span className="tiny muted">{o.piece_count} pieces · {o.fingerprint}</span></td>
                  <td><span className="badge">{o.status_label}</span></td>
                  <td className="small">{o.email}</td>
                  <td>{money(o.price?.total)}</td>
                  <td className="small">{o.payment?.provider}{o.payment?.test_mode ? ' (test)' : ''} · {o.payment?.status ?? 'pending'}</td>
                  <td className="small">{o.supplier_ref?.reference ?? o.supplier_ref?.error ?? '—'}</td>
                </tr>
              ))}
              {!orders.length && <tr><td colSpan={6} className="muted">No orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="stack">
        <h3>Suppliers</h3>
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Supplier</th><th>Status</th><th>API</th><th>Orders via</th><th>Dropship</th><th>Blind ship</th><th>Notes</th></tr></thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.key}>
                  <td><b>{s.name}</b><br /><span className="tiny muted">{s.key}{s.active ? ' · active' : ''}{s.configured ? '' : ' · not configured'}</span></td>
                  <td><span className={`badge badge--${String(s.capabilities.status)}`}>{String(s.capabilities.status)}</span></td>
                  <td>{String(s.capabilities.api)}</td>
                  <td>{String(s.capabilities.orders_via)}</td>
                  <td>{yesNo(s.capabilities.dropship)}</td>
                  <td>{yesNo(s.capabilities.blind_ship)}</td>
                  <td className="small">{String(s.capabilities.notes ?? '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
