import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lab demo — workflow trace",
  description: "Realtime deterministic workflow observability demo",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem('lab-demo-theme');document.documentElement.dataset.theme=t==='light'||t==='system'?t:'dark'}catch(e){document.documentElement.dataset.theme='dark'}` }} /></head>
      <body>{children}</body>
    </html>
  );
}
