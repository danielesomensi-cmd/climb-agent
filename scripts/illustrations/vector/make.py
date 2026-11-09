#!/usr/bin/env python3
"""make.py: render the vector plates.

  python3 make.py                      # every plate -> frontend/public/exercises/...
  python3 make.py pistol_squat v_sit   # only these
  python3 make.py --out /tmp/x --png   # write there, keep 2x PNG previews beside the WebP

Needs numpy, Pillow and playwright with Chromium (`pip install playwright && playwright install chromium`).
The SVG is deterministic; the WebP depends on the Chromium and libwebp versions.
"""
import argparse
import io
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[2]
DEFAULT_OUT = REPO / "frontend" / "public" / "exercises"


def render(svgs, scale):
    """{name: svg text} -> {name: PNG bytes} with one headless Chromium."""
    from playwright.sync_api import sync_playwright
    shots = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 800, "height": 400}, device_scale_factor=scale)
        for name, svg in svgs.items():
            pg.set_content(f"<!doctype html><html><body style='margin:0;background:#000'>{svg}</body></html>")
            shots[name] = pg.screenshot(clip={"x": 0, "y": 0, "width": 800, "height": 400})
        b.close()
    return shots


def main():
    import plates
    from PIL import Image, ImageOps
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--png", action="store_true", help="also write a 2x PNG preview")
    ap.add_argument("--svg", action="store_true", help="also write the SVG")
    ap.add_argument("--quality", type=int, default=88)
    a = ap.parse_args()
    names = a.names or list(plates.PLATES)
    out = pathlib.Path(a.out)
    svgs = {n: plates.PLATES[n]["fn"]().svg() for n in names}
    shots = render(svgs, 1)
    big = render(svgs, 2) if a.png else {}
    for n in names:
        spec = plates.PLATES[n]
        dst = out / spec["out"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(shots[n])).convert("RGB")
        im.save(dst, "WEBP", quality=a.quality, method=6)
        files = [dst]
        if spec.get("mirror"):
            left = dst.with_name(dst.stem + "_l.webp")
            ImageOps.mirror(im).save(left, "WEBP", quality=a.quality, method=6)
            files.append(left)
        if a.png:
            dst.with_suffix(".png").write_bytes(big[n])
        if a.svg:
            dst.with_suffix(".svg").write_text(svgs[n])
        print(f"{n:28s} " + "  ".join(f"{f.relative_to(out)} {f.stat().st_size / 1024:.1f} KB" for f in files))


if __name__ == "__main__":
    main()
