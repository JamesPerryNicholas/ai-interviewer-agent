export type ThemeMode = "light" | "dark" | "system";

export const THEME_KEY = "ai-interviewer-theme";

function prefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(mode: ThemeMode) {
  const dark = mode === "dark" || (mode === "system" && prefersDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem(THEME_KEY, mode);
}

export function getThemeMode(): ThemeMode {
  const value = localStorage.getItem(THEME_KEY);
  return value === "dark" || value === "system" ? value : "light";
}

export function initTheme() {
  applyTheme(getThemeMode());
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener?.("change", () => {
    if (getThemeMode() === "system") applyTheme("system");
  });
}
