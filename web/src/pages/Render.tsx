import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { api, type Geometry } from '../api';
import BrickViewer from '../components/BrickViewer';

/**
 * A bare, full-window render of one model, used to produce the homepage's
 * example images from the real 3D viewer (see scripts/render_examples.mjs).
 * Sets `window.__rendered` once the first frame is drawn.
 */
export default function Render() {
  const { id = '' } = useParams();
  const [search] = useSearchParams();
  const [geo, setGeo] = useState<Geometry | null>(null);
  useEffect(() => {
    document.body.style.background = 'transparent';
    api.geometry(id).then(setGeo);
  }, [id]);
  if (!geo) return null;
  const size = Number(search.get('size') ?? 800);
  return (
    <div style={{ width: size, height: size }}>
      <BrickViewer
        geometry={geo}
        interactive={false}
        onReady={() => setTimeout(() => ((window as unknown as { __rendered: boolean }).__rendered = true), 400)}
      />
    </div>
  );
}
