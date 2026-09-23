import { useEffect, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { Logo } from './icons';
import { useConfig } from '../config';

export default function Layout({ children }: { children: ReactNode }) {
  const [scrolled, setScrolled] = useState(false);
  const { pathname } = useLocation();
  const config = useConfig();
  const inFlow = pathname.startsWith('/create') || pathname.startsWith('/build') || pathname.startsWith('/checkout');

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener('scroll', on, { passive: true });
    return () => window.removeEventListener('scroll', on);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);

  return (
    <>
      <header className={`header ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="wrap header__inner">
          <Link to="/" className="logo" aria-label="Kitsnap home">
            <Logo />
            <span>{config?.brand ?? 'Kitsnap'}</span>
          </Link>
          {!inFlow && (
            <nav className="nav" aria-label="Main">
              <a href="/#how">How it works</a>
              <a href="/#examples">Examples</a>
              <a href="/#sizes">Sizes</a>
              <a href="/#faq">FAQ</a>
            </nav>
          )}
          {!inFlow && (
            <Link to="/create" className="btn btn--primary btn--sm">
              Create My Set
            </Link>
          )}
        </div>
      </header>
      <main>{children}</main>
      <footer className="footer">
        <div className="wrap">
          <div className="footer__grid">
            <div className="stack">
              <Link to="/" className="logo">
                <Logo />
                <span>{config?.brand ?? 'Kitsnap'}</span>
              </Link>
              <p className="small">Your photo, rebuilt as a real brick set, delivered with printed instructions.</p>
            </div>
            <div>
              <h4>Make</h4>
              <ul>
                <li><Link to="/create">Create a set</Link></li>
                <li><a href="/#examples">Examples</a></li>
                <li><a href="/#sizes">Sizes and prices</a></li>
              </ul>
            </div>
            <div>
              <h4>Help</h4>
              <ul>
                <li><a href="/#how">How it works</a></li>
                <li><a href="/#faq">Questions</a></li>
                <li><a href="mailto:hello@kitsnap.example">Contact us</a></li>
              </ul>
            </div>
          </div>
          <div className="footer__legal">
            <p>{config?.disclaimer}</p>
            <p style={{ marginTop: 8 }}>© {new Date().getFullYear()} {config?.brand ?? 'Kitsnap'}</p>
          </div>
        </div>
      </footer>
    </>
  );
}
