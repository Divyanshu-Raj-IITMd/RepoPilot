import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoPilot — Agentic AI Software Engineering Assistant",
  description:
    "Understands codebases through AST-aware indexing, semantic retrieval and agentic workflows: repository analysis, code search, issue investigation, PR review and verified test generation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
