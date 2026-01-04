import { useEffect, useState } from "react";

export interface UploadProgress {
  status: "processing" | "complete" | "error";
  progress: number; // 0-100
  message: string;
  details?: {
    transactions_added?: number;
    transactions_skipped?: number;
  };
  timestamp: string;
}

/**
 * Get the API base URL for SSE connections.
 * Uses NEXT_PUBLIC_API_URL environment variable if set, otherwise uses relative URL
 * which will be proxied through Next.js rewrites in development.
 */
function getApiBaseUrl(): string {
  // In browser, check for env variable (must be NEXT_PUBLIC_ prefixed)
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) {
      return envUrl;
    }
  }
  // Default to relative URL (works with Next.js rewrites in dev)
  return "/api";
}

/**
 * React hook to listen to real-time upload progress via Server-Sent Events (SSE).
 *
 * @param fileHash - The hash of the uploaded file (used to track progress)
 * @param enabled - Whether to start listening (default: true)
 * @returns Current progress state
 */
export function useUploadProgress(fileHash: string | null, enabled = true) {
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fileHash || !enabled) {
      setProgress(null);
      setError(null);
      return;
    }

    let eventSource: EventSource | null = null;
    console.log(`[SSE] Connecting to progress stream for file: ${fileHash.substring(0, 8)}...`);

    try {
      // Connect to SSE endpoint using configured API URL
      const apiBase = getApiBaseUrl();
      const url = `${apiBase}/upload/progress/${fileHash}`;
      console.log(`[SSE] Connecting to: ${url}`);
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        console.log("[SSE] Connection opened");
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as UploadProgress;
          console.log(`[SSE] Progress update: ${data.progress}% - ${data.message}`);
          setProgress(data);

          // Auto-close connection when complete or error
          if (data.status === "complete" || data.status === "error") {
            console.log(`[SSE] Processing ${data.status}, closing connection`);
            eventSource?.close();
          }
        } catch (err) {
          console.error("[SSE] Failed to parse message:", err, "Raw:", event.data);
        }
      };

      eventSource.onerror = (err) => {
        console.error("[SSE] Connection error:", err);
        // Check if it's a connection close vs actual error
        if (eventSource?.readyState === EventSource.CLOSED) {
          console.log("[SSE] Connection closed by server");
          // Don't set error if connection closed normally (server finished)
          // The last progress update should have been "complete" or "error"
        } else if (eventSource?.readyState === EventSource.CONNECTING) {
          console.log("[SSE] Reconnecting...");
        } else {
          console.error("[SSE] Unexpected error, readyState:", eventSource?.readyState);
          setError("Connection to progress stream failed");
          eventSource?.close();
        }
      };
    } catch (err) {
      console.error("[SSE] Failed to create EventSource:", err);
      setError("Failed to connect to progress stream");
    }

    // Cleanup on unmount or when fileHash changes
    return () => {
      if (eventSource) {
        console.log("[SSE] Cleaning up, closing connection");
        eventSource.close();
      }
    };
  }, [fileHash, enabled]);

  return { progress, error };
}
