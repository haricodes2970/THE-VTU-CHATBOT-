// src/types/index.ts — TypeScript interfaces for the VTU Smart Scheduler

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: SourceItem[];
  intent?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
}

export interface SourceItem {
  title: string;
  url: string;
  score: number;
}

export interface ChatSession {
  session_id: string;
  messages: ChatMessage[];
  created_at: string;
}

export interface Circular {
  id: number;
  title: string;
  url: string;
  circular_date: string | null;
  is_processed: boolean;
  is_indexed: boolean;
  scraped_at: string;
  content?: string;
}

export interface ExamSchedule {
  id: number;
  subject: string;
  subject_code: string | null;
  semester: number | null;
  exam_date: string | null;
  exam_time: string | null;
  branch: string | null;
  academic_year: string | null;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}

export interface ChatApiResponse {
  answer: string;
  intent: string;
  entities: Record<string, unknown>;
  sources: SourceItem[];
  session_id: string;
  response_time_ms: number;
  confidence: "HIGH" | "MEDIUM" | "LOW";
}

export interface CircularListResponse {
  circulars: Circular[];
  total: number;
  page: number;
  limit: number;
}

export interface ScheduleListResponse {
  schedules: ExamSchedule[];
  total: number;
}
