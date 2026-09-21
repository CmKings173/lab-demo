import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lab demo — workflow trace",
  description: "Realtime deterministic workflow observability demo",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
