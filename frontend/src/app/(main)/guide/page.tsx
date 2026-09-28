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

      {/* A286 — misura di lettura: max-w-2xl mandava il corpo oltre i 100 caratteri
          per riga su desktop. ~68ch è la riga leggibile. */}
      <main className="mx-auto max-w-[68ch] p-4 space-y-4">
        {/* Search bar */}
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search guide..."
          // A286 — text-base: sotto i 16px iOS zooma al focus e non torna indietro.
          className="w-full rounded-md border border-border bg-card px-3 py-2 text-base text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />

        {/* No results */}
        {query && filtered.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-6">
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
                className="rounded-md border border-border bg-card overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => toggle(section.id)}
                  className="flex min-h-[44px] w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-accent transition-colors"
                >
                  <span>{section.title}</span>
                  <svg
                    className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
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
        <p className="text-xs text-muted-foreground text-center pb-4">
          Built on peer-reviewed climbing training science: H&ouml;rst, Lattice, Eva L&oacute;pez, Tyler Nelson.
        </p>
      </main>
    </>
  );
}
