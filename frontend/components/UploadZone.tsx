"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Loader2,
  CloudUpload,
} from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";

interface UploadZoneProps {
  onUploadComplete?: () => void;
}

interface UploadResult {
  filename: string;
  success: boolean;
  transactions_added: number;
  transactions_skipped: number;
  message: string;
}

interface UploadState {
  status: "idle" | "uploading" | "success" | "error";
  message?: string;
  results?: UploadResult[];
  currentFile?: string;
  progress?: { current: number; total: number };
}

export function UploadZone({ onUploadComplete }: UploadZoneProps) {
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const results: UploadResult[] = [];

      setUploadState({
        status: "uploading",
        message: `Uploading ${acceptedFiles.length} file(s)...`,
        progress: { current: 0, total: acceptedFiles.length },
      });

      for (let i = 0; i < acceptedFiles.length; i++) {
        const file = acceptedFiles[i];
        setUploadState((prev) => ({
          ...prev,
          currentFile: file.name,
          progress: { current: i + 1, total: acceptedFiles.length },
        }));

        try {
          const result = await api.uploadFile(file);
          results.push({
            filename: file.name,
            success: true,
            transactions_added: result.transactions_added,
            transactions_skipped: result.transactions_skipped,
            message: result.message,
          });
        } catch (error) {
          results.push({
            filename: file.name,
            success: false,
            transactions_added: 0,
            transactions_skipped: 0,
            message: error instanceof Error ? error.message : "Upload failed",
          });
        }
      }

      const totalAdded = results.reduce(
        (sum, r) => sum + r.transactions_added,
        0
      );
      const totalSkipped = results.reduce(
        (sum, r) => sum + r.transactions_skipped,
        0
      );
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.filter((r) => !r.success).length;

      const hasErrors = failCount > 0;
      const hasSuccess = successCount > 0;

      setUploadState({
        status: hasErrors && !hasSuccess ? "error" : "success",
        message:
          `Processed ${successCount}/${acceptedFiles.length} files: ${totalAdded} transactions added` +
          (totalSkipped > 0 ? `, ${totalSkipped} duplicates skipped` : "") +
          (failCount > 0 ? `, ${failCount} failed` : ""),
        results,
      });

      if (hasSuccess) {
        onUploadComplete?.();
      }

      setTimeout(() => {
        setUploadState({ status: "idle" });
      }, 8000);
    },
    [onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/csv": [".csv"],
    },
    multiple: true,
    disabled: uploadState.status === "uploading",
  });

  return (
    <div
      {...getRootProps()}
      className={clsx(
        "dropzone relative rounded-2xl p-10 md:p-14 text-center cursor-pointer transition-all duration-300",
        isDragActive && "active",
        uploadState.status === "uploading" && "opacity-75 cursor-wait",
        uploadState.status === "success" &&
          "border-jade-500/50 bg-jade-500/5 border-solid",
        uploadState.status === "error" &&
          "border-red-500/50 bg-red-500/5 border-solid"
      )}
    >
      <input {...getInputProps()} />

      <div className="flex flex-col items-center gap-5">
        {uploadState.status === "idle" && (
          <>
            <div
              className={clsx(
                "relative w-20 h-20 rounded-2xl flex items-center justify-center transition-all duration-300",
                isDragActive
                  ? "bg-jade-500/20 scale-110"
                  : "bg-ink-lighter/50"
              )}
            >
              {isDragActive ? (
                <CloudUpload className="w-10 h-10 text-jade-400 animate-pulse" />
              ) : (
                <Upload className="w-10 h-10 text-midnight-400" />
              )}

              {/* Animated ring on drag */}
              {isDragActive && (
                <div className="absolute inset-0 rounded-2xl border-2 border-jade-500/50 animate-ping" />
              )}
            </div>

            <div className="space-y-2">
              <p className="text-lg font-medium text-cream-100">
                {isDragActive
                  ? "Release to upload"
                  : "Drag & drop your statements"}
              </p>
              <p className="text-sm text-midnight-400">
                or click to browse (multiple files supported)
              </p>
            </div>
          </>
        )}

        {uploadState.status === "uploading" && (
          <>
            <div className="relative w-20 h-20 rounded-2xl bg-jade-500/10 flex items-center justify-center">
              <Loader2 className="w-10 h-10 text-jade-400 animate-spin" />

              {/* Progress ring */}
              <svg
                className="absolute inset-0 w-full h-full -rotate-90"
                viewBox="0 0 80 80"
              >
                <circle
                  cx="40"
                  cy="40"
                  r="36"
                  fill="none"
                  stroke="rgba(26, 205, 138, 0.1)"
                  strokeWidth="4"
                />
                <circle
                  cx="40"
                  cy="40"
                  r="36"
                  fill="none"
                  stroke="rgba(26, 205, 138, 0.6)"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray={`${
                    ((uploadState.progress?.current || 0) /
                      (uploadState.progress?.total || 1)) *
                    226
                  } 226`}
                  className="transition-all duration-300"
                />
              </svg>
            </div>

            <div className="space-y-2">
              <p className="text-lg font-medium text-cream-100">
                Processing {uploadState.progress?.current}/
                {uploadState.progress?.total}...
              </p>
              <p className="text-sm text-midnight-400 font-mono">
                {uploadState.currentFile}
              </p>
            </div>
          </>
        )}

        {uploadState.status === "success" && (
          <>
            <div className="w-20 h-20 rounded-2xl bg-jade-500/20 flex items-center justify-center">
              <CheckCircle className="w-10 h-10 text-jade-400" />
            </div>

            <div className="space-y-2">
              <p className="text-lg font-medium text-jade-300">
                Upload Complete
              </p>
              <p className="text-sm text-midnight-300">{uploadState.message}</p>
            </div>
          </>
        )}

        {uploadState.status === "error" && (
          <>
            <div className="w-20 h-20 rounded-2xl bg-red-500/20 flex items-center justify-center">
              <XCircle className="w-10 h-10 text-red-400" />
            </div>

            <div className="space-y-2">
              <p className="text-lg font-medium text-red-300">Upload Failed</p>
              <p className="text-sm text-midnight-300">{uploadState.message}</p>
            </div>
          </>
        )}
      </div>

      {/* File type indicators */}
      {uploadState.status === "idle" && (
        <div className="flex items-center justify-center gap-3 mt-8">
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-ink-lighter/30 border border-white/[0.04] text-sm text-midnight-300">
            <FileText className="w-4 h-4" />
            PDF
          </span>
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-ink-lighter/30 border border-white/[0.04] text-sm text-midnight-300">
            <FileText className="w-4 h-4" />
            CSV
          </span>
        </div>
      )}
    </div>
  );
}
