"""A278 — schizzo SVG di settore/parete (scripts/topo_sketch.py).

Strumento personale (segue A276), non tocca l'engine. Copertura mirata su
`build_svg()`, che è pura e non ha dipendenze esterne, più `svg_to_png()` con
`subprocess.run` mockato (niente dipendenza da `rsvg-convert` installato per
far girare i test).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "topo_sketch.py"


@pytest.fixture(scope="module")
def topo_sketch():
    spec = importlib.util.spec_from_file_location("topo_sketch_a278", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_svg_rifiuta_lista_vuota(topo_sketch):
    with pytest.raises(ValueError):
        topo_sketch.build_svg("Settore vuoto", [])


def test_build_svg_contiene_nome_grado_e_settore(topo_sketch):
    svg = topo_sketch.build_svg(
        "Summertime — Main",
        [
            {"position": 1, "name": "Salbei", "grade": "6a", "length_m": 20, "stars": 2},
            {"position": 2, "name": "Friends", "grade": "6b+", "length_m": 20, "stars": 1},
        ],
    )
    assert "Summertime — Main" in svg
    assert "Salbei" in svg
    assert "Friends" in svg
    assert "6a" in svg
    assert "6b+" in svg
    assert svg.strip().startswith("<svg")
    assert svg.strip().endswith("</svg>")


def test_build_svg_rispetta_ordine_di_posizione_non_di_lista(topo_sketch):
    """Le vie vanno disegnate nell'ordine di `position`, anche se la lista in
    input arriva in un ordine diverso (è quello che succede coi dati di guida:
    Salbei #01, Friends #02, ma con dei buchi in mezzo)."""
    svg = topo_sketch.build_svg(
        "Settore",
        [
            {"position": 12, "name": "Salamina tis Kypros", "grade": "6a+"},
            {"position": 1, "name": "Salbei", "grade": "6a"},
            {"position": 2, "name": "Friends", "grade": "6b+"},
        ],
    )
    idx_salbei = svg.index("Salbei")
    idx_friends = svg.index("Friends")
    idx_salamina = svg.index("Salamina")
    assert idx_salbei < idx_friends < idx_salamina


def test_build_svg_allarga_le_colonne_per_nomi_lunghi(topo_sketch):
    """Regressione: 'A Route With a View' finiva sovrapposto al nome della via
    accanto perché la colonna aveva larghezza fissa indipendente dal testo —
    nessun errore, solo un PNG illeggibile (vedi lezione A278)."""
    import re

    def _svg_width(svg: str) -> float:
        return float(re.search(r'width="(\d+(?:\.\d+)?)"', svg).group(1))

    corte = topo_sketch.build_svg("S", [{"name": "A", "grade": "6a"}, {"name": "B", "grade": "6a"}])
    con_nome_lungo = topo_sketch.build_svg(
        "S",
        [{"name": "A Route With a View", "grade": "6a"}, {"name": "B", "grade": "6a"}],
    )
    assert _svg_width(con_nome_lungo) > _svg_width(corte)


def test_build_svg_via_senza_posizione_usa_ordine_di_lista(topo_sketch):
    svg = topo_sketch.build_svg(
        "Settore",
        [{"name": "Prima", "grade": "5"}, {"name": "Seconda", "grade": "6a"}],
    )
    assert svg.index("Prima") < svg.index("Seconda")


def test_build_svg_esegue_escaping_xml(topo_sketch):
    svg = topo_sketch.build_svg("Settore <test> & C.", [{"name": 'Via "strana" <A&B>', "grade": "6a"}])
    assert "<test>" not in svg
    assert "&lt;test&gt;" in svg
    assert "&amp;" in svg
    assert '"strana"' not in svg  # va escapato in &quot;


def test_grade_color_bande_approssimate(topo_sketch):
    facile = topo_sketch._grade_color("5")
    medio = topo_sketch._grade_color("6a")
    medio_alto = topo_sketch._grade_color("6b")
    duro = topo_sketch._grade_color("7a")
    assert len({facile, medio, medio_alto, duro}) == 4  # quattro fasce distinte


def test_svg_to_png_senza_binario_da_errore_azionabile(topo_sketch, monkeypatch, tmp_path):
    monkeypatch.setattr(topo_sketch, "rsvg_binary", lambda: str(tmp_path / "non-esiste"))
    with pytest.raises(RuntimeError, match="rsvg-convert non trovato"):
        topo_sketch.svg_to_png("<svg></svg>", tmp_path / "out.png")


def test_svg_to_png_orchestrazione_con_subprocess_finto(topo_sketch, monkeypatch, tmp_path):
    monkeypatch.setattr(topo_sketch, "rsvg_binary", lambda: sys.executable)

    calls = []

    class _FakeCompleted:
        returncode = 0
        stderr = b""

    def _fake_run(argv, input=None, capture_output=None):
        calls.append((argv, input))
        Path(argv[argv.index("-o") + 1]).write_bytes(b"\x89PNG\r\n")
        return _FakeCompleted()

    monkeypatch.setattr(topo_sketch.subprocess, "run", _fake_run)

    out = tmp_path / "out.png"
    topo_sketch.svg_to_png("<svg>ciao</svg>", out)

    assert out.read_bytes().startswith(b"\x89PNG")
    assert calls[0][1] == b"<svg>ciao</svg>"


def test_svg_to_png_subprocess_fallito_da_errore(topo_sketch, monkeypatch, tmp_path):
    monkeypatch.setattr(topo_sketch, "rsvg_binary", lambda: sys.executable)

    class _FakeCompleted:
        returncode = 1
        stderr = b"boom"

    monkeypatch.setattr(topo_sketch.subprocess, "run", lambda *a, **k: _FakeCompleted())

    with pytest.raises(RuntimeError, match="Conversione SVG->PNG fallita"):
        topo_sketch.svg_to_png("<svg></svg>", tmp_path / "out.png")
