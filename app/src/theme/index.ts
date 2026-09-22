/**
 * One place for every colour, radius and text size in the app.
 *
 * The brief asks for premium, playful and family-friendly at the same time,
 * which pulls in opposite directions: playful usually means loud, premium
 * usually means restrained. The resolution here is a near-neutral shell --
 * off-white, deep ink, generous rounding -- with saturated colour used only
 * on the things you act on and on the model itself. That way the brick model
 * is the brightest thing on every screen, which is what the brief asks for,
 * and the app around it stays calm however garish the photo was.
 */

export const colors = {
  bg: '#FBF9F5',
  surface: '#FFFFFF',
  surfaceAlt: '#F3F0EA',
  ink: '#16161A',
  inkSoft: '#5C5C66',
  inkFaint: '#9A9AA5',
  line: '#E6E2DA',

  // Brick colours, used for accents. Warm yellow leads because it reads as
  // play without shouting, the way a pile of bricks on a table does.
  brand: '#FFCF3F',
  brandInk: '#2B2100',
  red: '#D3372B',
  blue: '#1C6FD0',
  green: '#3A9E4A',

  success: '#2E7D4F',
  warning: '#B26A00',
  danger: '#C0392B',

  shadow: 'rgba(22,22,26,0.10)',
} as const;

export const radius = { sm: 10, md: 16, lg: 22, xl: 30, pill: 999 } as const;

export const space = (n: number) => n * 4;

export const type = {
  display: { fontSize: 32, fontWeight: '800' as const, letterSpacing: -0.6 },
  title: { fontSize: 24, fontWeight: '800' as const, letterSpacing: -0.4 },
  heading: { fontSize: 18, fontWeight: '700' as const, letterSpacing: -0.2 },
  body: { fontSize: 15, fontWeight: '400' as const },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const },
  small: { fontSize: 13, fontWeight: '400' as const },
  caps: { fontSize: 11, fontWeight: '700' as const, letterSpacing: 1.0 },
};

export const shadow = {
  card: {
    shadowColor: '#16161A',
    shadowOpacity: 0.07,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 3,
  },
  raised: {
    shadowColor: '#16161A',
    shadowOpacity: 0.14,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
};
