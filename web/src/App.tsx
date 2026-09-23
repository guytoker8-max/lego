import { lazy, Suspense } from 'react';
import { Link, Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import Home from './pages/Home';

// The 3D viewer (three.js) is the heavy part; pages that use it load on demand
// so the homepage's first paint isn't waiting for it.
const Create = lazy(() => import('./pages/Create'));
const Build = lazy(() => import('./pages/Build'));
const DesignPage = lazy(() => import('./pages/Design'));
const Checkout = lazy(() => import('./pages/Checkout'));
const TestPay = lazy(() => import('./pages/TestPay'));
const OrderPage = lazy(() => import('./pages/Order'));
const Ops = lazy(() => import('./pages/Ops'));
const Render = lazy(() => import('./pages/Render'));

function Loading() {
  return (
    <div className="page-center">
      <div className="spinner spinner--dark" />
    </div>
  );
}

function NotFound() {
  return (
    <div className="wrap page-center">
      <h2>That page isn't here</h2>
      <p className="muted">It may have moved, or the link is incomplete.</p>
      <Link className="btn" to="/">Back to the homepage</Link>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/render/:id" element={<Render />} />
        <Route
          path="*"
          element={
            <Layout>
              <Suspense fallback={<Loading />}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/create" element={<Create />} />
                  <Route path="/build/:jobId" element={<Build />} />
                  <Route path="/design/:id" element={<DesignPage />} />
                  <Route path="/checkout/test/:orderId" element={<TestPay />} />
                  <Route path="/checkout/:id" element={<Checkout />} />
                  <Route path="/order/:id" element={<OrderPage />} />
                  <Route path="/ops" element={<Ops />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </Layout>
          }
        />
      </Routes>
    </Suspense>
  );
}
