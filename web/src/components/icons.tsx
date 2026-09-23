/** A small, consistent icon set: 24px grid, 2px strokes, round joins. */

import type { SVGProps } from 'react';

type P = SVGProps<SVGSVGElement> & { size?: number };

const base = (size = 22): SVGProps<SVGSVGElement> => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
});

export const Logo = (p: P) => (
  <svg viewBox="0 0 64 64" aria-hidden {...p}>
    <rect x="4" y="18" width="56" height="40" rx="8" fill="#E5402B" />
    <rect x="11" y="8" width="17" height="14" rx="4.5" fill="#E5402B" />
    <rect x="36" y="8" width="17" height="14" rx="4.5" fill="#E5402B" />
    <rect x="11" y="8" width="17" height="5" rx="2.5" fill="#FF7A63" />
    <rect x="36" y="8" width="17" height="5" rx="2.5" fill="#FF7A63" />
    <rect x="4" y="18" width="56" height="6" rx="3" fill="#FF6B52" opacity=".55" />
  </svg>
);

export const Upload = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 16V4M7 9l5-5 5 5" /><path d="M20 16v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3" /></svg>
);
export const Camera = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" /><circle cx="12" cy="13.5" r="3.5" /></svg>
);
export const Sliders = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>
);
export const Cube = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" /></svg>
);
export const Box = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M3 7l9-4 9 4-9 4-9-4z" /><path d="M3 7v10l9 4 9-4V7" /><path d="M12 11v10" /></svg>
);
export const Bricks = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><rect x="3" y="11" width="18" height="9" rx="1.5" /><path d="M6 11V8h4v3M14 11V8h4v3" /></svg>
);
export const Check = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
);
export const X = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>
);
export const Arrow = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);
export const Back = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
);
export const Info = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h0" /></svg>
);
export const Lock = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
);
export const Truck = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="18" r="2" /><circle cx="17" cy="18" r="2" /></svg>
);
export const Doc = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></svg>
);
export const Shield = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>
);
export const Sparkle = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6" /></svg>
);

// Subject icons for "What are you turning into a brick set?"
export const Paw = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="7" cy="9" r="1.8" /><circle cx="17" cy="9" r="1.8" /><circle cx="10" cy="5.5" r="1.8" /><circle cx="14" cy="5.5" r="1.8" /><path d="M12 11c-3 0-5.5 3.5-5.5 6 0 1.7 1.3 2.5 2.7 2.5 1.2 0 1.8-.6 2.8-.6s1.6.6 2.8.6c1.4 0 2.7-.8 2.7-2.5 0-2.5-2.5-6-5.5-6z" /></svg>
);
export const Person = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="12" cy="7.5" r="3.5" /><path d="M5 21c0-4 3-7 7-7s7 3 7 7" /></svg>
);
export const Car = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M3 16v-3l2-5h11l3 5h2v3" /><path d="M3 16h18" /><circle cx="7.5" cy="16.5" r="2" /><circle cx="16.5" cy="16.5" r="2" /><path d="M7 8l-1 5M12 8v5" /></svg>
);
export const House = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></svg>
);
export const Mug = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M5 8h11v8a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4z" /><path d="M16 10h2a2 2 0 0 1 0 4h-2" /><path d="M8 3v2M12 3v2" /></svg>
);
export const Star = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z" /></svg>
);
export const Dots = ({ size, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="6" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="18" cy="12" r="1.3" /></svg>
);

export const CATEGORY_ICONS: Record<string, (p: P) => JSX.Element> = {
  pet: Paw,
  person: Person,
  vehicle: Car,
  building: House,
  object: Mug,
  character: Star,
  other: Dots,
};
