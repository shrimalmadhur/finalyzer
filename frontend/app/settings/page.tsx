"use client";

import { useState, useEffect } from "react";
import {
  Settings as SettingsIcon,
  Check,
  Loader2,
  Server,
  Key,
  Sparkles,
  Shield,
  Zap,
} from "lucide-react";
import { api, Settings } from "@/lib/api";
import clsx from "clsx";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Form state
  const [provider, setProvider] = useState<"ollama" | "openai">("ollama");
  const [ollamaHost, setOllamaHost] = useState("http://localhost:11434");
  const [openaiKey, setOpenaiKey] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await api.getSettings();
      setSettings(data);
      setProvider(data.llm_provider as "ollama" | "openai");
      setOllamaHost(data.ollama_host);
    } catch (error) {
      console.error("Failed to load settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      await api.updateSettings({
        llm_provider: provider,
        ollama_host: ollamaHost,
        openai_api_key: openaiKey || undefined,
      });
      setMessage({ type: "success", text: "Settings saved successfully!" });
      setOpenaiKey("");
      loadSettings();
    } catch (error) {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to save settings",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-jade-500/10 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-jade-400 animate-spin" />
          </div>
          <div className="absolute inset-0 w-16 h-16 rounded-2xl bg-jade-500/20 blur-xl animate-pulse" />
        </div>
        <p className="text-midnight-400">Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-10">
      {/* Header */}
      <div className="text-center animate-fade-up fill-both">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-jade-500/10 border border-jade-500/20 mb-4">
          <SettingsIcon className="w-4 h-4 text-jade-400" />
          <span className="text-sm font-medium text-jade-300">Configuration</span>
        </div>
        <h1 className="font-display text-display-sm md:text-display-md tracking-tight">
          <span className="gradient-text">Settings</span>
        </h1>
        <p className="text-midnight-400 mt-2">
          Configure your LLM provider and preferences
        </p>
      </div>

      {/* Settings Form */}
      <div className="glass-card rounded-3xl p-8 space-y-8 animate-fade-up fill-both delay-200">
        {/* LLM Provider Selection */}
        <div className="space-y-4">
          <label className="flex items-center gap-2 text-lg font-display font-semibold text-cream-100">
            <Sparkles className="w-5 h-5 text-jade-400" />
            LLM Provider
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Ollama Option */}
            <button
              onClick={() => setProvider("ollama")}
              className={clsx(
                "relative p-5 rounded-2xl text-left transition-all duration-300 group",
                provider === "ollama"
                  ? "bg-jade-500/10 border-2 border-jade-500/50"
                  : "bg-ink-lighter border-2 border-white/[0.04] hover:border-jade-500/20"
              )}
            >
              {provider === "ollama" && (
                <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-jade-500 flex items-center justify-center">
                  <Check className="w-4 h-4 text-ink" />
                </div>
              )}

              <div className="flex items-center gap-3 mb-3">
                <div
                  className={clsx(
                    "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
                    provider === "ollama" ? "bg-jade-500/20" : "bg-ink-light"
                  )}
                >
                  <Server
                    className={clsx(
                      "w-5 h-5",
                      provider === "ollama"
                        ? "text-jade-400"
                        : "text-midnight-400"
                    )}
                  />
                </div>
                <span
                  className={clsx(
                    "font-semibold",
                    provider === "ollama" ? "text-cream-100" : "text-midnight-200"
                  )}
                >
                  Ollama
                </span>
              </div>

              <p
                className={clsx(
                  "text-sm",
                  provider === "ollama" ? "text-midnight-300" : "text-midnight-400"
                )}
              >
                Run locally, fully private. No data leaves your machine.
              </p>

              <div className="flex items-center gap-2 mt-3">
                <Shield className="w-3.5 h-3.5 text-jade-500" />
                <span className="text-xs text-jade-400">100% Private</span>
              </div>
            </button>

            {/* OpenAI Option */}
            <button
              onClick={() => setProvider("openai")}
              className={clsx(
                "relative p-5 rounded-2xl text-left transition-all duration-300 group",
                provider === "openai"
                  ? "bg-jade-500/10 border-2 border-jade-500/50"
                  : "bg-ink-lighter border-2 border-white/[0.04] hover:border-jade-500/20"
              )}
            >
              {provider === "openai" && (
                <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-jade-500 flex items-center justify-center">
                  <Check className="w-4 h-4 text-ink" />
                </div>
              )}

              <div className="flex items-center gap-3 mb-3">
                <div
                  className={clsx(
                    "w-10 h-10 rounded-xl flex items-center justify-center transition-colors",
                    provider === "openai" ? "bg-jade-500/20" : "bg-ink-light"
                  )}
                >
                  <Key
                    className={clsx(
                      "w-5 h-5",
                      provider === "openai"
                        ? "text-jade-400"
                        : "text-midnight-400"
                    )}
                  />
                </div>
                <span
                  className={clsx(
                    "font-semibold",
                    provider === "openai" ? "text-cream-100" : "text-midnight-200"
                  )}
                >
                  OpenAI
                </span>
              </div>

              <p
                className={clsx(
                  "text-sm",
                  provider === "openai" ? "text-midnight-300" : "text-midnight-400"
                )}
              >
                Better accuracy. Requires API key.
              </p>

              <div className="flex items-center gap-2 mt-3">
                <Zap className="w-3.5 h-3.5 text-amber-500" />
                <span className="text-xs text-amber-400">Higher Accuracy</span>
              </div>
            </button>
          </div>
        </div>

        {/* Provider-specific settings */}
        {provider === "ollama" && (
          <div className="space-y-3 animate-fade-up fill-both">
            <label className="block text-sm font-medium text-midnight-300">
              Ollama Host URL
            </label>
            <input
              type="text"
              value={ollamaHost}
              onChange={(e) => setOllamaHost(e.target.value)}
              placeholder="http://localhost:11434"
              className="input-field"
            />
            <p className="text-xs text-midnight-500">
              Make sure Ollama is running with the{" "}
              <code className="text-jade-400 bg-ink-lighter px-1.5 py-0.5 rounded">
                llama3.2
              </code>{" "}
              and{" "}
              <code className="text-jade-400 bg-ink-lighter px-1.5 py-0.5 rounded">
                nomic-embed-text
              </code>{" "}
              models installed.
            </p>
          </div>
        )}

        {provider === "openai" && (
          <div className="space-y-3 animate-fade-up fill-both">
            <label className="block text-sm font-medium text-midnight-300">
              OpenAI API Key
            </label>
            <input
              type="password"
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              placeholder={settings?.has_openai_key ? "••••••••••••••••" : "sk-..."}
              className="input-field font-mono"
            />
            {settings?.has_openai_key && (
              <div className="flex items-center gap-2 text-jade-400">
                <Check className="w-4 h-4" />
                <span className="text-xs">API key is configured</span>
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        <div className="divider" />

        {/* Message */}
        {message && (
          <div
            className={clsx(
              "flex items-center gap-3 px-4 py-3 rounded-xl text-sm animate-scale-in fill-both",
              message.type === "success"
                ? "bg-jade-500/10 text-jade-300 border border-jade-500/20"
                : "bg-red-500/10 text-red-300 border border-red-500/20"
            )}
          >
            {message.type === "success" ? (
              <Check className="w-5 h-5 flex-shrink-0" />
            ) : (
              <span className="w-5 h-5 flex-shrink-0 text-center">!</span>
            )}
            {message.text}
          </div>
        )}

        {/* Save Button */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="w-5 h-5" />
              Save Settings
            </>
          )}
        </button>
      </div>

      {/* Info Footer */}
      <div className="text-center text-sm text-midnight-500 animate-fade-up fill-both delay-300">
        <p>
          Settings are stored in memory and will reset when the server restarts.
        </p>
        <p className="mt-1">
          For persistent settings, edit the{" "}
          <code className="text-jade-400 bg-ink-lighter px-1.5 py-0.5 rounded">
            .env
          </code>{" "}
          file.
        </p>
      </div>
    </div>
  );
}
