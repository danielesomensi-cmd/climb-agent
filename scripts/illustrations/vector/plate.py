"""plate.py: one 800x400 picture: navy ground, soft spotlight, a scene, and the marks that carry the lesson.

Three layers: `scene` (what the magnified detail repeats), `extra` (drawn over the scene in
the main view only) and `over` (the amber marks: line of sight, ring, detail circle, arrows).
"""
import numpy as np

from figkit import Canvas, unit

BG, SPOT, SPOT_MID = "#1F2633", "#3A4966", "#2A364E"
GUIDE = "#FFC857"


class Plate:
    W, H = 800, 400

    def __init__(self, scale, gx, gy, spot=None, kx=0.2):
        self.cv = Canvas(self.W, self.H, scale, gx, gy, kx)
        self.scene, self.extra, self.over = [], [], []
        cx, cy, r = spot if spot is not None else (gx + 66, 200, 212)
        self.cv.defs.append(
            f'<radialGradient id="spot" gradientUnits="userSpaceOnUse" cx="{cx}" cy="{cy}" r="{r}">'
            f'<stop offset="0" stop-color="{SPOT}"/><stop offset="0.5" stop-color="{SPOT_MID}"/>'
            f'<stop offset="1" stop-color="{BG}"/></radialGradient>')
        self.scene.append(f'<rect width="{self.W}" height="{self.H}" fill="{BG}"/>')
        self.scene.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#spot)"/>')

    # ------------------------------------------------------------ marks
    def ring(self, p, r=16.0, width=2.6):
        self.over.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r}" fill="none" stroke="{GUIDE}" stroke-width="{width}"/>')

    def gaze(self, eye, target, ring=16.0):
        """Dashed line of sight from the eye to a ringed target (pixel points)."""
        eye, target = np.asarray(eye, float), np.asarray(target, float)
        v = unit(target - eye)
        g0, g1 = eye + v * 7, target - v * (ring + 2)
        self.over.append(f'<path d="M{g0[0]:.1f},{g0[1]:.1f} L{g1[0]:.1f},{g1[1]:.1f}" stroke="{GUIDE}" stroke-width="2.6" '
                         f'stroke-dasharray="8 6" stroke-linecap="round" fill="none"/>')
        self.ring(target, ring)

    def dashed(self, a, b, width=2.2):
        self.over.append(f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}" stroke="{GUIDE}" stroke-width="{width}" '
                         f'stroke-dasharray="7 6" stroke-linecap="round" fill="none"/>')

    def arrow(self, a, b, width=2.6, head=9.0, layer=None):
        """A straight amber arrow from a to b (pixel points)."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        v = unit(b - a)
        n = np.array([-v[1], v[0]])
        tip, base = b, b - v * head
        l, r = base + n * head * 0.55, base - n * head * 0.55
        tgt = self.over if layer is None else layer
        tgt.append(f'<path d="M{a[0]:.1f},{a[1]:.1f} L{base[0]:.1f},{base[1]:.1f}" stroke="{GUIDE}" stroke-width="{width}" '
                   f'stroke-linecap="round" fill="none"/>'
                   f'<path d="M{tip[0]:.1f},{tip[1]:.1f} L{l[0]:.1f},{l[1]:.1f} L{r[0]:.1f},{r[1]:.1f}Z" fill="{GUIDE}"/>')

    def bracket(self, a, b, tick=7.0, width=2.2):
        """A measuring bracket between two pixel points (ticks at both ends)."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        v = unit(b - a)
        n = np.array([-v[1], v[0]]) * tick
        self.over.append(
            f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} M{(a - n)[0]:.1f},{(a - n)[1]:.1f} L{(a + n)[0]:.1f},{(a + n)[1]:.1f} '
            f'M{(b - n)[0]:.1f},{(b - n)[1]:.1f} L{(b + n)[0]:.1f},{(b + n)[1]:.1f}" stroke="{GUIDE}" stroke-width="{width}" '
            f'stroke-linecap="round" fill="none"/>')

    def inset(self, focus, center=(628.0, 200.0), radius=118.0, zoom=3.55, ring_at=None, ring=16.0, leader=True,
              mark=True, source="scene", bg=BG):
        """A magnified detail of the scene in a circle. focus = the pixel point shown at the centre.
        ring_at = the spot of the main view the detail comes from: it gets a ring (unless mark=False, when
        something else, like `gaze`, already ringed it) and a thin leader to the circle."""
        IC, focus = np.asarray(center, float), np.asarray(focus, float)
        cid = self.cv.uid("ins")
        self.cv.defs.append(f'<clipPath id="{cid}"><circle cx="{IC[0]}" cy="{IC[1]}" r="{radius}"/></clipPath>')
        if ring_at is not None:
            ring_at = np.asarray(ring_at, float)
            if mark:
                self.ring(ring_at, ring)
            if leader:
                lv = unit(IC - ring_at)
                l0, l1 = ring_at + lv * ring, IC - lv * radius
                self.over.append(f'<path d="M{l0[0]:.1f},{l0[1]:.1f} L{l1[0]:.1f},{l1[1]:.1f}" stroke="{GUIDE}" '
                                 f'stroke-width="1.9" opacity="0.95"/>')
        self.over.append(f'<circle cx="{IC[0]}" cy="{IC[1]}" r="{radius + 6}" fill="#000" opacity="0.30" '
                         f'filter="url(#{self.cv.blur(7)})"/>')
        self.over.append(
            f'<g clip-path="url(#{cid})"><rect x="{IC[0] - radius}" y="{IC[1] - radius}" width="{2 * radius}" '
            f'height="{2 * radius}" fill="{bg}"/><use href="#{source}" transform="translate({IC[0]:.2f} {IC[1]:.2f}) '
            f'scale({zoom}) translate({-focus[0]:.2f} {-focus[1]:.2f})"/></g>')
        self.over.append(f'<circle cx="{IC[0]}" cy="{IC[1]}" r="{radius}" fill="none" stroke="{GUIDE}" stroke-width="2.8"/>')
        return IC, cid

    def panel(self, center=(628.0, 200.0), radius=118.0):
        """An empty detail circle to draw a second small scene in. Returns (clip id, list to append to)."""
        IC = np.asarray(center, float)
        cid = self.cv.uid("pan")
        self.cv.defs.append(f'<clipPath id="{cid}"><circle cx="{IC[0]}" cy="{IC[1]}" r="{radius}"/></clipPath>')
        self._panel = (IC, radius, cid, [])
        return self._panel[3]

    # ------------------------------------------------------------ output
    def svg(self):
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                 f'width="{self.W}" height="{self.H}" viewBox="0 0 {self.W} {self.H}">']
        body = [f'<g id="scene">{"".join(self.scene)}</g><g id="targets">{"".join(self.extra)}</g>']
        if getattr(self, "_panel", None):
            IC, radius, cid, items = self._panel
            body.append(f'<circle cx="{IC[0]}" cy="{IC[1]}" r="{radius + 6}" fill="#000" opacity="0.30" '
                        f'filter="url(#{self.cv.blur(7)})"/>')
            body.append(f'<g clip-path="url(#{cid})">{"".join(items)}</g>')
            body.append(f'<circle cx="{IC[0]}" cy="{IC[1]}" r="{radius}" fill="none" stroke="{GUIDE}" stroke-width="2.8"/>')
        body.append("".join(self.over))
        parts.append("<defs>" + "".join(self.cv.defs) + "</defs>")
        parts.extend(body)
        parts.append("</svg>")
        return "".join(parts)
