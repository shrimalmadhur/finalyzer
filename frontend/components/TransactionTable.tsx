"use client";

import { Transaction } from "@/lib/api";
import { ArrowUpRight, ArrowDownRight, CreditCard } from "lucide-react";
import clsx from "clsx";
import { usePrivacy } from "@/contexts/PrivacyContext";

interface TransactionTableProps {
  transactions: Transaction[];
  compact?: boolean;
}

const categoryColors: Record<string, string> = {
  "Food & Dining": "bg-orange-500/10 text-orange-400 border-orange-500/20",
  Shopping: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  Transportation: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  Entertainment: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  "Bills & Utilities": "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  Travel: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  Health: "bg-red-500/10 text-red-400 border-red-500/20",
  Groceries: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Gas: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  Subscriptions: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
  Income: "bg-jade-500/10 text-jade-400 border-jade-500/20",
  Transfer: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  Other: "bg-gray-500/10 text-gray-400 border-gray-500/20",
};

const sourceLabels: Record<string, string> = {
  chase_credit: "Chase",
  amex: "Amex",
  coinbase: "Coinbase",
};

const sourceColors: Record<string, string> = {
  chase_credit: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  amex: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  coinbase: "bg-purple-500/10 text-purple-400 border-purple-500/20",
};

export function TransactionTable({
  transactions,
  compact = false,
}: TransactionTableProps) {
  const { isHidden, formatAmount } = usePrivacy();

  if (transactions.length === 0) {
    return (
      <div className="text-center py-12 text-midnight-400">
        No transactions to display
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="transaction-table w-full">
        <thead>
          <tr className="border-b border-midnight-800">
            <th className="pb-4 pr-4 text-xs font-medium text-midnight-400 uppercase tracking-wider">
              Date
            </th>
            <th className="pb-4 pr-4 text-xs font-medium text-midnight-400 uppercase tracking-wider">
              Description
            </th>
            {!compact && (
              <th className="pb-4 pr-4 text-xs font-medium text-midnight-400 uppercase tracking-wider">
                Category
              </th>
            )}
            <th className="pb-4 text-right text-xs font-medium text-midnight-400 uppercase tracking-wider">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((txn, index) => (
            <tr
              key={txn.id}
              className="border-b border-midnight-800/50 hover:bg-jade-500/[0.02] transition-colors"
              style={{ animationDelay: `${index * 20}ms` }}
            >
              <td className="py-4 pr-4 text-sm text-midnight-300 whitespace-nowrap font-mono">
                {formatDate(txn.date)}
              </td>
              <td className="py-4 pr-4">
                <p className="text-cream-100 truncate max-w-[280px]">
                  {txn.description}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  {/* Source badge */}
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs ${
                      sourceColors[txn.source] ||
                      "bg-midnight-800 text-midnight-400 border-midnight-700"
                    }`}
                  >
                    <CreditCard className="w-3 h-3" />
                    {sourceLabels[txn.source] || txn.source}
                  </span>
                  {/* Category badge (compact mode) */}
                  {compact && txn.category && (
                    <span
                      className={`inline-block px-2 py-0.5 rounded-md border text-xs ${
                        categoryColors[txn.category] ||
                        categoryColors.Other
                      }`}
                    >
                      {txn.category}
                    </span>
                  )}
                </div>
              </td>
              {!compact && (
                <td className="py-4 pr-4">
                  {txn.category && (
                    <span
                      className={`px-2.5 py-1 rounded-lg border text-xs font-medium ${
                        categoryColors[txn.category] ||
                        categoryColors.Other
                      }`}
                    >
                      {txn.category}
                    </span>
                  )}
                </td>
              )}
              <td className="py-4 text-right whitespace-nowrap">
                <span
                  className={clsx(
                    "inline-flex items-center gap-1.5 font-mono font-medium",
                    isHidden
                      ? "text-midnight-400"
                      : txn.amount < 0
                        ? "text-red-400"
                        : "text-jade-400"
                  )}
                >
                  {!isHidden &&
                    (txn.amount < 0 ? (
                      <ArrowDownRight className="w-4 h-4" />
                    ) : (
                      <ArrowUpRight className="w-4 h-4" />
                    ))}
                  {formatAmount(txn.amount)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
