// src/api/client.ts — Axios instance and API helper functions

import axios from "axios";
import type { ChatApiResponse, CircularListResponse, ScheduleListResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor — add correlation ID
api.interceptors.request.use((config) => {
  config.headers["X-Request-ID"] = crypto.randomUUID();
  return config;
});

// Response interceptor — normalise errors
api.interceptors.response.use(
  (res) => res,
  (error) => {
    const message =
      error.response?.data?.message ??
      error.response?.data?.detail ??
      error.message ??
      "Unknown error";
    error.userMessage = message;
    return Promise.reject(error);
  }
);

// ── Chat API ──────────────────────────────────────────────────────────────────

export const chatApi = {
  sendMessage: async (
    message: string,
    sessionId?: string
  ): Promise<ChatApiResponse> => {
    const { data } = await api.post<ChatApiResponse>("/chat", {
      message,
      session_id: sessionId ?? null,
    });
    return data;
  },

  getHistory: async (
    sessionId: string
  ): Promise<{ session_id: string; messages: unknown[] }> => {
    const { data } = await api.get(`/chat/history/${sessionId}`);
    return data;
  },

  clearSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/chat/session/${sessionId}`);
  },
};

// ── Circulars API ─────────────────────────────────────────────────────────────

export const circularApi = {
  getAll: async (
    page = 1,
    limit = 10,
    search?: string
  ): Promise<CircularListResponse> => {
    const params: Record<string, unknown> = { page, limit };
    if (search) params.search = search;
    const { data } = await api.get<CircularListResponse>("/circulars", { params });
    return data;
  },

  getById: async (id: number) => {
    const { data } = await api.get(`/circulars/${id}`);
    return data;
  },
};

// ── Schedule API ──────────────────────────────────────────────────────────────

export const scheduleApi = {
  getSchedule: async (params: {
    semester?: number;
    branch?: string;
    subject?: string;
  }): Promise<ScheduleListResponse> => {
    const { data } = await api.get<ScheduleListResponse>("/exam-schedule", {
      params,
    });
    return data;
  },

  getUpcoming: async (days = 7): Promise<ScheduleListResponse> => {
    const { data } = await api.get<ScheduleListResponse>(
      "/exam-schedule/upcoming",
      { params: { days } }
    );
    return data;
  },
};

// ── Subscribe API ─────────────────────────────────────────────────────────────

export const subscribeApi = {
  subscribe: async (payload: {
    email: string;
    name: string;
    semester?: number;
    branch?: string;
    channels: string[];
  }) => {
    const { data } = await api.post("/subscribe", payload);
    return data;
  },
};
