"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Upload,
  MessageSquare,
  Settings,
  BarChart3,
  Sparkles,
  Eye,
  EyeOff,
} from "lucide-react";
import clsx from "clsx";
import { usePrivacy } from "@/contexts/PrivacyContext";

const navItems = [
  { href: "/", label: "Upload", icon: Upload },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/chat", label: "Ask AI", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();
  const { isHidden, toggle } = usePrivacy();

  return (
    <header className="sticky top-0 z-50">
      {/* Blur backdrop */}
      <div className="absolute inset-0 bg-ink/80 backdrop-blur-xl border-b border-jade-500/10" />

      <div className="relative container mx-auto px-6 max-w-6xl">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            {/* Logo mark */}
            <div className="relative">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-jade-400 to-jade-600 flex items-center justify-center shadow-glow transition-shadow duration-300 group-hover:shadow-glow-lg">
                <Sparkles className="w-5 h-5 text-ink" />
              </div>
              {/* Glow effect */}
              <div className="absolute inset-0 w-9 h-9 rounded-xl bg-jade-500/30 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </div>

            {/* Wordmark */}
            <div className="flex items-baseline">
              <span className="font-display text-xl font-bold text-jade-400 tracking-tight">
                FIN
              </span>
              <span className="font-display text-xl font-semibold text-cream-100 tracking-tight italic">
                alyzer
              </span>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-3">
            {/* Nav pills container */}
            <div className="flex items-center gap-1 p-1 rounded-full bg-ink-light/50 border border-white/[0.03]">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={clsx(
                      "relative flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-300",
                      isActive
                        ? "text-ink"
                        : "text-midnight-300 hover:text-cream-100"
                    )}
                  >
                    {/* Active background */}
                    {isActive && (
                      <div className="absolute inset-0 rounded-full bg-gradient-to-r from-jade-400 to-jade-500 shadow-glow" />
                    )}

                    {/* Content */}
                    <span className="relative flex items-center gap-2">
                      <Icon
                        className={clsx(
                          "w-4 h-4 transition-transform duration-300",
                          isActive && "scale-110"
                        )}
                      />
                      <span className="hidden sm:inline">{item.label}</span>
                    </span>
                  </Link>
                );
              })}
            </div>

            {/* Privacy Toggle Button */}
            <button
              onClick={toggle}
              className={clsx(
                "relative flex items-center justify-center w-10 h-10 rounded-full transition-all duration-300",
                "border border-white/[0.05] hover:border-jade-500/30",
                isHidden
                  ? "bg-jade-500/20 text-jade-400"
                  : "bg-ink-light/50 text-midnight-300 hover:text-cream-100"
              )}
              title={isHidden ? "Show amounts" : "Hide amounts"}
              aria-label={isHidden ? "Show amounts" : "Hide amounts"}
            >
              {isHidden ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
              {/* Active glow */}
              {isHidden && (
                <div className="absolute inset-0 rounded-full bg-jade-500/10 blur-md" />
              )}
            </button>
          </nav>
        </div>
      </div>

      {/* Decorative bottom line */}
      <div className="absolute bottom-0 left-0 right-0 h-px">
        <div className="h-full w-full bg-gradient-to-r from-transparent via-jade-500/20 to-transparent" />
      </div>
    </header>
  );
}
