import { useEffect } from "react";
import type { Theme } from "@paperhelp/shared";
import { useUiStore } from "@paperhelp/shared";

function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return theme;
}

function applyResolvedTheme(resolved: "light" | "dark") {
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

/** Syncs uiStore theme to the document root for Tailwind dark mode. */
export function useThemeEffect() {
  const theme = useUiStore((s) => s.theme);

  useEffect(() => {
    applyResolvedTheme(resolveTheme(theme));

    if (theme !== "system") return;

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyResolvedTheme(resolveTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme]);
}
