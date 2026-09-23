import { lazy, Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api, cm, money, type Example, type Geometry } from '../api';
import { useConfig } from '../config';
import { Arrow, Bricks, Box, Check, Cube, Sliders, Upload } from '../components/icons';

const BrickViewer = lazy(() => import('../components/BrickViewer'));

const LABELS: Record<string, string> = {
  pet: 'Pet',
  car: 'Car',
  house: 'House',
  person: 'Person',
  object: 'Object',
};

const PROCESS = [
  { icon: Upload, title: 'Upload', text: 'Add a photo, or a few from different angles. Pets, cars, homes, people, favourite things.' },
  { icon: Sliders, title: 'Customize', text: 'Tell us what it is and pick a size, from a desk-sized mini to a detailed display piece.' },
  { icon: Cube, title: 'Preview', text: 'Turn your set around in 3D. Every brick you see is a real piece on the parts list.' },
  { icon: Box, title: 'Order', text: 'Approve it, pay securely, and the exact pieces are packed and shipped to your door.' },
  { icon: Bricks, title: 'Build', text: 'Follow the printed step-by-step booklet that comes in the box. No glue, no guesswork.' },
];

const FLOW = [
  ['Your photo', 'what it is, its shape'],
  ['Brick model', 'every piece, placed'],
  ['3D preview', 'drawn from the model'],
  ['Parts list', 'counted from the model'],
  ['Price', 'computed from the parts'],
  ['Instructions', 'built from the model'],
  ['Your box', 'packed from the parts list'],
];

const FAQ = [
  ['Is the preview what I actually get?', 'Yes. The preview is not a picture of a set, it is the set: every brick drawn on screen is a real piece on your parts list, in the position the instructions put it. The price is calculated from that same parts list.'],
  ['What kind of bricks are they?', 'Standard LEGO-compatible bricks, plates and tiles in the common sizes and colours, so they work with bricks you already have. They are not made by the LEGO Group.'],
  ['What photos work best?', 'A clear, well-lit photo with the subject filling most of the frame and a plain background. Two or more photos from different angles (front and side) give the most accurate 3D shape.'],
  ['Can it really stand up?', 'Every set is checked before you see it: each piece must clip onto the one below, the whole model must be buildable from the bottom up, and it must balance. Where something would overhang, hidden support bricks are added and shown in the parts list.'],
  ['How long does delivery take?', 'Parts are picked and packed to order, usually within about a week, then shipped with tracking. You will see the exact shipping options and costs before you pay.'],
  ['Can I change my set before ordering?', 'Yes. You can try a different size as many times as you like; each one is rebuilt from your photos and repriced before you approve anything.'],
];

export default function Home() {
  const config = useConfig();
  const [examples, setExamples] = useState<Example[]>([]);
  const [hero, setHero] = useState<{ ex: Example; geo: Geometry } | null>(null);

  useEffect(() => {
    let alive = true;
    api.examples().then(({ examples }) => {
      if (!alive) return;
      setExamples(examples);
      const pick = examples.find((e) => e.slug === 'pet') ?? examples[0];
      if (pick) api.geometry(pick.model_id).then((geo) => alive && setHero({ ex: pick, geo }), () => {});
    }, () => {});
    return () => {
      alive = false;
    };
  }, []);

  const sizes = config?.sizes ?? [];

  return (
    <>
      <section className="hero">
        <div className="studs-bg" />
        <div className="wrap hero__grid">
          <div>
            <span className="eyebrow">Custom brick sets, made from your photos</span>
            <h1 style={{ marginTop: 16 }}>
              Turn Any Photo Into Your Own <span className="accent">Brick Set</span>
            </h1>
            <p className="lede" style={{ marginTop: 20 }}>
              Upload a photo. See it rebuilt in bricks. Customize it. Then have the pieces delivered to your door.
            </p>
            <div className="hero__ctas">
              <Link to="/create" className="btn btn--primary btn--lg">
                Create My Set <Arrow size={20} />
              </Link>
              <a href="#examples" className="btn btn--ghost btn--lg">
                See Examples
              </a>
            </div>
            <div className="hero__points">
              <span><Check size={18} /> Real, buildable parts list</span>
              <span><Check size={18} /> Checked for stability</span>
              <span><Check size={18} /> Printed instructions included</span>
            </div>
          </div>
          <div className="hero__stage" aria-label="A brick set turning in 3D">
            {hero ? (
              <>
                <div className="hero__photo">
                  <img src={hero.ex.source} alt={`The picture the ${hero.ex.title} was built from`} />
                  <span>Your photo</span>
                </div>
                <Suspense fallback={null}>
                  <BrickViewer geometry={hero.geo} autoRotate interactive />
                </Suspense>
                <Link to={`/design/${hero.ex.model_id}`} className="hero__chip" style={{ textDecoration: 'none' }}>
                  <b>{hero.ex.piece_count.toLocaleString()} pieces</b>
                  <span>
                    {cm(hero.ex.dimensions_cm[0])} wide{hero.ex.price ? ` · ${money(hero.ex.price)}` : ''}
                  </span>
                </Link>
              </>
            ) : (
              <div className="skeleton" style={{ position: 'absolute', inset: 0 }} />
            )}
          </div>
        </div>
      </section>

      <section className="section" id="examples">
        <div className="wrap">
          <div className="section__head">
            <span className="eyebrow">Examples</span>
            <h2>From picture to pieces</h2>
            <p className="lede">
              Each of these was built by the same process your photo goes through. Open one to turn it around, see
              every part, and read its instructions.
            </p>
          </div>
          <div className="examples">
            {(examples.length ? examples : Array.from({ length: 5 }, () => null)).map((ex, i) =>
              ex ? (
                <Link key={ex.slug} to={`/design/${ex.model_id}`} className="example">
                  <div className="example__art">
                    <img
                      className="render"
                      src={`/examples/${ex.slug}.png`}
                      onError={(e) => {
                        const img = e.currentTarget;
                        if (!img.dataset.fallback) {
                          img.dataset.fallback = '1';
                          img.src = ex.thumbnail;
                        }
                      }}
                      alt={`${ex.title} as a brick model`}
                      loading="lazy"
                    />
                    <div className="example__src">
                      <img src={ex.source} alt={`The ${ex.title} picture`} loading="lazy" />
                    </div>
                  </div>
                  <div className="example__body">
                    <span className="tag" style={{ width: 'fit-content' }}>{LABELS[ex.slug] ?? ex.category}</span>
                    <b style={{ marginTop: 6 }}>{ex.title}</b>
                    <span className="example__meta">
                      {ex.piece_count.toLocaleString()} pieces · {cm(ex.dimensions_cm[0])} wide
                      {ex.price ? ` · ${money(ex.price)}` : ''}
                    </span>
                  </div>
                </Link>
              ) : (
                <div key={i} className="example">
                  <div className="example__art skeleton" />
                  <div className="example__body"><div className="skeleton" style={{ height: 40 }} /></div>
                </div>
              ),
            )}
          </div>
        </div>
      </section>

      <section className="section" id="how">
        <div className="wrap">
          <div className="section__head">
            <span className="eyebrow">How it works</span>
            <h2>Five steps from photo to finished model</h2>
          </div>
          <div className="process">
            {PROCESS.map(({ icon: Icon, title, text }, i) => (
              <div className="process__item" key={title}>
                <div className="process__icon"><Icon size={24} /></div>
                <span className="process__num">STEP {i + 1}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap">
          <div className="principle">
            <div className="stack" style={{ gap: 18 }}>
              <span className="eyebrow">Not just a pretty picture</span>
              <h2>What you see is exactly what's in the box</h2>
              <p className="lede">
                We don't draw an image and then guess which bricks might match it. Your photo becomes a structured
                model of real pieces first, and everything else is read from that one model: the 3D preview, the
                parts list, the price, the instructions and the order we send to be packed.
              </p>
              <p className="lede">
                So if the preview shows 1,024 pieces, the box holds 1,024 pieces, and the booklet uses every one.
              </p>
            </div>
            <div className="flow" aria-label="How one model drives everything">
              {FLOW.map(([a, b], i) => (
                <div className={`flow__row ${i === 1 ? 'is-core' : ''}`} key={a}>
                  <span className="flow__dot" />
                  {a}
                  <small>{b}</small>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="sizes">
        <div className="wrap">
          <div className="section__head">
            <span className="eyebrow">Sizes</span>
            <h2>Pick the size, we do the maths</h2>
            <p className="lede">
              Piece counts are hard limits, not guesses. The real dimensions and price are measured from your
              finished model and shown before you pay.
            </p>
          </div>
          <div className="sizes">
            {sizes.map((s) => (
              <div className="size-card" key={s.key}>
                <h3>{s.label}</h3>
                {s.max_pieces ? (
                  <span className="stat">Up to {s.max_pieces.toLocaleString()} pieces</span>
                ) : (
                  <span className="stat">10 to 40 cm wide</span>
                )}
                <ul>
                  {s.blurb.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                  {s.max_width_cm ? <li>About {Math.round(s.max_width_cm)} cm wide at most</li> : null}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="faq">
        <div className="wrap">
          <div className="section__head center">
            <span className="eyebrow">Questions</span>
            <h2 className="center">Good to know</h2>
          </div>
          <div className="faq">
            {FAQ.map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>

          <div className="cta-band">
            <h2>Got a photo you love? Let's build it.</h2>
            <Link to="/create" className="btn btn--light btn--lg">
              Create My Set <Arrow size={20} />
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
