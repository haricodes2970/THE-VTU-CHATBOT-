// src/pages/CircularsPage.tsx — Browse VTU circulars

import React, { useState, useEffect, useCallback } from "react";
import { circularApi } from "../api/client";
import type { Circular } from "../types";

export function CircularsPage() {
  const [circulars, setCirculars] = useState<Circular[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const LIMIT = 10;

  const fetchCirculars = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await circularApi.getAll(page, LIMIT, search || undefined);
      setCirculars(data.circulars);
      setTotal(data.total);
    } catch {
      setError("Failed to load circulars. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => { fetchCirculars(); }, [fetchCirculars]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-6">VTU Circulars</h2>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="Search circulars..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2
                     text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100
                     focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
        >
          Search
        </button>
        {search && (
          <button
            type="button"
            onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
            className="px-3 py-2 text-sm text-gray-500 hover:text-red-500"
          >
            ✕
          </button>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4 flex justify-between">
          <span>{error}</span>
          <button onClick={fetchCirculars} className="text-sm underline">Retry</button>
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {/* Circular list */}
      {!loading && (
        <div className="space-y-3">
          {circulars.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No circulars found.</p>
          ) : (
            circulars.map((c) => (
              <a
                key={c.id}
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
                           rounded-lg px-4 py-3 hover:border-blue-400 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                      {c.title}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {c.circular_date ? new Date(c.circular_date).toLocaleDateString() : "No date"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {c.is_indexed && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        AI-indexed
                      </span>
                    )}
                    <span className="text-xs text-blue-500">PDF ↗</span>
                  </div>
                </div>
              </a>
            ))
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && !loading && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 rounded border text-sm disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            ← Prev
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 rounded border text-sm disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
