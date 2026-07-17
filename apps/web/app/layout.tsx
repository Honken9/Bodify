import type { Metadata, Viewport } from "next";
import { DM_Sans, Montserrat } from "next/font/google";
import { LayoutModeProvider } from "./components/LayoutMode";
import Nav from "./components/Nav";
import ServiceWorkerRegistrar from "./components/ServiceWorkerRegistrar";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

// Endast för logotypen (badge-S + wordmark) enligt varumärkesguiden
const montserrat = Montserrat({
  subsets: ["latin"],
  weight: "800",
  style: ["normal", "italic"],
  variable: "--font-montserrat",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Shapiqo",
  description: "Din self-hostade plattform för kost och träning",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/brand/shapiqo-icon.svg", type: "image/svg+xml" },
      { url: "/brand/shapiqo-icon.png", type: "image/png", sizes: "384x384" },
    ],
    apple: "/brand/shapiqo-icon-180.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Shapiqo",
  },
};

export const viewport: Viewport = {
  themeColor: "#faf7f1",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sv" className={`${dmSans.variable} ${montserrat.variable}`}>
      <body className="min-h-dvh bg-cream pb-20 font-sans text-ink antialiased desktop:pb-8 desktop:pl-60 dark:bg-stone-950 dark:text-stone-100">
        <LayoutModeProvider>
          <TopBar />
          <Sidebar />
          {children}
          <Nav />
        </LayoutModeProvider>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
