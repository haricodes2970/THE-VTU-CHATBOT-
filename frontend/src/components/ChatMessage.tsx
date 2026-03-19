// src/components/ChatMessage.tsx — Individual chat bubble

import React, { useState } from "react";
import type { ChatMessage as ChatMessageType } from "../types";

interface Props {
  message: ChatMessageType;
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const [showSources, setShowSources] = useState(false);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? "order-2" : "order-1"}`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 shadow-sm ${
            isUser
              ? "bg-blue-600 text-white rounded-br-sm"
              : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
          }`}
        >
          {/* Low-confidence warning */}
          {!isUser && message.confidence === "LOW" && (
            <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-xs mb-2 bg-amber-50 dark:bg-amber-900/20 rounded px-2 py-1">
              <span>⚠️</span>
              <span>Please verify with the official VTU website.</span>
            </div>
          )}

          {/* Message content */}
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>

          {/* Sources collapsible */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-2">
              <button
                onClick={() => setShowSources(!showSources)}
                className="text-xs text-blue-500 dark:text-blue-400 hover:underline focus:outline-none"
              >
                {showSources ? "▲ Hide sources" : `▼ ${message.sources.length} source(s)`}
              </button>
              {showSources && (
                <div className="mt-1 space-y-1">
                  {message.sources.map((src, i) => (
                    <div key={i} className="text-xs text-gray-500 dark:text-gray-400 pl-2 border-l-2 border-blue-300">
                      {src.title || "VTU Circular"}
                      {src.url && (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-1 text-blue-500 hover:underline"
                        >
                          ↗
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <p className={`text-xs text-gray-400 mt-1 ${isUser ? "text-right" : "text-left"}`}>
          {formatTimestamp(message.timestamp)}
        </p>
      </div>
    </div>
  );
}
