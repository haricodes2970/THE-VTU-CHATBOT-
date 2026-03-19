// src/hooks/useChat.ts — Custom React hook for chat state management

import { useState, useCallback } from "react";
import { v4 as uuidv4 } from "https://esm.sh/uuid@9";
import { chatApi } from "../api/client";
import type { ChatMessage } from "../types";

const SESSION_KEY = "vtu_session_id";

function getOrCreateSessionId(): string {
  let sid = localStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = uuidv4();
    localStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(getOrCreateSessionId);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      const userMessage: ChatMessage = {
        id: uuidv4(),
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await chatApi.sendMessage(text, sessionId);

        // Persist session ID from response
        if (response.session_id && response.session_id !== sessionId) {
          setSessionId(response.session_id);
          localStorage.setItem(SESSION_KEY, response.session_id);
        }

        const assistantMessage: ChatMessage = {
          id: uuidv4(),
          role: "assistant",
          content: response.answer,
          timestamp: new Date().toISOString(),
          sources: response.sources,
          intent: response.intent,
          confidence: response.confidence,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err: unknown) {
        const msg =
          (err as { userMessage?: string }).userMessage ??
          "Something went wrong. Please try again.";
        setError(msg);

        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: "assistant",
            content: `Sorry, I encountered an error: ${msg}`,
            timestamp: new Date().toISOString(),
            confidence: "LOW",
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const clearChat = useCallback(async () => {
    try {
      await chatApi.clearSession(sessionId);
    } catch {
      // Ignore errors on clear
    }
    const newSid = uuidv4();
    setSessionId(newSid);
    localStorage.setItem(SESSION_KEY, newSid);
    setMessages([]);
    setError(null);
  }, [sessionId]);

  return { messages, isLoading, sessionId, error, sendMessage, clearChat };
}
