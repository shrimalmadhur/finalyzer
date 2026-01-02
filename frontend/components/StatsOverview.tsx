"use client";

import { Receipt, TrendingUp, ArrowRight } from "lucide-react";
import Link from "next/link";

interface StatsOverviewProps {
  transactionCount: number;
}

export function StatsOverview({ transactionCount }: StatsOverviewProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Transaction count */}
      <div className="elevated-card rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-midnight-400 uppercase tracking-wider">
              Total Transactions
            </p>
            <p className="font-display text-4xl font-semibold text-cream-100">
              {transactionCount.toLocaleString()}
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-jade-500/10 flex items-center justify-center">
            <Receipt className="w-6 h-6 text-jade-400" />
          </div>
        </div>

        {/* Decorative bar */}
        <div className="mt-6 h-1 rounded-full bg-ink-lighter overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-jade-500 to-jade-400 rounded-full"
            style={{ width: "100%" }}
          />
        </div>
      </div>

      {/* Quick action - Analyze */}
      <Link
        href="/chat"
        className="group elevated-card rounded-2xl p-6 cursor-pointer"
      >
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-midnight-400 uppercase tracking-wider">
              AI Assistant
            </p>
            <p className="font-display text-2xl font-semibold text-cream-100 group-hover:text-jade-300 transition-colors">
              Analyze Spending
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-jade-500/10 group-hover:bg-jade-500/20 flex items-center justify-center transition-colors">
            <TrendingUp className="w-6 h-6 text-jade-400" />
          </div>
        </div>

        <div className="mt-6 flex items-center gap-2 text-sm text-jade-400 group-hover:text-jade-300 transition-colors">
          <span>Ask questions about your finances</span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
        </div>
      </Link>
    </div>
  );
}
