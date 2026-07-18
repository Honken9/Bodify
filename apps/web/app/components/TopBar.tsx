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
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const { resolved, wideScreen, setMode } = useLayoutMode();

  useEffect(() => {
    api<Me>("/api/me")
      .then((me) => {
        setInitials(initialsOf(me));
        setAvatarUrl(me.avatar_url);
      })
      .catch(() => {});
  }, []);

  return (
    <header className="mx-auto flex w-full max-w-md items-center justify-between px-5 pt-4 desktop:hidden">
      <Logo badge={30} name={16} />
      <div className="flex items-center gap-2">
        {wideScreen && resolved === "mobile" && (
          <button
            onClick={() => setMode("desktop")}
            className="rounded-full bg-shell px-3 py-1.5 text-xs font-semibold text-muted dark:bg-night-shell dark:text-night-muted"
            title="Bredare layout med sidomeny"
          >
            🖥️ Helskärmsläge
          </button>
        )}
        <a
          href="/settings"
          aria-label="Kopplingar & inställningar"
          title="Kopplingar & inställningar"
          className="flex h-8 w-8 items-center justify-center rounded-full bg-shell text-base dark:bg-night-shell"
        >
          ⚙️
        </a>
        <a
          href="/profile"
          aria-label="Min profil"
          className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-shell text-[11px] font-semibold text-sand-ink dark:bg-night-shell dark:text-night-muted"
        >
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarUrl}
              alt="Profil"
              className="h-full w-full object-cover"
            />
          ) : (
            initials ?? "•"
          )}
        </a>
      </div>
    </header>
  );
}
