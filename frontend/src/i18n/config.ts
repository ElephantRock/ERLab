import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./en.json";
import zh from "./zh.json";
import es from "./es.json";
import fr from "./fr.json";
import de from "./de.json";
import ja from "./ja.json";
import ko from "./ko.json";
import pt from "./pt.json";
import ar from "./ar.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
      es: { translation: es },
      fr: { translation: fr },
      de: { translation: de },
      ja: { translation: ja },
      ko: { translation: ko },
      pt: { translation: pt },
      ar: { translation: ar },
    },
    fallbackLng: "en",
    lng: "en",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
