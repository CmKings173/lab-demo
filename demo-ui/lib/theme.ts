export type ThemePreference = "dark" | "light" | "system";
export const THEME_KEY = "lab-demo-theme";

export function nextTheme(current: ThemePreference): ThemePreference {
  if (current === "dark") return "light";
  if (current === "light") return "system";
  return "dark";
}

export function readTheme(): ThemePreference {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" || saved === "system" ? saved : "dark";
  } catch {
    return "dark";
  }
}

export function saveTheme(theme: ThemePreference): void {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* Storage can be disabled. */ }
  window.dispatchEvent(new Event("lab-demo-theme-change"));
}

export function subscribeTheme(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  window.addEventListener("lab-demo-theme-change", onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener("lab-demo-theme-change", onChange);
  };
}
