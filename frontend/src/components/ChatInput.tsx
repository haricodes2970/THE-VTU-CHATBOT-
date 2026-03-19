// src/components/ChatInput.tsx — Message input with suggestion chips

import React, { useState, useRef, useCallback } from "react";

interface Props {
  onSend: (message: string) => void;
  isLoading: boolean;
}

const SUGGESTIONS = [
  "When is my DBMS exam?",
  "5th sem exam schedule",
  "Latest circulars",
  "3rd semester timetable",
];

const MAX_CHARS = 500;

export function ChatInput({ onSend, isLoading }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isLoading, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    if (val.length > MAX_CHARS) return;
    setText(val);
    // Auto-grow textarea (max 4 lines ≈ 96px)
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 96) + "px";
  };

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4">
      {/* Suggestion chips */}
      <div className="flex gap-2 mb-3 flex-wrap">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => !isLoading && onSend(s)}
            disabled={isLoading}
            className="text-xs px-3 py-1 rounded-full border border-blue-300 dark:border-blue-700
                       text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30
                       disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div className="flex gap-2 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask me about VTU exams, schedules, circulars..."
            disabled={isLoading}
            rows={1}
            className="w-full resize-none rounded-xl border border-gray-300 dark:border-gray-600
                       bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100
                       px-4 py-3 pr-16 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500
                       disabled:opacity-60 disabled:cursor-not-allowed transition"
          />
          {/* Character counter */}
          <span
            className={`absolute right-3 bottom-3 text-xs ${
              text.length > MAX_CHARS * 0.9 ? "text-red-500" : "text-gray-400"
            }`}
          >
            {text.length}/{MAX_CHARS}
          </span>
        </div>

        <button
          onClick={handleSend}
          disabled={!text.trim() || isLoading}
          className="flex-shrink-0 w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-700
                     disabled:bg-blue-300 dark:disabled:bg-blue-900
                     text-white flex items-center justify-center
                     focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
          aria-label="Send message"
        >
          {isLoading ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
