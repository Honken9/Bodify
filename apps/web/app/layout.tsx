import type { Metadata, Viewport } from "next";
import Nav from "./components/Nav";
import ServiceWorkerRegistrar from "./components/ServiceWorkerRegistrar";
import "./globals.css";

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
  themeColor: "#052e16",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="sv">
      <body className="min-h-dvh bg-stone-50 pb-20 text-stone-900 antialiased dark:bg-stone-950 dark:text-stone-100">
        {children}
        <Nav />
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
