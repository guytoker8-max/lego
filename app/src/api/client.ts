/**
 * Everything the app knows about the server.
 *
 * Deliberately the only module that talks to it: screens call these
 * functions and never build a URL. Errors come back as one `ApiError` with a
 * message already fit to show a person, because a screen should not have to
 * decide what a 413 means.
 */

import { Platform } from 'react-native';
import Constants from 'expo-constants';

/**
 * Where the server is.
 *
 * `extra.apiUrl` is the answer, except for the case that matters most: a
 * phone running the app from Expo Go. There `127.0.0.1` is the phone itself,
 * so every screen reports it cannot reach BrickSnap and the fix is to edit a
 * JSON file and restart -- which is a poor first five minutes.
 *
 * Expo already tells the app which machine served the bundle, so when the
 * configured host is a loopback one and we are not on that machine, the API
 * is looked for on the development machine at the same port instead. An
 * explicit LAN or public address is always left alone.
 */
function apiBase(): string {
  const configured =
    (Constants.expoConfig?.extra as any)?.apiUrl ?? 'http://127.0.0.1:8000';
  if (Platform.OS === 'web') return configured;

  const loopback = /^https?:\/\/(127\.0\.0\.1|localhost|0\.0\.0\.0)(:|\/|$)/;
  if (!loopback.test(configured)) return configured;

  // "192.168.1.20:8081" while running from a development server.
  const hostUri =
    (Constants.expoConfig as any)?.hostUri ??
    (Constants as any)?.expoGoConfig?.debuggerHost ??
    '';
  const host = String(hostUri).split('/')[0].split(':')[0];
  if (!host || loopback.test(`http://${host}`)) return configured;

  const port = configured.split(':')[2] ?? '8000';
  return `${configured.split('://')[0]}://${host}:${port}`;
}

const BASE: string = apiBase();

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    // No status to report: the request never reached the server.
    throw new ApiError(
      'Could not reach BrickSnap. Check your connection and try again.',
      0,
    );
  }
  if (!res.ok) {
    let detail = 'Something went wrong.';
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* server sent no JSON; the default message stands */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

// ---- types ---------------------------------------------------------------

export type SizePreset = {
  key: string; label: string; width_studs: number; max_pieces: number;
  max_dimension_cm: number; colors: number; detail: string;
};

export type Config = {
  product_name: string;
  branding: {
    product_name: string; brick_term: string;
    disclaimer: string; short_disclaimer: string; official_product: boolean;
  };
  size_presets: SizePreset[];
  default_preset: string;
  max_references: number;
  max_upload_mb: number;
  vision_enabled: boolean;
};

export type Question = {
  id: string;
  prompt: string;
  options: { id: string; label: string; default?: boolean }[];
};

export type Job = {
  id: string; status: string; stage?: string; message?: string;
  progress?: number; questions?: Question[]; error?: string;
  model_id?: string; summary?: Summary; warnings?: string[];
  analysis?: { display_name: string; subject: string; warnings: string[];
               confidence: number; source: string };
};

export type Summary = {
  name: string; subject: string; piece_count: number; color_count: number;
  dimensions_cm: number[]; weight_g: number; difficulty: string;
  step_count: number; fingerprint: string;
  build_time: { minutes: number; label: string };
};

export type Geometry = {
  fingerprint: string;
  size_studs: number[];
  palette: Record<string, { name: string; hex: string }>;
  parts: Record<string, { w: number; d: number; h: number; has_studs: boolean }>;
  bricks: [string, number, number, number, number, number][];
  steps: number[][];
};

export type PartLine = {
  part_id: string; part_name: string; color_id: number; color_name: string;
  color_hex: string; quantity: number; line_weight_g: number; line_cost: number;
};

export type Parts = {
  fingerprint: string; total_pieces: number; distinct_parts: number;
  distinct_colors: number; total_weight_g: number; lines: PartLine[];
  mismatches: string[]; unavailable: { part_name: string; color_name: string }[];
};

export type Step = {
  index: number; title: string; note: string; piece_count: number;
  cumulative: number;
  add: { quantity: number; part_name: string; color_name: string;
         color_hex: string; label: string }[];
  placements: { brick_index: number; part_id: string; color_hex: string;
                x: number; y: number; z: number; rotation: number }[];
};

export type Price = {
  currency: string; symbol: string; set_price: number; total: number;
  production_days: number;
  breakdown: Record<string, number>;
  shipping_options: { key: string; label: string; cost: number; days: string }[];
  shipping_selected: string;
};

export type Order = {
  id: string; status: string; status_label: string; piece_count: number;
  price: Price; tracking: { carrier?: string; number?: string };
  steps: { key: string; label: string; done: boolean }[];
};

// ---- calls ---------------------------------------------------------------

export const getConfig = () => request<Config>('/api/config');

export async function uploadPhotos(
  uris: string[], angles: string[] = [],
): Promise<Job> {
  const form = new FormData();
  for (let i = 0; i < uris.length; i += 1) {
    const uri = uris[i];
    const name = (uri.split('/').pop() || `ref${i}.jpg`).split('?')[0];
    const ext = name.split('.').pop()?.toLowerCase();
    const type = ext === 'png' ? 'image/png' : 'image/jpeg';
    if (Platform.OS === 'web') {
      // A browser's FormData only understands a Blob. React Native's
      // {uri, name, type} shape would be stringified to "[object Object]"
      // and the server would reject the upload as a missing file.
      const blob = await (await fetch(uri)).blob();
      form.append('files', blob, name);
    } else {
      form.append('files', { uri, name, type } as any);
    }
  }
  if (angles.length) form.append('angles', angles.join(','));
  return request<Job>('/api/jobs', { method: 'POST', body: form });
}

export const startBuild = (jobId: string, answers: Record<string, string>) =>
  request<Job>(`/api/jobs/${jobId}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answers),
  });

export const getJob = (jobId: string) => request<Job>(`/api/jobs/${jobId}`);

export const getModel = (id: string) =>
  request<{ summary: Summary; parts: Parts; steps: Step[]; price: Price;
            validation: any; warnings: string[] }>(`/api/models/${id}`);

export const getGeometry = (id: string) =>
  request<Geometry>(`/api/models/${id}/geometry`);

export const getParts = (id: string) => request<Parts>(`/api/models/${id}/parts`);

export const getSteps = (id: string) =>
  request<{ steps: Step[]; fingerprint: string }>(`/api/models/${id}/steps`);

export const priceModel = (id: string, shipping: string) =>
  request<Price>(`/api/models/${id}/price`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ shipping }),
  });

export const listModels = () =>
  request<{ models: { id: string; name: string; piece_count: number;
                      dimensions_cm: number[]; status: string;
                      updated_at: number; thumbnail: string | null }[] }>(
    '/api/models');

/** Absolute URL of a model's rendered still, for <Image source>. */
export const previewUrl = (id: string) => `${BASE}/api/models/${id}/preview`;

export type EditPlan = {
  size: string | null; detail: string | null; priority: string | null;
  recolour: { region: string; color_id: number }[];
  understood: string[]; not_understood: string[]; needs_rebuild: boolean;
};

export const editModel = (id: string, instruction: string) =>
  request<{ job_id: string; model_id: string; plan: EditPlan }>(
    `/api/models/${id}/edit`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    },
  );

export const getVersions = (id: string) =>
  request<{ current: Summary;
            versions: { change: string; piece_count: number }[] }>(
    `/api/models/${id}/versions`);

export const createOrder = (modelId: string, shipping: string) =>
  request<{ order: Order; payment: { status: string; message: string } }>(
    '/api/orders',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId, shipping }),
    },
  );

export const getOrder = (id: string) => request<Order>(`/api/orders/${id}`);
