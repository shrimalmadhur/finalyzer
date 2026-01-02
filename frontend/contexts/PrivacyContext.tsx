"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from "react";

interface PrivacyContextType {
  isHidden: boolean;
  toggle: () => void;
  formatAmount: (amount: number) => string;
}

const PrivacyContext = createContext<PrivacyContextType | undefined>(undefined);

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [isHidden, setIsHidden] = useState(false);

  const toggle = useCallback(() => {
    setIsHidden((prev) => !prev);
  }, []);

  const formatAmount = useCallback(
    (amount: number) => {
      if (isHidden) {
        return "••••••";
      }
      const formatted = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
      }).format(Math.abs(amount));

      return amount < 0 ? `-${formatted}` : formatted;
    },
    [isHidden]
  );

  return (
    <PrivacyContext.Provider value={{ isHidden, toggle, formatAmount }}>
      {children}
    </PrivacyContext.Provider>
  );
}

export function usePrivacy() {
  const context = useContext(PrivacyContext);
  if (context === undefined) {
    throw new Error("usePrivacy must be used within a PrivacyProvider");
  }
  return context;
}
