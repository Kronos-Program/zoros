import React from 'react';

export interface Fiber {
  id: string;
  content: string;
  tags: string;
  created_at: string;
  source: string;
}

interface ZorosState {
  fibers: Fiber[];
  filter: string;
  selectedThread: string | null;
  setFibers: (f: Fiber[]) => void;
  setFilter: (q: string) => void;
  setSelectedThread: (t: string | null) => void;
}

const StoreContext = React.createContext<ZorosState | null>(null);

export const ZorosStoreProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [fibers, setFibers] = React.useState<Fiber[]>([]);
  const [filter, setFilter] = React.useState('');
  const [selectedThread, setSelectedThread] = React.useState<string | null>(null);

  const value: ZorosState = {
    fibers,
    filter,
    selectedThread,
    setFibers,
    setFilter,
    setSelectedThread,
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
};

export const useZorosStore = () => {
  const ctx = React.useContext(StoreContext);
  if (!ctx) throw new Error('useZorosStore must be used within provider');
  return ctx;
};
