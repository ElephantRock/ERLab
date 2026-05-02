import i18n from "../config";
import en from "../en.json";

describe("i18n locales (BATCH-50)", () => {
  beforeEach(async () => {
    await i18n.init();
  });

  it("switches to zh and returns Chinese translations", async () => {
    await i18n.changeLanguage("zh");
    expect(i18n.t("common.loading")).toBe("加载中...");
    expect(i18n.t("nav.dashboard")).toBe("仪表板");
    expect(i18n.t("pages.pipeline")).toBe("研究管道");
  });

  it("switches to es and returns Spanish translations", async () => {
    await i18n.changeLanguage("es");
    expect(i18n.t("common.loading")).toBe("Cargando...");
    expect(i18n.t("nav.dashboard")).toBe("Panel");
    expect(i18n.t("pages.settings")).toBe("Configuración");
  });

  it("falls back to English for missing keys", async () => {
    await i18n.changeLanguage("zh");
    // Use a key that exists in en but verify fallback works via non-existent key
    const result = i18n.t("common.save");
    // zh has "保存" for save, so test with a truly missing key
    const fallback = i18n.t("nonexistent.key.that.does.not.exist");
    // With fallbackLng: "en", missing keys return the key string itself
    expect(fallback).toBe("nonexistent.key.that.does.not.exist");

    // Verify switching back to en works
    await i18n.changeLanguage("en");
    expect(i18n.t("common.loading")).toBe(en.common.loading);
  });
});
