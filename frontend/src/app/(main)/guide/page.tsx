"use client";

import { useMemo, useState } from "react";
import { TopBar } from "@/components/layout/top-bar";
import { GUIDE_SECTIONS } from "@/lib/guide-content";

export default function GuidePage() {
  const [search, setSearch] = useState("");
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  const query = search.trim().toLowerCase();

  const filtered = useMemo(() => {
    if (!query) return GUIDE_SECTIONS;
    return GUIDE_SECTIONS.filter(
      (s) =>
        s.title.toLowerCase().includes(query) ||
        s.searchText.toLowerCase().includes(query),
    );
  }, [query]);

  // When searching, auto-expand all matches
  const effectiveOpen = query ? new Set(filtered.map((s) => s.id)) : openIds;

  function toggle(id: string) {
    if (query) return; // Don't toggle during search — all are open
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <>
      <TopBar title="Guide" />

      <main className="mx-auto max-w-2xl p-4 space-y-4">
        {/* Search bar */}
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search guide..."
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
        />

        {/* No results */}
        {query && filtered.length === 0 && (
          <p className="text-sm text-zinc-500 text-center py-6">
            No results found for &ldquo;{search.trim()}&rdquo;
          </p>
        )}

        {/* Accordion sections */}
        <div className="space-y-2">
          {filtered.map((section) => {
            const isOpen = effectiveOpen.has(section.id);
            return (
              <div
                key={section.id}
                className="rounded-lg border border-zinc-800 overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => toggle(section.id)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-zinc-200 hover:bg-zinc-800/50 transition-colors"
                >
                  <span>{section.title}</span>
                  <svg
                    className={`h-4 w-4 shrink-0 text-zinc-500 transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 pt-1">{section.body}</div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <p className="text-[11px] text-zinc-600 text-center pb-4">
          Built on peer-reviewed climbing training science: H&ouml;rst, Lattice, Eva L&oacute;pez, Tyler Nelson.
        </p>
      </main>
    </>
  );
}
