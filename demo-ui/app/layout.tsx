import type { Metadata } from "next";
import "./globals.css";
import "./stitch-ui.css";

export const metadata: Metadata = {
  title: "AI Engineering Console · Lab Demo",
  description: "Training evaluation, grounded tools, and deterministic workflow observability.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `document.documentElement.dataset.theme='light'` }} /></head>
      <body>{children}</body>
    </html>
  );
}
