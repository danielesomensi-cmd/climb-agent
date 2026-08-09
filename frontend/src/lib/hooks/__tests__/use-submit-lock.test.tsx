/**
 * @vitest-environment jsdom
 *
 * B330 — a double tap must produce one write, not two.
 *
 * `disabled={busy}` is not a guard: setState is asynchronous, so two clicks
 * dispatched before React re-renders both enter the handler. This is not a
 * theoretical race — it is an ordinary double tap on a phone, and on a slow
 * connection the window stays open for the whole request.
 *
 * No jest-dom matchers here: the suite (B323) does not install them, so
 * assertions read the DOM directly.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor, act } from "@testing-library/react";
import { useState } from "react";
import { useSubmitLock } from "../use-submit-lock";

afterEach(cleanup);

function Form({ onSave }: { onSave: () => Promise<void> }) {
  const { run, busy } = useSubmitLock(onSave);
  // `run` re-throws whatever the handler throws (the hook owns the lock, not
  // the error policy). The app's handlers catch internally and set an error
  // message; here we swallow so a rejection test does not surface as an
  // unhandled rejection.
  return (
    <button
      data-testid="save"
      onClick={() => {
        run().catch(() => {});
      }}
      disabled={busy}
    >
      {busy ? "Saving..." : "Save"}
    </button>
  );
}

const btn = () => screen.getByTestId("save") as HTMLButtonElement;

describe("useSubmitLock", () => {
  let release: () => void;
  let calls: number;
  let onSave: () => Promise<void>;

  beforeEach(() => {
    calls = 0;
    onSave = vi.fn(() => {
      calls += 1;
      return new Promise<void>((r) => {
        release = r;
      });
    });
  });

  it("runs the handler once for two clicks in the same batch", async () => {
    render(<Form onSave={onSave} />);
    // The real double-tap shape: no await between the two clicks, so React has
    // not re-rendered and the button is still enabled for the second one.
    await act(async () => {
      btn().click();
      btn().click();
    });
    expect(calls).toBe(1);
  });

  it("blocks further clicks for the whole in-flight request", async () => {
    render(<Form onSave={onSave} />);
    await act(async () => {
      btn().click();
    });
    expect(btn().disabled).toBe(true);
    await act(async () => {
      btn().click();
      btn().click();
    });
    expect(calls).toBe(1);
  });

  it("allows a second submit after the first settles", async () => {
    render(<Form onSave={onSave} />);
    await act(async () => {
      btn().click();
    });
    await act(async () => {
      release();
    });
    await waitFor(() => expect(btn().disabled).toBe(false));
    await act(async () => {
      btn().click();
    });
    expect(calls).toBe(2);
  });

  it("releases the lock when the handler rejects", async () => {
    let fail: (e: Error) => void = () => {};
    const failing = vi.fn(
      () =>
        new Promise<void>((_, reject) => {
          fail = reject;
        }),
    );
    render(<Form onSave={failing} />);
    await act(async () => {
      btn().click();
    });
    await act(async () => {
      fail(new Error("network down"));
      // the rejection surfaces through run(); a caller would handle it
      await Promise.resolve().catch(() => {});
    });
    await waitFor(() => expect(btn().disabled).toBe(false));
    await act(async () => {
      btn().click();
    });
    expect(failing).toHaveBeenCalledTimes(2);
  });

  it("reflects the in-flight state in the label", async () => {
    render(<Form onSave={onSave} />);
    await act(async () => {
      btn().click();
    });
    expect(btn().textContent).toBe("Saving...");
    await act(async () => {
      release();
    });
    await waitFor(() => expect(btn().textContent).toBe("Save"));
  });

  it("control: the plain useState pattern it replaces DOES double-fire", async () => {
    // Proves the tests above are not tautological — this is the exact code
    // shape the three forms used before B330.
    function Unguarded() {
      const [busy, setBusy] = useState(false);
      return (
        <button
          data-testid="unguarded"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void onSave().finally(() => setBusy(false));
          }}
        >
          save
        </button>
      );
    }
    render(<Unguarded />);
    const b = screen.getByTestId("unguarded") as HTMLButtonElement;
    await act(async () => {
      b.click();
      b.click();
    });
    expect(calls).toBe(2);
  });

  it("survives a parent re-render mid-flight", async () => {
    function Parent() {
      const [, force] = useState(0);
      return (
        <>
          <Form onSave={onSave} />
          <button data-testid="force" onClick={() => force((n) => n + 1)}>
            rerender
          </button>
        </>
      );
    }
    render(<Parent />);
    await act(async () => {
      btn().click();
    });
    await act(async () => {
      (screen.getByTestId("force") as HTMLButtonElement).click();
    });
    await act(async () => {
      btn().click();
    });
    expect(calls).toBe(1);
  });
});
