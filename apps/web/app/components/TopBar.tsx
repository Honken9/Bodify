"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Me } from "../lib/types";
import { useLayoutMode } from "./LayoutMode";
import Logo from "./Logo";

function initialsOf(me: Me): string {
  const source = me.display_name?.trim() || me.email;
  const parts = source.split(/[\s.@_-]+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

export default function TopBar() {
  const [initials, setInitials] = useState<string | null>(null);
  const { resolved, wideScreen, setMode } = useLayoutMode();

  useEffect(() => {
    api<Me>("/api/me")
      .then((me) => setInitials(initialsOf(me)))
      .catch(() => {});
  }, []);

  return (
    <header className="mx-auto flex w-full max-w-md items-center justify-between px-5 pt-4 desktop:hidden">
      <Logo badge={30} name={16} />
      <div className="flex items-center gap-2">
        {wideScreen && resolved === "mobile" && (
          <button
            onClick={() => setMode("desktop")}
            className="rounded-full bg-shell px-3 py-1.5 text-xs font-semibold text-muted dark:bg-stone-800 dark:text-stone-300"
            title="Bredare layout med sidomeny"
          >
            🖥️ Helskärmsläge
          </button>
        )}
        <a
          href="/settings"
          aria-label="Inställningar & kopplingar"
          className="flex h-8 w-8 items-center justify-center rounded-full bg-shell text-[11px] font-semibold text-sand-ink dark:bg-stone-800 dark:text-stone-300"
        >
          {initials ?? "•"}
        </a>
      </div>
    </header>
  );
}
