"""A316 — heart-rate bands from the athlete's own max heart rate.

Pure and deterministic. The catalog carries the band as a percentage of HRmax
(``exercise.hr_target``); this module turns it into beats per minute. There is
no estimate from age: a formula can be 10 bpm off for a given person, so with no
recorded HRmax the band stays a percentage.

The frontend mirrors ``bpm_band`` in ``src/lib/hr-zones.ts`` (display only).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Tuple

HR_MAX_MIN = 120
HR_MAX_MAX = 230
HR_REST_MIN = 30
HR_REST_MAX = 110

#: Zone 2 and the 4x4 bands, the two the catalog uses (% of HRmax).
Z2_PCT = (60, 70)
INTERVAL_PCT = (90, 95)
RECOVERY_PCT = (65, 75)


def _int_in(value: Any, lo: int, hi: int) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = int(round(value))
    return v if lo <= v <= hi else None


def _body(state: Mapping[str, Any]) -> Mapping[str, Any]:
    body = state.get("body") or {}
    if body.get("hr_max_bpm") is None:
        body = (state.get("assessment") or {}).get("body") or body
    return body


def hr_max(state: Mapping[str, Any]) -> Optional[int]:
    """The recorded HRmax (``body.hr_max_bpm``), or None if absent/implausible."""
    return _int_in(_body(state).get("hr_max_bpm"), HR_MAX_MIN, HR_MAX_MAX)


def hr_rest(state: Mapping[str, Any]) -> Optional[int]:
    return _int_in(_body(state).get("hr_rest_bpm"), HR_REST_MIN, HR_REST_MAX)


def bpm_band(hr_max_bpm: int, pct: Sequence[float]) -> Tuple[int, int]:
    """``pct`` = (low, high) % of HRmax → (low, high) bpm, never outside the % band.

    The low end rounds up and the high end rounds down, in integer arithmetic:
    ``round()`` would round half to even (190 × 95 % = 180.5 → 180 but
    190 × 75 % = 142.5 → 142) and the frontend's ``Math.round`` half up, so the
    two sides would disagree by one beat on every .5.
    """
    lo, hi = (int(round(p)) for p in pct)
    return -(-hr_max_bpm * lo // 100), hr_max_bpm * hi // 100


def coach_line(state: Mapping[str, Any]) -> Optional[str]:
    """One prompt line with the athlete's bands in bpm, or None without HRmax."""
    hm = hr_max(state)
    if hm is None:
        return None
    source = _body(state).get("hr_max_source") or "measured"
    z2 = bpm_band(hm, Z2_PCT)
    iv = bpm_band(hm, INTERVAL_PCT)
    rc = bpm_band(hm, RECOVERY_PCT)
    rest = hr_rest(state)
    rest_txt = f", resting HR {rest} bpm" if rest is not None else ""
    return (
        f"- Heart rate: HRmax {hm} bpm ({source}){rest_txt}. Bands in bpm, use these "
        f"and never an age formula: Zone 2 {z2[0]}-{z2[1]}, 4x4 intervals "
        f"{iv[0]}-{iv[1]}, active recovery between intervals {rc[0]}-{rc[1]}."
    )
