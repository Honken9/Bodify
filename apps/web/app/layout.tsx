import type { Metadata, Viewport } from "next";
import { DM_Sans } from "next/font/google";
import Nav from "./components/Nav";
import ServiceWorkerRegistrar from "./components/ServiceWorkerRegistrar";
import TopBar from "./components/TopBar";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Shapiqo",
  description: "Din self-hostade plattform för kost och träning",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Shapiqo",
  },
};

export const viewport: Viewport = {
  themeColor: "#5b7a5e",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sv" className={dmSans.variable}>
      <body className="min-h-dvh bg-cream pb-20 font-sans text-ink antialiased dark:bg-stone-950 dark:text-stone-100">
        <TopBar />
        {children}
        <Nav />
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
