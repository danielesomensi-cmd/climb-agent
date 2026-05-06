/**
 * B-NEWMACRO-DEADLINE-FIX — pin the user-facing error classifier so future
 * refactors of the dialog don't accidentally leak raw API strings to the user.
 *
 * The dialog NEVER displays:
 *   - HTTP status codes
 *   - Response body / detail field
 *   - Stack traces / "API <code>:" prefix
 *
 * Only the classifier's `userMessage` ever reaches the DOM.
 */

import { describe, it, expect } from "vitest";
import { classifyApiError } from "../start-new-macrocycle-dialog";

describe("classifyApiError", () => {
  it("returns the subscription copy for 402", () => {
    const err = new Error('API 402: {"detail":{"error":"subscription_required"}}');
    const { userMessage, status } = classifyApiError(err);
    expect(status).toBe(402);
    expect(userMessage).toContain("subscription is required");
    expect(userMessage).not.toContain("402");
    expect(userMessage).not.toContain("detail");
  });

  it("returns the generic copy for 404 — never leaks 'Not Found' or status", () => {
    const err = new Error('API 404: {"detail":"Not Found"}');
    const { userMessage, status } = classifyApiError(err);
    expect(status).toBe(404);
    expect(userMessage).toMatch(/Couldn't start the new cycle/);
    expect(userMessage).not.toMatch(/404|Not Found|detail/);
  });

  it("returns the generic copy for 500", () => {
    const err = new Error('API 500: {"detail":"Internal Server Error"}');
    const { userMessage } = classifyApiError(err);
    expect(userMessage).toMatch(/Couldn't start the new cycle/);
    expect(userMessage).not.toMatch(/500|Internal/);
  });

  it("returns the generic copy when status cannot be parsed (network error)", () => {
    const err = new Error("Failed to fetch");
    const { userMessage, status } = classifyApiError(err);
    expect(status).toBeNull();
    expect(userMessage).toMatch(/Couldn't start the new cycle/);
    expect(userMessage).not.toMatch(/fetch/);
  });

  it("handles non-Error throwables", () => {
    const { userMessage, status } = classifyApiError("plain string error");
    expect(status).toBeNull();
    expect(userMessage).toMatch(/Couldn't start the new cycle/);
  });
});
