import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ApiError, type Job } from '../api';
import { Check } from '../components/icons';
import { Stepper } from './Create';

/**
 * The analysis screen. It shows the stage the server says it is in, and
 * nothing else: no invented percentage, no timer pretending to know how long
 * is left. When the builder has to try a smaller size to fit the piece
 * count, it says that too.
 */
export default function Build() {
  const { jobId = '' } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    let misses = 0;
    const poll = async () => {
      try {
        const j = await api.job(jobId);
        if (!alive) return;
        misses = 0;
        setJob(j);
        if (j.status === 'done' && j.model_id) {
          timer = window.setTimeout(() => navigate(`/design/${j.model_id}`, { replace: true }), 700);
          return;
        }
        if (j.status === 'failed') return;
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 404) {
          setError("We couldn't find that set. It may have expired.");
          return;
        }
        misses += 1;
        if (misses > 20) {
          setError('We lost touch with the builder. Please refresh the page.');
          return;
        }
      }
      timer = window.setTimeout(poll, 900);
    };
    poll();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [jobId, navigate]);

  const stages = (job?.stages ?? []).filter((s) => s.key !== 'queued' || s.state === 'active');
  const photo = job?.photos?.[0]?.url;

  return (
    <div className="wrap flowpage">
      <Stepper current="preview" done={['upload', 'subject', 'size']} />
      <section className="panel">
        {error ? (
          <div className="page-center">
            <h2>{error}</h2>
            <Link to="/create" className="btn btn--primary">Start again</Link>
          </div>
        ) : job?.status === 'failed' ? (
          <div className="page-center">
            <h2>We couldn't build this one</h2>
            <p className="muted" style={{ maxWidth: 520 }}>{job.error}</p>
            <div className="hero__ctas" style={{ justifyContent: 'center', marginTop: 8 }}>
              <Link to="/create" className="btn btn--primary">Try another photo</Link>
            </div>
          </div>
        ) : (
          <div className="building">
            <div className="building__photo" aria-hidden>
              {photo ? <img src={photo} alt="" /> : <div className="skeleton" style={{ position: 'absolute', inset: 0 }} />}
              <div className="building__scan" />
            </div>
            <div className="stack" style={{ gap: 20 }}>
              <div className="stack" style={{ gap: 8 }}>
                <h2>{job?.status === 'done' ? 'Your set is ready' : 'Building your set'}</h2>
                <p className="muted" aria-live="polite">{job?.message ?? 'Starting...'}</p>
              </div>
              <ol className="stages">
                {stages.map((s) => (
                  <li key={s.key} className={`stage is-${s.state}`}>
                    <span className="stage__dot">{s.state === 'done' ? <Check size={15} /> : null}</span>
                    {s.label}
                  </li>
                ))}
              </ol>
              <p className="muted small">
                Every brick is placed, checked and counted for real, so this usually takes under a minute.
                You can leave this page open; it moves on by itself.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
