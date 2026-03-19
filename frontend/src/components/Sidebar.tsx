// src/components/Sidebar.tsx — Navigation sidebar

import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", label: "Chat", icon: "💬" },
  { path: "/circulars", label: "Circulars", icon: "📋" },
  { path: "/schedule", label: "Exam Schedule", icon: "📅" },
];

interface Props {
  onSubscribeClick: () => void;
}

export function Sidebar({ onSubscribeClick }: Props) {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(true);

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="md:hidden fixed top-4 left-4 z-50 bg-blue-600 text-white rounded-lg p-2 shadow-lg"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Toggle sidebar"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Sidebar */}
      <aside
        className={`${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } fixed md:static inset-y-0 left-0 z-40 w-64 bg-white dark:bg-gray-900
          border-r border-gray-200 dark:border-gray-700 flex flex-col
          transition-transform duration-200 ease-in-out`}
      >
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-200 dark:border-gray-700">
          <h1 className="text-lg font-bold text-blue-600 dark:text-blue-400">
            🎓 VTU Smart Scheduler
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">AI-powered exam assistant</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-1">
          {NAV_ITEMS.map(({ path, label, icon }) => (
            <Link
              key={path}
              to={path}
              onClick={() => setIsOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                location.pathname === path
                  ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                  : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>

        {/* Subscribe button */}
        <div className="px-4 pb-4">
          <button
            onClick={onSubscribeClick}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium
                       py-2.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            🔔 Subscribe to Alerts
          </button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/50"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
}
