// src/pages/SchedulePage.tsx — Exam schedule with filters

import React, { useState, useEffect, useCallback } from "react";
import { scheduleApi } from "../api/client";
import type { ExamSchedule } from "../types";

const BRANCHES = ["CSE", "ECE", "ISE", "MECH", "CIVIL", "EEE", "BIOTECH"];

function isUpcoming(dateStr: string | null): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const now = new Date();
  const sevenDaysLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  return d >= now && d <= sevenDaysLater;
}

export function SchedulePage() {
  const [schedules, setSchedules] = useState<ExamSchedule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [semester, setSemester] = useState<string>("");
  const [branch, setBranch] = useState<string>("");
  const [subject, setSubject] = useState<string>("");

  const fetchSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await scheduleApi.getSchedule({
        semester: semester ? Number(semester) : undefined,
        branch: branch || undefined,
        subject: subject || undefined,
      });
      setSchedules(data.schedules);
    } catch {
      setError("Failed to load exam schedule.");
    } finally {
      setLoading(false);
    }
  }, [semester, branch, subject]);

  useEffect(() => { fetchSchedule(); }, [fetchSchedule]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-6">Exam Schedule</h2>

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <select
          value={semester}
          onChange={(e) => setSemester(e.target.value)}
          className="rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Semesters</option>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
            <option key={s} value={s}>Semester {s}</option>
          ))}
        </select>

        <select
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          className="rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Branches</option>
          {BRANCHES.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Search subject..."
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4">
          {error}
          <button onClick={fetchSchedule} className="ml-2 underline text-sm">Retry</button>
        </div>
      )}

      {loading && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-14 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {!loading && schedules.length === 0 && (
        <p className="text-gray-500 text-center py-8">No exams found. Try changing filters.</p>
      )}

      {!loading && schedules.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800">
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">Subject</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">Code</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">Sem</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">Date</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 font-medium border-b border-gray-200 dark:border-gray-700">Time</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr
                  key={s.id}
                  className={`border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 ${
                    isUpcoming(s.exam_date) ? "bg-amber-50/50 dark:bg-amber-900/10" : ""
                  }`}
                >
                  <td className="px-4 py-3 text-gray-800 dark:text-gray-200 font-medium">
                    {s.subject}
                    {isUpcoming(s.exam_date) && (
                      <span className="ml-2 text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">Soon</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{s.subject_code ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{s.semester ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                    {s.exam_date ? new Date(s.exam_date).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{s.exam_time ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
