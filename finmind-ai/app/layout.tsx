import React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FinGuard AI — Intelligent Financial Security Platform",
  description:
    "AI-powered financial security platform with real-time fraud detection, risk scoring, spending analytics, and an intelligent financial assistant. Built for modern finance teams.",
  keywords: ["finance", "AI", "fraud detection", "financial security", "analytics"],
  authors: [{ name: "FinGuard AI" }],
  openGraph: {
    title: "FinGuard AI",
    description: "AI-powered financial security and analytics platform",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
