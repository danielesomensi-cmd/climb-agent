"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * Keeps a lazily loaded component (next/dynamic) from taking the page down
 * when its chunk cannot be fetched.
 *
 * A dynamic chunk is only cached by the service worker once it has been
 * fetched online. Offline (gym, crag) or right after a deploy, the import
 * rejects, React.lazy throws during render and the nearest route error
 * boundary replaces the whole page — or the whole app for a component that
 * lives in a layout. Wrapped in this boundary, the component renders
 * `fallback` (nothing by default) and `onError` can tell the user why.
 *
 * React.lazy keeps the rejected import for the life of the page, so the
 * component stays unavailable until the next page load; pair the boundary
 * with an idle preload (`void import(...)` while online) so the chunk is in
 * the service worker cache before it is needed.
 */
export class ChunkErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode; onError?: (error: Error) => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Lazy component failed to load:", error, info.componentStack);
    this.props.onError?.(error);
  }

  render(): ReactNode {
    return this.state.failed ? (this.props.fallback ?? null) : this.props.children;
  }
}
