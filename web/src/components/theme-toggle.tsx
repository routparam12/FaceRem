"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "faceattend_theme";

export default function ThemeToggle() {
  const [isGlass, setIsGlass] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem(STORAGE_KEY);
    const active = saved !== "flat";
    setIsGlass(active);
    if (!active) {
      document.documentElement.setAttribute("data-theme", "flat");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, []);

  function toggle() {
    const next = !isGlass;
    setIsGlass(next);
    if (next) {
      localStorage.setItem(STORAGE_KEY, "glass");
      document.documentElement.removeAttribute("data-theme");
    } else {
      localStorage.setItem(STORAGE_KEY, "flat");
      document.documentElement.setAttribute("data-theme", "flat");
    }
  }

  if (!mounted) {
    return (
      <div className="flex h-7 items-center gap-1.5 rounded-full border border-ink-200/60 bg-white/50 px-2.5 text-xs font-medium text-ink-600">
        <span className="size-2 rounded-full bg-brand-500" />
        <span>Liquid glass: On</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex h-7 items-center gap-1.5 rounded-full border border-ink-200/70 bg-white/60 px-2.5 text-xs font-semibold text-ink-700 shadow-xs backdrop-blur-xs transition hover:bg-white hover:text-ink-900 dark:border-ink-700/60 dark:bg-ink-800/60 dark:text-ink-300 dark:hover:bg-ink-800"
      title={`Toggle style: currently ${isGlass ? "Liquid glass" : "Flat"}`}
      aria-label={`Toggle Liquid Glass styling. Currently ${isGlass ? "on" : "off"}.`}
    >
      <span
        className="size-2 rounded-full transition-colors"
        style={{ backgroundColor: isGlass ? "#2970ff" : "#98a2b3" }}
      />
      <span>Liquid glass: {isGlass ? "On" : "Off"}</span>
    </button>
  );
}

