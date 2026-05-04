import { useEffect } from "react";
import { useTranslation } from "react-i18next";

const RTL_LANGUAGES = ["ar"];

/**
 * Hook that sets document direction and lang attribute based on current language.
 * Supports RTL languages (Arabic) and sets dir="rtl" on <html> element.
 * BATCH-71: i18n + RTL support.
 */
export function useRTL() {
  const { i18n } = useTranslation();
  const lng = i18n.language;

  useEffect(() => {
    const isRTL = RTL_LANGUAGES.includes(lng);
    document.documentElement.dir = isRTL ? "rtl" : "ltr";
    document.documentElement.lang = lng;
  }, [lng]);
}
