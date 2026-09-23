/**
 * The website's view of the Kitsnap API.
 *
 * Every number the site shows -- pieces, centimetres, price -- comes from
 * here, and every one of them was computed on the server from the structured
 * brick model. The site never estimates anything itself.
 */

export type Money = number;

export interface SizeOption {
  key: 'mini' | 'standard' | 'detailed' | 'custom';
  label: string;
  blurb: string[];
  max_pieces?: number;
  max_width_cm?: number;
  colors?: number;
}

export interface StoreConfig {
  brand: string;
  disclaimer: string;
  short_disclaimer: string;
  currency: string;
  symbol: string;
  categories: { key: string; label: string }[];
  sizes: SizeOption[];
  custom_widths_cm: { width_cm: number; max_pieces: number; max_width_cm: number }[];
  max_photos: number;
  max_upload_mb: number;
  formats: string[];
  ship_countries: string[];
  payments: { provider: string; live: boolean };
  vision: boolean;
}

export interface Stage { key: string; label: string; state: 'done' | 'active' | 'pending' }

export interface Job {
  id: string;
  status: 'uploaded' | 'building' | 'done' | 'failed';
  photos: { url: string; name: string }[];
  category?: string;
  size?: string;
  stages?: Stage[];
  current?: string;
  message?: string;
  model_id?: string | null;
  error?: string | null;
  retries?: number;
  warnings?: string[];
  parent?: string;
}

export interface PartLine {
  part_id: string;
  design_id: string;
  name: string;
  type: string;
  color_id: number;
  color_name: string;
  color_hex: string;
  quantity: number;
  image: string;
}

export interface ShippingOption { key: string; label: string; cost: Money; days: string }

export interface PublicPrice {
  currency: string;
  symbol: string;
  set_price: Money;
  vat: Money;
  shipping: Money;
  total: Money;
  shipping_options: ShippingOption[];
  shipping_selected: string;
  production_days: number;
}

export interface Design {
  id: string;
  name: string;
  fingerprint: string;
  summary: {
    piece_count: number;
    color_count: number;
    dimensions_cm: number[];
    weight_g: number;
    build_time: { minutes: number; label: string };
    difficulty: string;
    step_count: number;
  };
  dimensions_cm: { width: number; height: number; depth: number };
  layers: number;
  parts: PartLine[];
  distinct_parts: number;
  price: PublicPrice;
  checks: { ok: boolean; repairs: string[]; warnings: string[]; stats: Record<string, number> };
  approval: { approved: boolean; stale: boolean; at?: number };
  web: { category?: string; size?: string; width_cm?: number; photos?: { url: string; name: string }[] };
  can_resize: boolean;
  example: boolean;
  thumbnail: string;
  booklet: string;
}

export interface Geometry {
  fingerprint: string;
  size_studs: [number, number, number];
  palette: Record<string, { name: string; hex: string }>;
  parts: Record<string, { w: number; d: number; h: number; has_studs: boolean }>;
  bricks: [string, number, number, number, number, number][];
  steps: number[][];
}

export interface Step {
  index: number;
  title: string;
  note: string;
  piece_count: number;
  cumulative: number;
  add: { quantity: number; part_id: string; part_name: string; color_id: number; color_name: string; color_hex: string; label: string }[];
}

export interface Example {
  slug: string;
  title: string;
  caption: string;
  category: string;
  model_id: string;
  source: string;
  thumbnail: string;
  piece_count: number;
  dimensions_cm: number[];
  price?: Money;
}

export interface Order {
  id: string;
  model_id: string;
  status: string;
  status_label: string;
  steps: { key: string; label: string; done: boolean }[];
  price: { currency: string; symbol: string; total: Money; set_price: Money; breakdown: { vat: Money; shipping: Money; subtotal?: Money } };
  piece_count: number;
  created_at: number;
  history: { status: string; at: number; note?: string }[];
  tracking: { carrier?: string; number?: string; url?: string };
  email: string;
  ship_to: Record<string, string>;
  shipping_method: string;
  payment: { provider?: string; status?: string; test_mode?: boolean };
  supplier_ref: { status?: string };
  design: { id: string; name: string; thumbnail: string };
  payments: { provider: string; live: boolean };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "We couldn't reach Kitsnap. Check your connection and try again.");
  }
  const text = await res.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : 'Something went wrong. Please try again.';
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
});

export const api = {
  config: () => request<StoreConfig>('/api/store/config'),
  examples: () => request<{ examples: Example[] }>('/api/store/examples'),

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f, f.name));
    return request<Job>('/api/store/uploads', { method: 'POST', body: form });
  },
  build: (jobId: string, body: { category: string; size: string; width_cm?: number; angles?: string[] }) =>
    request<Job>(`/api/store/jobs/${jobId}/build`, json(body)),
  job: (jobId: string) => request<Job>(`/api/store/jobs/${jobId}`),

  design: (id: string) => request<Design>(`/api/store/designs/${id}`),
  geometry: (id: string) => request<Geometry>(`/api/models/${id}/geometry`),
  steps: (id: string) => request<{ steps: Step[]; fingerprint: string }>(`/api/models/${id}/steps`),
  approve: (id: string, fingerprint: string) =>
    request<{ approved: boolean }>(`/api/store/designs/${id}/approve`, json({ fingerprint })),
  resize: (id: string, body: { size: string; width_cm?: number }) =>
    request<Job>(`/api/store/designs/${id}/resize`, json(body)),

  checkout: (body: unknown) =>
    request<{ order_id: string; token: string; redirect_url: string; test_mode: boolean; total: number }>(
      '/api/store/checkout',
      json(body),
    ),
  order: (id: string, token: string, sessionId?: string) =>
    request<Order>(
      `/api/store/orders/${id}?token=${encodeURIComponent(token)}` +
        (sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ''),
    ),
  testPay: (id: string, token: string) =>
    request<Order>(`/api/store/orders/${id}/test-pay?token=${encodeURIComponent(token)}`, { method: 'POST' }),
};

export const admin = {
  get: <T,>(path: string, token: string) => request<T>(path, { headers: { 'X-Admin-Token': token } }),
  post: <T,>(path: string, token: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token },
      body: JSON.stringify(body ?? {}),
    }),
};

export function money(amount: number | undefined, symbol = '₪'): string {
  if (amount === undefined || amount === null || Number.isNaN(amount)) return '';
  const whole = Math.abs(amount - Math.round(amount)) < 0.005;
  return `${symbol}${amount.toLocaleString('en-US', {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  })}`;
}

export function cm(value: number): string {
  return `${Math.round(value * 10) / 10} cm`;
}
