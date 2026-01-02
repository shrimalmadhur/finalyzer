"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  MessageSquare,
  Bot,
  User,
} from "lucide-react";
import { api, Transaction } from "@/lib/api";
import { TransactionTable } from "@/components/TransactionTable";
import clsx from "clsx";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  transactions?: Transaction[];
  totalAmount?: number | null;
  isLoading?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input.trim(),
    };

    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: "assistant",
      content: "",
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await api.query(userMessage.content);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingMessage.id
            ? {
                ...msg,
                content: response.summary,
                transactions: response.transactions,
                totalAmount: response.total_amount,
                isLoading: false,
              }
            : msg
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingMessage.id
            ? {
                ...msg,
                content:
                  error instanceof Error
                    ? `Sorry, I encountered an error: ${error.message}`
                    : "Sorry, something went wrong. Please try again.",
                isLoading: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const suggestedQueries = [
    "How much did I spend on food this month?",
    "What are my biggest expenses?",
    "Show me my Amazon purchases",
    "What subscriptions am I paying for?",
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Chat Header */}
      <div className="text-center pb-6 border-b border-midnight-800/50 animate-fade-down fill-both">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-jade-500/10 border border-jade-500/20 mb-4">
          <Sparkles className="w-4 h-4 text-jade-400" />
          <span className="text-sm font-medium text-jade-300">AI Assistant</span>
        </div>
        <h1 className="font-display text-display-sm md:text-display-md tracking-tight">
          <span className="text-cream-100">Ask about your</span>{" "}
          <span className="gradient-text">finances</span>
        </h1>
        <p className="text-midnight-400 mt-2">
          Use natural language to explore your transactions
        </p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto py-8 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center animate-fade-up fill-both">
            <div className="relative mb-6">
              <div className="w-20 h-20 rounded-2xl bg-ink-lighter flex items-center justify-center">
                <MessageSquare className="w-10 h-10 text-midnight-500" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-xl bg-jade-500/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-jade-400" />
              </div>
            </div>

            <h2 className="font-display text-xl font-semibold text-cream-200 mb-2">
              Start a conversation
            </h2>
            <p className="text-midnight-400 max-w-md mb-8">
              Ask me anything about your transactions. I can help you understand
              your spending patterns, find specific purchases, and more.
            </p>

            {/* Suggested queries */}
            <div className="flex flex-wrap justify-center gap-2 max-w-2xl">
              {suggestedQueries.map((query) => (
                <button
                  key={query}
                  onClick={() => setInput(query)}
                  className="px-4 py-2.5 rounded-xl bg-ink-lighter border border-white/[0.04] text-sm text-midnight-300 hover:text-cream-100 hover:border-jade-500/20 hover:bg-ink-lighter/80 transition-all duration-200"
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLast={index === messages.length - 1}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-midnight-800/50 pt-6 animate-fade-up fill-both">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your finances..."
              disabled={isLoading}
              className="input-field pr-12"
            />
            {/* Animated border on focus */}
            <div className="absolute inset-0 rounded-xl pointer-events-none">
              <div className="absolute inset-0 rounded-xl border-2 border-jade-500/0 transition-colors focus-within:border-jade-500/30" />
            </div>
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={clsx(
              "w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300",
              input.trim() && !isLoading
                ? "bg-gradient-to-br from-jade-400 to-jade-600 text-ink shadow-glow hover:shadow-glow-lg"
                : "bg-ink-lighter text-midnight-500 cursor-not-allowed"
            )}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  isLast,
}: {
  message: Message;
  isLast: boolean;
}) {
  const [showTransactions, setShowTransactions] = useState(false);

  if (message.type === "user") {
    return (
      <div className="flex justify-end animate-fade-up fill-both">
        <div className="flex items-start gap-3 max-w-[80%]">
          <div className="px-5 py-3 rounded-2xl rounded-br-lg bg-gradient-to-br from-jade-500 to-jade-600 text-ink shadow-glow">
            <p className="font-medium">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-lg bg-jade-500/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-jade-400" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start animate-fade-up fill-both">
      <div className="flex items-start gap-3 max-w-[85%]">
        <div className="w-8 h-8 rounded-lg bg-ink-lighter flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-jade-400" />
        </div>

        <div className="space-y-3">
          <div className="px-5 py-3 rounded-2xl rounded-bl-lg bg-ink-lighter border border-white/[0.04]">
            {message.isLoading ? (
              <div className="flex items-center gap-3 text-midnight-400">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-jade-500 animate-bounce" />
                  <span
                    className="w-2 h-2 rounded-full bg-jade-500 animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  />
                  <span
                    className="w-2 h-2 rounded-full bg-jade-500 animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  />
                </div>
                <span>Analyzing your transactions...</span>
              </div>
            ) : (
              <p className="whitespace-pre-wrap text-cream-100">
                {message.content}
              </p>
            )}
          </div>

          {/* Total amount badge */}
          {message.totalAmount !== undefined && message.totalAmount !== null && (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-ink-lighter/50 border border-white/[0.04]">
              <span className="text-sm text-midnight-400">Total:</span>
              <span
                className={clsx(
                  "font-mono font-semibold",
                  message.totalAmount < 0 ? "text-red-400" : "text-jade-400"
                )}
              >
                ${Math.abs(message.totalAmount).toFixed(2)}
              </span>
            </div>
          )}

          {/* Transactions toggle */}
          {message.transactions && message.transactions.length > 0 && (
            <div className="space-y-3">
              <button
                onClick={() => setShowTransactions(!showTransactions)}
                className="flex items-center gap-2 text-sm text-jade-400 hover:text-jade-300 transition-colors"
              >
                {showTransactions ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
                {showTransactions ? "Hide" : "Show"}{" "}
                {message.transactions.length} transactions
              </button>

              {showTransactions && (
                <div className="glass-card rounded-xl p-4 animate-scale-in fill-both">
                  <TransactionTable transactions={message.transactions} compact />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
