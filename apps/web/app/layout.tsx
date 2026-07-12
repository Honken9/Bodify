import type { Metadata, Viewport } from "next";
import Nav from "./components/Nav";
import ServiceWorkerRegistrar from "./components/ServiceWorkerRegistrar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bodify",
  description: "Din self-hostade plattform för kost och träning",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Bodify",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sv">
      <body className="min-h-dvh bg-slate-50 pb-20 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        {children}
        <Nav />
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
