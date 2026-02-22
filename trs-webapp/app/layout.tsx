import type { Metadata } from "next";
import "./globals.css";
import { Layout } from "@/components/layout";

export const metadata: Metadata = {
  title: "TRS - Teammate Reputation System",
  description: "One-stop solution for serious competitors looking for reputable team-ups",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">
        <Layout>{children}</Layout>
      </body>
    </html>
  );
}
