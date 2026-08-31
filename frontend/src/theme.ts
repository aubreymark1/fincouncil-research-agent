export type Theme = "dark" | "light";

interface ThemeStorage {
  getItem(key: string): string | null;
}

export function nextTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
}

export function getInitialTheme(storage: ThemeStorage, prefersLight: boolean): Theme {
  const stored = storage.getItem("fincouncil-theme");
  if (stored === "light" || stored === "dark") return stored;
  return prefersLight ? "light" : "dark";
}
