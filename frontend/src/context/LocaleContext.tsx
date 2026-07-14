import { createContext, useContext, type ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { translations, type Translations, type Lang } from "../i18n/translations";

interface LocaleContextType {
  lang: Lang;
  t: Translations;
}

const LocaleContext = createContext<LocaleContextType>({
  lang: "de",
  t: translations.de,
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const lang: Lang = user?.language === "en" ? "en" : "de";
  return (
    <LocaleContext.Provider value={{ lang, t: translations[lang] }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useT() {
  return useContext(LocaleContext).t;
}

export function useLang() {
  return useContext(LocaleContext).lang;
}
