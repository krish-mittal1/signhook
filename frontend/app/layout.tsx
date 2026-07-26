import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "signhook",
  description: "Generate, sign, and send webhook payloads locally",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-100 text-zinc-900 antialiased">
        {children}
      </body>
    </html>
  );
}
