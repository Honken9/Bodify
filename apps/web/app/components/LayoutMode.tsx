"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Mode = "auto" | "mobile" | "desktop";

const LayoutModeContext = createContext<{
  mode: Mode;
  resolved: "mobile" | "desktop";
  wideScreen: boolean;
  setMode: (mode: Mode) => void;
}>({
  mode: "auto",
  resolved: "mobile",
  wideScreen: false,
  setMode: () => {},
});

export function LayoutModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>("auto");
  const [wideScreen, setWideScreen] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem("shapiqo-layout");
    if (saved === "mobile" || saved === "desktop" || saved === "auto") {
      setModeState(saved);
    }
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setWideScreen(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const resolved: "mobile" | "desktop" =
    mode === "auto" ? (wideScreen ? "desktop" : "mobile") : mode;

  useEffect(() => {
    document.documentElement.setAttribute("data-layout", resolved);
  }, [resolved]);

  function setMode(next: Mode) {
    setModeState(next);
    window.localStorage.setItem("shapiqo-layout", next);
  }

  return (
    <LayoutModeContext.Provider value={{ mode, resolved, wideScreen, setMode }}>
      {children}
    </LayoutModeContext.Provider>
  );
}

export const useLayoutMode = () => useContext(LayoutModeContext);
