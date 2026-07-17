"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Hem", icon: "🏠" },
  { href: "/food", label: "Kost", icon: "🥗" },
  { href: "/health", label: "Hälsa", icon: "❤️" },
  { href: "/programs", label: "Träning", icon: "🏋️" },
  { href: "/history", label: "Historik", icon: "🕘" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="desktop:hidden fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 backdrop-blur dark:border-night-shell dark:bg-night-card/95">
      <div className="mx-auto flex max-w-md pb-[env(safe-area-inset-bottom)]">
        {TABS.map((tab) => {
          const active =
            tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-xs ${
                active
                  ? "font-bold text-navy dark:text-lime"
                  : "text-muted dark:text-faint"
              }`}
            >
              <span className="text-lg leading-none">{tab.icon}</span>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
