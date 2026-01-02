"use client";

import { useEffect, useState } from "react";
import { FileText, Calendar, Hash, Loader2, Sparkles } from "lucide-react";
import { UploadedFile, ProcessingJob, api } from "@/lib/api";

interface RecentUploadsProps {
  uploads: UploadedFile[];
}

const sourceLabels: Record<string, string> = {
  chase_credit: "Chase Credit",
  amex: "American Express",
  coinbase: "Coinbase Card",
};

const sourceColors: Record<string, string> = {
  chase_credit: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  amex: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  coinbase: "bg-purple-500/10 text-purple-400 border-purple-500/20",
};

export function RecentUploads({ uploads }: RecentUploadsProps) {
  const [processingJobs, setProcessingJobs] = useState<ProcessingJob[]>([]);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    const checkStatus = async () => {
      try {
        const status = await api.getProcessingStatus();
        setProcessingJobs(status.jobs);

        if (!status.has_active && interval) {
          clearInterval(interval);
          interval = null;
        }
      } catch (error) {
        console.error("Failed to get processing status:", error);
      }
    };

    checkStatus();
    interval = setInterval(checkStatus, 2000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [uploads]);

  const getProcessingJob = (fileHash: string): ProcessingJob | undefined => {
    return processingJobs.find(
      (job) => job.file_hash === fileHash && job.status === "processing"
    );
  };

  return (
    <div className="space-y-3">
      {uploads.map((file, index) => {
        const processingJob = getProcessingJob(file.file_hash);
        const isProcessing = !!processingJob;

        return (
          <div
            key={file.id}
            className={`group relative rounded-xl transition-all duration-300 ${
              isProcessing
                ? "bg-jade-500/5 border border-jade-500/20"
                : "bg-ink-lighter/30 border border-white/[0.03] hover:border-jade-500/10 hover:bg-ink-lighter/50"
            }`}
            style={{
              animationDelay: `${index * 50}ms`,
            }}
          >
            <div className="flex items-center gap-4 p-4">
              {/* Icon */}
              <div
                className={`relative w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                  isProcessing ? "bg-jade-500/10" : "bg-ink-lighter/50"
                }`}
              >
                {isProcessing ? (
                  <Loader2 className="w-6 h-6 text-jade-400 animate-spin" />
                ) : (
                  <FileText className="w-6 h-6 text-midnight-400 group-hover:text-midnight-300 transition-colors" />
                )}
              </div>

              {/* File info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-cream-100 truncate">
                  {file.filename}
                </p>
                <div className="flex items-center gap-4 mt-1.5 text-sm text-midnight-400">
                  <span className="flex items-center gap-1.5">
                    <Hash className="w-3.5 h-3.5" />
                    {file.transaction_count} transactions
                  </span>
                  {isProcessing && processingJob ? (
                    <span className="flex items-center gap-1.5 text-jade-400">
                      <Sparkles className="w-3.5 h-3.5" />
                      Categorizing {processingJob.processed}/{processingJob.total}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      {formatDate(file.uploaded_at)}
                    </span>
                  )}
                </div>

                {/* Progress bar for processing */}
                {isProcessing && processingJob && (
                  <div className="mt-3 h-1.5 bg-ink-lighter rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-jade-500 to-jade-400 rounded-full transition-all duration-500 ease-out-expo"
                      style={{
                        width: `${Math.round(
                          (processingJob.processed / processingJob.total) * 100
                        )}%`,
                      }}
                    />
                  </div>
                )}
              </div>

              {/* Source badge */}
              <span
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
                  sourceColors[file.source] ||
                  "bg-midnight-800 text-midnight-300 border-midnight-700"
                }`}
              >
                {sourceLabels[file.source] || file.source}
              </span>
            </div>

            {/* Subtle shine effect on hover */}
            <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}
