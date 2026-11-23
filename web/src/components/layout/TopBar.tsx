import { LockKeyhole, Menu, Moon, Plus, Search, Sun } from "lucide-react";
import { useEffect, useRef } from "react";
import type { View } from "@/lib/types";

const labels: Record<View, { eyebrow: string; title: string }> = {
  dashboard: { eyebrow: "Overview", title: "Command Center" },
  leads: { eyebrow: "Intelligence", title: "Lead Explorer" },
  scraper: { eyebrow: "Automation", title: "Auto-Scraper" },
  settings: { eyebrow: "Workspace", title: "Quota & Settings" },
};

interface TopBarProps {
  view: View;
  isOwner: boolean;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onRun: () => void;
  onMenu: () => void;
}

export default function TopBar({
  view,
  isOwner,
  theme,
  onToggleTheme,
  searchQuery,
  onSearchChange,
  onRun,
  onMenu,
}: TopBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Toggle navigation">
        <Menu size={20} />
      </button>
      <div className="title-block">
        <span>{labels[view].eyebrow}</span>
        <h1>{labels[view].title}</h1>
      </div>
      <div className="top-actions">
        {isOwner && <span className="workspace-pill">LIVE · prospectiq</span>}
        <label className="global-search">
          <Search size={17} />
          <input
            ref={inputRef}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search leads, cities, domains..."
          />
          <kbd>⌘ K</kbd>
        </label>
        <button
          className="theme-toggle"
          type="button"
          onClick={onToggleTheme}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="primary-button" onClick={onRun}>
          {isOwner ? <Plus size={17} /> : <LockKeyhole size={15} />} Run scrape
        </button>
      </div>
    </header>
  );
}
