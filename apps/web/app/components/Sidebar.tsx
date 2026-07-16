"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Me } from "../lib/types";
import { useLayoutMode } from "./LayoutMode";

const ITEMS = [
  { href: "/", label: "Hem", icon: "🏠" },
  { href: "/food", label: "Kost", icon: "🥗" },
  { href: "/health", label: "Hälsa", icon: "❤️" },
  { href: "/programs", label: "Program", icon: "📋" },
  { href: "/exercises", label: "Övningar", icon: "💪" },
  { href: "/history", label: "Historik", icon: "🕘" },
  { href: "/social", label: "Socialt", icon: "🏆" },
  { href: "/photos", label: "Foton", icon: "📸" },
  { href: "/settings", label: "Kopplingar", icon: "⚙️" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { setMode } = useLayoutMode();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api<Me>("/api/me").then(setMe).catch(() => {});
  }, []);

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-line bg-white px-4 py-6 desktop:flex dark:border-stone-800 dark:bg-stone-900">
      <Link
        href="/"
        className="px-3 text-lg font-bold lowercase tracking-wide text-sage"
      >
        shapiqo
      </Link>

      <nav className="mt-6 flex flex-1 flex-col gap-1">
        {ITEMS.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${
                active
                  ? "bg-sage-soft font-bold text-sage-deep dark:bg-emerald-950 dark:text-emerald-300"
                  : "font-medium text-muted hover:bg-cream-deep dark:text-stone-400 dark:hover:bg-stone-800"
              }`}
            >
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
        {me?.is_admin && (
          <Link
            href="/admin"
            className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${
              pathname.startsWith("/admin")
                ? "bg-sage-soft font-bold text-sage-deep dark:bg-emerald-950 dark:text-emerald-300"
                : "font-medium text-muted hover:bg-cream-deep dark:text-stone-400 dark:hover:bg-stone-800"
            }`}
          >
            <span className="text-base leading-none">🛠️</span>
            Admin
          </Link>
        )}
      </nav>

      <div className="border-t border-line pt-3 dark:border-stone-800">
        {me && (
          <p className="truncate px-3 pb-2 text-xs text-faint">
            {me.display_name ?? me.email}
          </p>
        )}
        <div className="flex gap-1.5 px-1">
          <button
            onClick={() => setMode("mobile")}
            className="flex-1 rounded-lg bg-shell py-1.5 text-xs font-semibold text-muted dark:bg-stone-800 dark:text-stone-300"
            title="Smal mobilvy"
          >
            📱 Mobilläge
          </button>
          <button
            onClick={() => setMode("auto")}
            className="rounded-lg bg-shell px-3 py-1.5 text-xs font-semibold text-muted dark:bg-stone-800 dark:text-stone-300"
            title="Följ skärmstorleken"
          >
            Auto
          </button>
        </div>
      </div>
    </aside>
  );
}
