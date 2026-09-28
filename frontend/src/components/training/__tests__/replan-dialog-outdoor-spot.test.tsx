/**
 * @vitest-environment jsdom
 *
 * B360 — replanificare una giornata come outdoor deve chiedere DOVE.
 *
 * Prima: il dialog mandava solo {intent, location:"outdoor"} e il backend
 * derivava il nome della falesia dall'intent — "projecting", "volume", "easy".
 * Nomi che `geocode_place()` non risolve, quindi niente meteo nel coach per
 * quella giornata (visto in produzione sul trip di Kalymnos).
 *
 * Ora il picker è obbligatorio, come già in quick-add-dialog: Apply resta
 * disabled finché non scegli una falesia, con "Add new spot" inline se non
 * ne hai.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor } from "@testing-library/react";

const getOutdoorSpots = vi.fn();
const addOutdoorSpot = vi.fn();

vi.mock("@/lib/api", () => ({
  getOutdoorSpots: (...a: unknown[]) => getOutdoorSpots(...a),
  addOutdoorSpot: (...a: unknown[]) => addOutdoorSpot(...a),
}));

import { ReplanDialog } from "../replan-dialog";

afterEach(cleanup);

const SPOTS = [
  { id: "spot_gg", name: "Grande Grotta", discipline: "lead" as const },
  { id: "spot_sym", name: "Symplegades", discipline: "lead" as const },
];

const applyButton = () =>
  screen.getByRole("button", { name: "Apply" }) as HTMLButtonElement;

const clickText = async (label: string | RegExp) => {
  await act(async () => {
    (screen.getByText(label).closest("button") as HTMLButtonElement).click();
  });
};

function renderDialog(onApply = vi.fn()) {
  render(
    <ReplanDialog
      open
      date="2026-01-06"
      gyms={[{ gym_id: "cocque", name: "Cocque", equipment: [] }]}
      onClose={vi.fn()}
      onApply={onApply}
    />,
  );
  return onApply;
}

describe("ReplanDialog — outdoor spot picker (B360)", () => {
  beforeEach(() => {
    getOutdoorSpots.mockReset();
    addOutdoorSpot.mockReset();
    getOutdoorSpots.mockResolvedValue({ spots: SPOTS });
  });

  it("non carica gli spot finché si resta indoor", async () => {
    renderDialog();
    expect(getOutdoorSpots).not.toHaveBeenCalled();
    expect(applyButton().disabled).toBe(false);
  });

  it("carica gli spot passando su Outdoor", async () => {
    renderDialog();
    await clickText("Outdoor");
    await waitFor(() => expect(getOutdoorSpots).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Grande Grotta")).toBeTruthy());
  });

  it("Apply resta disabled finché non si sceglie una falesia", async () => {
    renderDialog();
    await clickText("Outdoor");
    await waitFor(() => expect(screen.getByText("Grande Grotta")).toBeTruthy());
    expect(applyButton().disabled).toBe(true);

    await clickText("Grande Grotta");
    expect(applyButton().disabled).toBe(false);
  });

  it("onApply riceve spot_id e spot_name insieme all'intent", async () => {
    const onApply = renderDialog();
    await clickText("Outdoor");
    await waitFor(() => expect(screen.getByText("Symplegades")).toBeTruthy());
    await clickText("Symplegades");
    await clickText("Volume routes");
    await act(async () => {
      applyButton().click();
    });

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0]).toMatchObject({
      intent: "outdoor_volume",
      location: "outdoor",
      spot_id: "spot_sym",
      spot_name: "Symplegades",
    });
  });

  it("non manda mai l'intent come nome della falesia", async () => {
    const onApply = renderDialog();
    await clickText("Outdoor");
    await waitFor(() => expect(screen.getByText("Grande Grotta")).toBeTruthy());
    await clickText("Grande Grotta");
    await clickText("Projecting");
    await act(async () => {
      applyButton().click();
    });

    const payload = onApply.mock.calls[0][0] as { spot_name?: string };
    expect(payload.spot_name).toBe("Grande Grotta");
    expect(["projecting", "volume", "easy", "boulder"]).not.toContain(
      (payload.spot_name ?? "").toLowerCase(),
    );
  });

  it("senza spot salvati si può crearne uno inline e diventa selezionato", async () => {
    getOutdoorSpots.mockResolvedValue({ spots: [] });
    addOutdoorSpot.mockResolvedValue({
      spot: { id: "spot_new", name: "Berdorf", discipline: "lead" },
    });
    const onApply = renderDialog();
    await clickText("Outdoor");
    await waitFor(() => expect(screen.getByText("No saved spots")).toBeTruthy());
    expect(applyButton().disabled).toBe(true);

    await clickText("+ Add new spot");
    const input = screen.getByPlaceholderText(/Spot name/) as HTMLInputElement;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(input, "Berdorf");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await clickText("Save spot");

    await waitFor(() => expect(applyButton().disabled).toBe(false));
    await act(async () => {
      applyButton().click();
    });
    expect(onApply.mock.calls[0][0]).toMatchObject({
      spot_id: "spot_new",
      spot_name: "Berdorf",
    });
  });

  it("Skip day resta un percorso indoor senza falesia", async () => {
    const onApply = renderDialog();
    await clickText("Skip day");
    expect(onApply.mock.calls[0][0]).toMatchObject({
      intent: "rest",
      location: "home",
    });
    expect(onApply.mock.calls[0][0].spot_name).toBeUndefined();
  });
});
