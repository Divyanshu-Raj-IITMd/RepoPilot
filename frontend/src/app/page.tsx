"use client";

import { useState } from "react";
import Sidebar, { TabId } from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";
import ReviewPanel from "@/components/ReviewPanel";
import TestsPanel from "@/components/TestsPanel";
import EvalPanel from "@/components/EvalPanel";
import { RepoOverview } from "@/lib/api";

export default function Home() {
  const [tab, setTab] = useState<TabId>("chat");
  const [repo, setRepo] = useState<RepoOverview | null>(null);

  return (
    <div className="h-screen flex overflow-hidden">
      <Sidebar tab={tab} onTab={setTab} repo={repo} onRepoChange={setRepo} />
      <main className="flex-1 min-w-0 h-full">
        {tab === "chat" && <ChatPanel repo={repo} />}
        {tab === "review" && <ReviewPanel repo={repo} />}
        {tab === "tests" && <TestsPanel repo={repo} />}
        {tab === "eval" && <EvalPanel repo={repo} />}
      </main>
    </div>
  );
}
