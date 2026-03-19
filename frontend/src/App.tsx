// src/App.tsx — Root app component with routing

import React, { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { CircularsPage } from "./pages/CircularsPage";
import { SchedulePage } from "./pages/SchedulePage";
import { SubscribePage } from "./pages/SubscribePage";

export default function App() {
  const [showSubscribe, setShowSubscribe] = useState(false);

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 dark:bg-gray-950 overflow-hidden">
        <Sidebar onSubscribeClick={() => setShowSubscribe(true)} />

        {/* Main content */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<ChatWindow />} />
            <Route path="/circulars" element={
              <div className="h-full overflow-y-auto">
                <CircularsPage />
              </div>
            } />
            <Route path="/schedule" element={
              <div className="h-full overflow-y-auto">
                <SchedulePage />
              </div>
            } />
          </Routes>
        </main>

        {/* Subscribe modal */}
        {showSubscribe && (
          <SubscribePage onClose={() => setShowSubscribe(false)} />
        )}
      </div>
    </BrowserRouter>
  );
}
