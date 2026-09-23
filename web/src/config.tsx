import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { api, type StoreConfig } from './api';

const Ctx = createContext<StoreConfig | null>(null);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<StoreConfig | null>(null);
  useEffect(() => {
    let alive = true;
    const load = (attempt: number) =>
      api.config().then(
        (c) => alive && setConfig(c),
        () => alive && attempt < 4 && setTimeout(() => load(attempt + 1), 1500 * (attempt + 1)),
      );
    load(0);
    return () => {
      alive = false;
    };
  }, []);
  return <Ctx.Provider value={config}>{children}</Ctx.Provider>;
}

export const useConfig = () => useContext(Ctx);
