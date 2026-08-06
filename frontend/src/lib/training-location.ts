/**
 * B322 — where a training slot defaults to when the user never picks a place.
 *
 * The availability step used to default every slot to "home". The planner
 * treats `preferred_location` as binding, so a user who ticked "Yes" without
 * ever opening the location control had their whole climbing week dropped: in
 * production a boulderer with a fully equipped gym, `home_enabled=false` and an
 * empty home kit received nothing but stretching, core and prehab.
 *
 * The engine now falls back when home is a dead end, but the honest fix is not
 * to hand it a wrong default in the first place.
 */

export interface EquipmentLike {
  home_enabled?: boolean;
  home?: string[];
  gyms?: unknown[];
}

/**
 * Default `preferred_location` for a newly enabled slot.
 *
 * Returns "gym" only when the user has a gym AND home is not somewhere they
 * can train. With no gym on file "home" stays the default — it is the only
 * place left, and pointing at a gym that does not exist helps nobody.
 */
export function defaultTrainingLocation(equipment: EquipmentLike | null | undefined): "home" | "gym" {
  const gyms = equipment?.gyms ?? [];
  const home = equipment?.home ?? [];
  const homeUsable = equipment?.home_enabled !== false && home.length > 0;
  return gyms.length > 0 && !homeUsable ? "gym" : "home";
}
