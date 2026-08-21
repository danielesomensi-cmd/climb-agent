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
import json
import os
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

BG_COLOR = "#faf6ee"
ROCK_COLOR = "#8a7a63"
TEXT_COLOR = "#2b2b2b"


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


def build_svg(sector: str, routes: list[dict], subtitle: str = "") -> str:
    """Genera l'SVG dello schizzo. Pura — nessuna dipendenza esterna, testabile."""
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
        f'<rect width="{width}" height="{height}" fill="{BG_COLOR}"/>',
        f'<text x="{width / 2}" y="34" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="26" font-weight="bold" text-anchor="middle" fill="{TEXT_COLOR}">'
        f'{_esc(sector)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{width / 2}" y="56" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="14" text-anchor="middle" fill="#666">{_esc(subtitle)}</text>'
        )

    parts.append(
        f'<rect x="0" y="{MARGIN_TOP + WALL_HEIGHT}" width="{width}" height="8" '
        f'fill="{ROCK_COLOR}"/>'
    )

    x = MARGIN_SIDE
    for _, route in ordered:
        name = route.get("name", "?")
        grade = route.get("grade", "?")
        length = route.get("length_m")
        stars = int(route.get("stars", 0) or 0)
        color = _grade_color(grade)

        cx = x + route_width / 2
        y_top = MARGIN_TOP + 10
        y_bot = MARGIN_TOP + WALL_HEIGHT - 10
        mid1 = y_top + (y_bot - y_top) * 0.35
        mid2 = y_top + (y_bot - y_top) * 0.7
        dx = route_width * 0.18
        path = f"M {cx} {y_bot} L {cx - dx} {mid2} L {cx + dx} {mid1} L {cx} {y_top}"
        parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="5" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
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
