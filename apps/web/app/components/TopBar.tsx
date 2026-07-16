"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Me } from "../lib/types";

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

  useEffect(() => {
    api<Me>("/api/me")
      .then((me) => setInitials(initialsOf(me)))
      .catch(() => {});
  }, []);

  return (
    <header className="mx-auto flex w-full max-w-md items-center justify-between px-5 pt-4">
      <a
        href="/"
        className="text-[15px] font-bold lowercase tracking-wide text-sage"
      >
        shapiqo
      </a>
      <a
        href="/settings"
        aria-label="Inställningar & kopplingar"
        className="flex h-8 w-8 items-center justify-center rounded-full bg-shell text-[11px] font-semibold text-sand-ink dark:bg-stone-800 dark:text-stone-300"
      >
        {initials ?? "•"}
      </a>
    </header>
  );
}
