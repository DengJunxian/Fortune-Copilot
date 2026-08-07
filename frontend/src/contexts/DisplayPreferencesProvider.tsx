import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  DisplayPreferencesContext,
  type DisplayPreferencesValue,
  type MoneyUnitPreference,
  type ThemePreference,
  type ValueViewPreference,
} from "./displayPreferences";

export function DisplayPreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemePreference>("light");
  const [largeText, setLargeText] = useState(false);
  const [plainLanguage, setPlainLanguage] = useState(false);
  const [maskAmounts, setMaskAmounts] = useState(false);
  const [valueView, setValueView] = useState<ValueViewPreference>("amount");
  const [moneyUnit, setMoneyUnit] = useState<MoneyUnitPreference>("yuan");

  useEffect(() => {
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const value = useMemo<DisplayPreferencesValue>(
    () => ({
      theme,
      largeText,
      plainLanguage,
      maskAmounts,
      valueView,
      moneyUnit,
      setTheme,
      setLargeText,
      setPlainLanguage,
      setMaskAmounts,
      setValueView,
      setMoneyUnit,
    }),
    [theme, largeText, plainLanguage, maskAmounts, valueView, moneyUnit],
  );

  return (
    <DisplayPreferencesContext.Provider value={value}>
      {children}
    </DisplayPreferencesContext.Provider>
  );
}
