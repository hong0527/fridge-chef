'use client';

import { createContext, useContext, useState } from 'react';

interface NavigationGuardContextType {
  isDirty: boolean;
  setIsDirty: (v: boolean) => void;
}

const NavigationGuardContext = createContext<NavigationGuardContextType>({
  isDirty: false,
  setIsDirty: () => {},
});

export function NavigationGuardProvider({ children }: { children: React.ReactNode }) {
  const [isDirty, setIsDirty] = useState(false);
  return (
    <NavigationGuardContext.Provider value={{ isDirty, setIsDirty }}>
      {children}
    </NavigationGuardContext.Provider>
  );
}

export const useNavigationGuard = () => useContext(NavigationGuardContext);
