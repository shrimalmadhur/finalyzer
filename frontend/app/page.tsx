"use client";

import { useState, useEffect } from "react";
import { UploadZone } from "@/components/UploadZone";
import { RecentUploads } from "@/components/RecentUploads";
import { StatsOverview } from "@/components/StatsOverview";
import { api, UploadedFile, HealthResponse } from "@/lib/api";
import { ArrowRight, Sparkles, Shield, Zap } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  const [uploads, setUploads] = useState<UploadedFile[]>([]);
  const [stats, setStats] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [filesRes, healthRes] = await Promise.all([
        api.getUploadedFiles(),
        api.healthCheck(),
      ]);
      setUploads(filesRes.files);
      setStats(healthRes);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUploadComplete = () => {
    loadData();
  };

  return (
    <div className="space-y-16">
      {/* Hero Section */}
      <section className="relative pt-8 pb-4">
        {/* Decorative elements */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-16 bg-gradient-to-b from-transparent via-jade-500/30 to-jade-500/10" />

        <div className="text-center space-y-6 animate-fade-up fill-both">
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-jade-500/10 border border-jade-500/20">
            <Sparkles className="w-4 h-4 text-jade-400" />
            <span className="text-sm font-medium text-jade-300">
              AI-Powered Finance Analysis
            </span>
          </div>

          {/* Main headline */}
          <h1 className="font-display text-display-lg md:text-display-xl tracking-tight">
            <span className="text-cream-100">Your finances,</span>
            <br />
            <span className="gradient-text">understood.</span>
          </h1>

          {/* Subheadline */}
          <p className="text-lg md:text-xl text-midnight-300 max-w-2xl mx-auto leading-relaxed">
            Upload your bank statements and let AI categorize your transactions.
            Ask questions in{" "}
            <span className="text-cream-200">plain English</span> to understand
            your spending.
          </p>

          {/* CTA buttons */}
          {stats && stats.transaction_count > 0 && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4 animate-fade-up fill-both delay-200">
              <Link href="/chat" className="btn-primary flex items-center gap-2">
                <span>Ask about your finances</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/dashboard" className="btn-secondary">
                View Dashboard
              </Link>
            </div>
          )}
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-3 mt-12 animate-fade-up fill-both delay-300">
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-ink-light border border-white/[0.04]">
            <Shield className="w-4 h-4 text-jade-400" />
            <span className="text-sm text-midnight-200">100% Private</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-ink-light border border-white/[0.04]">
            <Zap className="w-4 h-4 text-jade-400" />
            <span className="text-sm text-midnight-200">Instant Analysis</span>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-ink-light border border-white/[0.04]">
            <Sparkles className="w-4 h-4 text-jade-400" />
            <span className="text-sm text-midnight-200">
              Smart Categorization
            </span>
          </div>
        </div>
      </section>

      {/* Stats Overview */}
      {stats && stats.transaction_count > 0 && (
        <section className="animate-fade-up fill-both delay-400">
          <StatsOverview transactionCount={stats.transaction_count} />
        </section>
      )}

      {/* Upload Zone */}
      <section className="animate-fade-up fill-both delay-500">
        <div className="glass-card rounded-3xl p-8 md:p-10">
          {/* Section header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-jade-500/10 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-jade-400" />
            </div>
            <div>
              <h2 className="font-display text-xl font-semibold text-cream-100">
                Upload Statements
              </h2>
              <p className="text-sm text-midnight-400">
                Drop your files to begin analysis
              </p>
            </div>
          </div>

          <UploadZone onUploadComplete={handleUploadComplete} />

          {/* Supported formats */}
          <div className="mt-6 space-y-3">
            <p className="text-sm text-midnight-400">Supported formats:</p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="tag">Chase PDF</span>
              <span className="tag">Chase CSV</span>
              <span className="tag">Chase Report PDF</span>
              <span className="tag">Amex CSV</span>
              <span className="tag">Amex Year-End PDF</span>
              <span className="tag">Coinbase CSV</span>
              <span className="tag">Coinbase PDF</span>
            </div>
          </div>
        </div>
      </section>

      {/* Recent Uploads */}
      {!loading && uploads.length > 0 && (
        <section className="animate-fade-up fill-both delay-600">
          <div className="glass-card rounded-3xl p-8 md:p-10">
            {/* Section header */}
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="w-2 h-8 rounded-full bg-gradient-to-b from-jade-400 to-jade-600" />
                <div>
                  <h2 className="font-display text-xl font-semibold text-cream-100">
                    Recent Uploads
                  </h2>
                  <p className="text-sm text-midnight-400">
                    {uploads.length} file{uploads.length !== 1 ? "s" : ""}{" "}
                    processed
                  </p>
                </div>
              </div>

              <Link
                href="/dashboard"
                className="text-sm font-medium text-jade-400 hover:text-jade-300 transition-colors flex items-center gap-1 group"
              >
                <span>View all</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>

            <RecentUploads uploads={uploads} />
          </div>
        </section>
      )}

      {/* Empty State */}
      {!loading && uploads.length === 0 && (
        <section className="text-center py-16 animate-fade-up fill-both delay-600">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-ink-light border border-white/[0.04] flex items-center justify-center">
              <Sparkles className="w-8 h-8 text-midnight-500" />
            </div>
            <h3 className="font-display text-xl font-semibold text-cream-200">
              No statements yet
            </h3>
            <p className="text-midnight-400">
              Drop a file above to get started with your financial analysis.
              Your data stays completely private.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
