#!/usr/bin/env python3
"""Schizzo di un settore/parete a partire da un elenco di vie (A278, seguito ad A276).

NON è un topo fotografico: è uno schema didattico (linee colorate per grado,
nome/lunghezza/stelle in etichetta) costruito dai dati testuali di guida
(nome, grado, posizione sinistra→destra, lunghezza, stelle) — non traccia
niente su una foto reale della parete.

Uso da riga di comando:

    python3 scripts/topo_sketch.py --sector "Summertime — Main" \
        --routes routes.json --out schizzo.png

`routes.json` è una lista di oggetti: {"position": 1, "name": "Salbei",
"grade": "6a", "length_m": 20, "stars": 2}. Solo "name" e "grade" sono
obbligatori; "position" di default segue l'ordine della lista.

Dipende da `rsvg-convert` (`brew install librsvg`) per il passaggio SVG→PNG;
`build_svg()` da solo non ha dipendenze esterne ed è quello coperto dai test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROUTE_WIDTH = 90
ROUTE_GAP = 40
WALL_HEIGHT = 420
MARGIN_TOP = 110  # spazio per titolo + sottotitolo + etichetta via, senza sovrapporli
MARGIN_BOTTOM = 40
MARGIN_SIDE = 40

BG_TOP = "#eef2f4"      # cielo pallido
ROCK_LIGHT = "#cabfa8"  # roccia in luce
ROCK_DARK = "#9c8f76"   # roccia in ombra / talus
TEXT_COLOR = "#2b2b2b"
BOLT_COLOR = "#4a4438"


def _seed_for(*parts: str) -> int:
    """Seed deterministico da stringhe — stesso input, stesso schizzo, sempre
    (niente `random` senza seme: due run dello stesso settore devono
    combaciare, altrimenti build_svg smette di essere testabile a puntino)."""
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _grade_color(grade: str) -> str:
    """Fascia di colore approssimata sulla scala francese — solo per leggibilità
    a colpo d'occhio, non un giudizio di difficoltà preciso."""
    g = str(grade).strip().lower()
    digits = "".join(ch for ch in g if ch.isdigit())
    n = int(digits) if digits else 0
    has_plus = "+" in g
    if n <= 5 and not has_plus and "a" not in g and "b" not in g and "c" not in g:
        return "#3fae5c"  # verde: facile (fino a 5)
    if n <= 6 and ("a" in g or (n == 5 and has_plus)):
        return "#2f9bd6"  # blu/turchese: 5+/6a-6a+
    if n <= 6:
        return "#f0a52c"  # arancio: 6b/6c
    return "#d94f4f"  # rosso: 7a e oltre


def _label_width_px(route: dict) -> float:
    """Stima larghezza (px) delle due righe di etichetta di una via, per
    dimensionare la colonna — senza questo, un nome lungo ("A Route With a
    View") si sovrapponeva alla via accanto: nessun errore, solo un render
    illeggibile (vedi lezione A278 in docs/lessons.md)."""
    name = str(route.get("name", "?"))
    grade = str(route.get("grade", "?"))
    length = route.get("length_m")
    grade_line = grade + (f" · {length}m" if length else "")
    # Helvetica bold ~14px e regular ~12px: stima grezza, non metrica di font vera.
    return max(len(name) * 8.6, len(grade_line) * 7.2)


def _jagged_line(rng: random.Random, x0: float, x1: float, y: float, amplitude: float, step: float) -> list[tuple[float, float]]:
    """Punti di un profilo roccioso irregolare fra x0 e x1, attorno a y."""
    points = []
    x = x0
    while x < x1:
        points.append((x, y + rng.uniform(-amplitude, amplitude)))
        x += step * rng.uniform(0.6, 1.4)
    points.append((x1, y + rng.uniform(-amplitude, amplitude)))
    return points


def _smooth_path(points: list[tuple[float, float]]) -> str:
    """Path SVG che passa dai punti dati con curve morbide (quadratiche verso
    il punto medio fra un punto e il successivo) invece di segmenti dritti."""
    if len(points) < 2:
        return ""
    d = f"M {points[0][0]:.1f} {points[0][1]:.1f} "
    for i in range(1, len(points)):
        px, py = points[i - 1]
        cx, cy = points[i]
        mx, my = (px + cx) / 2, (py + cy) / 2
        d += f"Q {px:.1f} {py:.1f} {mx:.1f} {my:.1f} "
    last = points[-1]
    d += f"L {last[0]:.1f} {last[1]:.1f}"
    return d


def _route_climb_points(rng: random.Random, cx: float, y_top: float, y_bot: float, half_width: float) -> list[tuple[float, float]]:
    """Punti (base→cima) di una via: zig-zag naturale, non un tubo dritto."""
    n = rng.randint(4, 6)
    points = [(cx, y_bot)]
    for i in range(1, n):
        frac = i / n
        y = y_bot - (y_bot - y_top) * frac
        spread = half_width * rng.uniform(0.4, 1.0) * rng.choice([-1, 1])
        points.append((cx + spread, y))
    points.append((cx, y_top))
    return points


def _rock_backdrop(width: float, height: float, sector: str) -> list[str]:
    """Sfondo roccia: cielo sfumato, silhouette di cresta irregolare in alto,
    talus irregolare in basso, e qualche macchia scura per la texture — tutto
    seminato sul nome del settore, così lo stesso settore produce sempre lo
    stesso sfondo (niente diff casuali fra due run identiche)."""
    rng = random.Random(_seed_for("backdrop", sector))
    wall_top = MARGIN_TOP - 10
    wall_bottom = MARGIN_TOP + WALL_HEIGHT
    parts = [
        "<defs>",
        f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{BG_TOP}"/>'
        f'<stop offset="100%" stop-color="#dfd6c2"/>'
        f"</linearGradient>",
        f'<linearGradient id="rock" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{ROCK_LIGHT}"/>'
        f'<stop offset="100%" stop-color="#b3a68d"/>'
        f"</linearGradient>",
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="url(#sky)"/>',
    ]

    # Silhouette della parete: profilo di cresta irregolare fino al bordo alto,
    # riempita di roccia fino al fondo.
    crest = _jagged_line(rng, 0, width, wall_top, amplitude=22, step=width / 14)
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in crest)
    parts.append(
        f'<polygon points="0,{height:.1f} {poly} {width:.1f},{height:.1f}" fill="url(#rock)"/>'
    )

    # Macchie scure sparse, decorative — suggeriscono texture di roccia senza
    # pretendere di essere una foto.
    for _ in range(max(6, int(width / 220))):
        bx = rng.uniform(0, width)
        by = rng.uniform(wall_top + 20, wall_bottom - 20)
        br = rng.uniform(18, 48)
        parts.append(
            f'<ellipse cx="{bx:.1f}" cy="{by:.1f}" rx="{br:.1f}" ry="{br * rng.uniform(0.5, 0.9):.1f}" '
            f'fill="{ROCK_DARK}" opacity="{rng.uniform(0.08, 0.18):.2f}"/>'
        )

    # Base/talus irregolare invece di una barra piatta.
    talus = _jagged_line(rng, 0, width, wall_bottom + 6, amplitude=6, step=width / 18)
    talus_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in talus)
    parts.append(
        f'<polygon points="0,{height:.1f} {talus_poly} {width:.1f},{height:.1f}" fill="{ROCK_DARK}"/>'
    )
    return parts


def build_svg(sector: str, routes: list[dict], subtitle: str = "") -> str:
    """Genera l'SVG dello schizzo. Pura — nessuna dipendenza esterna, testabile.

    Stile "topo vettoriale da guidebook" (silhouette di roccia + linee vie +
    rinvii), non un fotomontaggio: niente qui prova a imitare una foto reale
    della parete — non ne ho una da annotare."""
    if not routes:
        raise ValueError("build_svg richiede almeno una via")

    ordered = sorted(
        enumerate(routes),
        key=lambda pair: (pair[1].get("position", pair[0]), pair[0]),
    )

    route_width = max(ROUTE_WIDTH, max(_label_width_px(r) for _, r in ordered) + 10)

    width = MARGIN_SIDE * 2 + len(ordered) * (route_width + ROUTE_GAP) - ROUTE_GAP
    height = MARGIN_TOP + WALL_HEIGHT + MARGIN_BOTTOM

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
    ]
    parts.extend(_rock_backdrop(width, height, sector))
    parts.append(
        f'<text x="{width / 2}" y="34" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="26" font-weight="bold" text-anchor="middle" fill="{TEXT_COLOR}" '
        f'style="paint-order: stroke; stroke: {BG_TOP}; stroke-width: 5px;">'
        f'{_esc(sector)}</text>'
    )
    if subtitle:
        parts.append(
            f'<text x="{width / 2}" y="56" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="14" text-anchor="middle" fill="#4a4438" '
            f'style="paint-order: stroke; stroke: {BG_TOP}; stroke-width: 4px;">'
            f'{_esc(subtitle)}</text>'
        )

    x = MARGIN_SIDE
    for position, route in ordered:
        name = route.get("name", "?")
        grade = route.get("grade", "?")
        length = route.get("length_m")
        stars = int(route.get("stars", 0) or 0)
        color = _grade_color(grade)
        route_number = route.get("position", position + 1)

        cx = x + route_width / 2
        y_top = MARGIN_TOP + 10
        y_bot = MARGIN_TOP + WALL_HEIGHT - 10
        half_width = route_width * 0.32

        rng = random.Random(_seed_for("route", sector, str(name), str(route_number)))
        climb_points = _route_climb_points(rng, cx, y_top, y_bot, half_width)

        # Alone chiaro sotto la linea vera: la stacca dallo sfondo scuro senza
        # bisogno di un contorno nero che la farebbe sembrare un cartone.
        parts.append(
            f'<path d="{_smooth_path(climb_points)}" fill="none" stroke="{BG_TOP}" '
            f'stroke-width="7" stroke-linecap="round" stroke-linejoin="round" opacity="0.55"/>'
        )
        parts.append(
            f'<path d="{_smooth_path(climb_points)}" fill="none" stroke="{color}" '
            f'stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        # Rinvii: pallini lungo la via, non a ogni vertice del percorso ma a
        # intervalli regolari — un topo vero non segna ogni piega della corda.
        n_bolts = max(3, min(9, round((length or 20) / 4)))
        for i in range(1, n_bolts):
            t = i / n_bolts
            idx = t * (len(climb_points) - 1)
            lo, hi = int(idx), min(int(idx) + 1, len(climb_points) - 1)
            frac = idx - lo
            bx = climb_points[lo][0] + (climb_points[hi][0] - climb_points[lo][0]) * frac
            by = climb_points[lo][1] + (climb_points[hi][1] - climb_points[lo][1]) * frac
            parts.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="2.6" fill="{BOLT_COLOR}"/>')

        # Numero via in un cerchietto alla base — convenzione da guidebook.
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{y_bot + 14:.1f}" r="11" fill="{TEXT_COLOR}"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{y_bot + 18:.1f}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="11" font-weight="bold" text-anchor="middle" fill="{BG_TOP}">'
            f'{_esc(route_number)}</text>'
        )

        label_top = _esc(name)
        label_grade = _esc(grade) + (f" · {length}m" if length else "")
        stars_str = "★" * stars if stars else ""
        parts.append(
            f'<text x="{cx}" y="{y_top - 40}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="14" font-weight="bold" text-anchor="middle" fill="{TEXT_COLOR}">'
            f'{label_top}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{y_top - 24}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="12" text-anchor="middle" fill="{color}">{label_grade} {stars_str}</text>'
        )
        x += route_width + ROUTE_GAP

    parts.append("</svg>")
    return "\n".join(parts)


def rsvg_binary() -> str:
    override = os.environ.get("RSVG_CONVERT_BIN")
    if override:
        return override
    found = shutil.which("rsvg-convert")
    if found:
        return found
    return "/opt/homebrew/bin/rsvg-convert"


def svg_to_png(svg_text: str, out_path: Path) -> None:
    binary = rsvg_binary()
    if not Path(binary).exists():
        raise RuntimeError(
            f"rsvg-convert non trovato ({binary}) — installa con `brew install librsvg`."
        )
    proc = subprocess.run(
        [binary, "-o", str(out_path)],
        input=svg_text.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            "Conversione SVG->PNG fallita:\n" + proc.stderr.decode("utf-8", "replace")[-500:]
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sector", required=True, help="Nome del settore/parete")
    parser.add_argument("--subtitle", default="", help="Sottotitolo opzionale")
    parser.add_argument("--routes", required=True, help="File JSON con la lista di vie")
    parser.add_argument("--out", required=True, help="Percorso PNG di output")
    parser.add_argument("--svg-out", default=None, help="Se dato, salva anche l'SVG intermedio")
    args = parser.parse_args(argv)

    routes = json.loads(Path(args.routes).read_text(encoding="utf-8"))
    svg = build_svg(args.sector, routes, args.subtitle)

    if args.svg_out:
        Path(args.svg_out).write_text(svg, encoding="utf-8")

    svg_to_png(svg, Path(args.out))
    print(f"Scritto {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
