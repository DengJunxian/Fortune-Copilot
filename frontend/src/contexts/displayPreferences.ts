import { createContext, useContext } from "react";

export type ThemePreference = "light" | "dark";
export type ValueViewPreference = "amount" | "ratio";
export type MoneyUnitPreference = "yuan" | "wan";

export interface DisplayPreferencesValue {
  theme: ThemePreference;
  largeText: boolean;
  plainLanguage: boolean;
  maskAmounts: boolean;
  valueView: ValueViewPreference;
  moneyUnit: MoneyUnitPreference;
  setTheme: (value: ThemePreference) => void;
  setLargeText: (value: boolean) => void;
  setPlainLanguage: (value: boolean) => void;
  setMaskAmounts: (value: boolean) => void;
  setValueView: (value: ValueViewPreference) => void;
  setMoneyUnit: (value: MoneyUnitPreference) => void;
}

export const DisplayPreferencesContext = createContext<DisplayPreferencesValue | undefined>(undefined);

export function useDisplayPreferences(): DisplayPreferencesValue {
  const value = useContext(DisplayPreferencesContext);
  if (!value) throw new Error("Display preferences context is missing");
  return value;
}
