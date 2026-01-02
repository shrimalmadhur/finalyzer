import type { Metadata } from "next";
import { Fraunces, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/Navigation";
import { PrivacyProvider } from "@/contexts/PrivacyContext";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "FINalyzer - Personal Finance Analyzer",
  description:
    "Analyze your finances with AI-powered categorization and natural language queries",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-ink text-cream-100 font-sans antialiased selection:bg-jade-500/30 selection:text-jade-100">
        <PrivacyProvider>
          {/* Grain texture overlay */}
          <div className="grain-overlay" aria-hidden="true" />

          {/* Ambient gradient background */}
          <div className="fixed inset-0 -z-10 overflow-hidden">
            {/* Base gradient */}
            <div className="absolute inset-0 bg-gradient-to-b from-ink via-ink-light to-ink" />

            {/* Floating orbs */}
            <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-jade-500/[0.03] blur-3xl animate-float" />
            <div
              className="absolute top-1/2 -left-40 w-[500px] h-[500px] rounded-full bg-jade-600/[0.02] blur-3xl animate-float"
              style={{ animationDelay: "-3s" }}
            />
            <div
              className="absolute -bottom-20 right-1/4 w-[400px] h-[400px] rounded-full bg-cream-500/[0.02] blur-3xl animate-float"
              style={{ animationDelay: "-1.5s" }}
            />

            {/* Grid pattern */}
            <div
              className="absolute inset-0 opacity-[0.015]"
              style={{
                backgroundImage: `linear-gradient(rgba(26, 205, 138, 0.5) 1px, transparent 1px),
                                 linear-gradient(90deg, rgba(26, 205, 138, 0.5) 1px, transparent 1px)`,
                backgroundSize: "60px 60px",
              }}
            />
          </div>

          <div className="relative flex flex-col min-h-screen">
            <Navigation />
            <main className="flex-1 container mx-auto px-6 py-10 max-w-6xl">
              {children}
            </main>

            {/* Footer */}
            <footer className="border-t border-midnight-800/50 py-6">
              <div className="container mx-auto px-6 max-w-6xl">
                <div className="flex items-center justify-between text-sm text-midnight-400">
                  <span className="font-display">
                    <span className="font-bold text-jade-400">FIN</span>
                    <span className="italic text-midnight-300">alyzer</span>
                  </span>
                  <span>Your finances, understood.</span>
                </div>
              </div>
            </footer>
          </div>
        </PrivacyProvider>
      </body>
    </html>
  );
}
