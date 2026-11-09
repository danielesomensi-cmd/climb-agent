"""props.py: what the athlete climbs, hangs from or lies on, seen side-on like the athlete.

A wall is described in its own coordinates: `s` metres down the wall from an origin
point on its surface, `o` metres out of it toward the climber. The climber is always on
the left of the wall, facing right. Angle 0 = vertical, + = overhanging.
"""
import math

import numpy as np

from figkit import V, lerp, poly, smooth_closed, smooth_open

HOLD, HOLD_HI, HOLD_SH, HOLD_FAR = "#2FA7A0", "#7ADDD4", "#1A726E", "#1D827D"
WOOD, WOOD_HI, WOOD_SH = "#C9A77A", "#E6CBA3", "#8E6F4A"
STEEL, STEEL_HI, STEEL_SH = "#8D98A8", "#C5CDD8", "#586273"
PAD, PAD_HI, PAD_SH = "#4A566C", "#687690", "#313A4B"
ROPE = "#E8795E"

# the jug of the first plate, measured on its 30 degree wall and stored in wall coordinates
_WD30, _NO30, O_GRIP = V(0.5, -0.8660254), V(-0.8660254, -0.5), 0.0374
_W0 = -_NO30 * O_GRIP


def _xw(y):
    return _W0[0] - 0.5774 * (y - _W0[1])


def _so(p):
    d = np.asarray(p, float) - _W0
    return float(np.dot(d, _WD30)), float(np.dot(d, _NO30))


_JUG = [_so(p) for p in [_W0 + _WD30 * 0.010, V(0.040, -0.012), V(0.018, -0.008), V(-0.002, 0.004), V(-0.017, -0.006),
                         V(-0.020, -0.028), V(-0.008, -0.052), V(0.020, -0.082), V(0.056, -0.108), V(0.092, -0.120),
                         V(_xw(-0.112) - 0.002, -0.118), V(_xw(-0.100), -0.100)]]
_JUG_HI = [_so(p) for p in [V(0.010, -0.004), V(-0.004, -0.004), V(-0.014, -0.012), V(-0.015, -0.028)]]
_JUG_LO = [_so(p) for p in [V(-0.002, -0.056), V(0.026, -0.086), V(0.060, -0.108), V(0.094, -0.118)]]
_JUG_BOLT = _so(V(0.060, -0.072))
_JUG_SH = [_so(V(_xw(-0.08) - 0.004, -0.08)), _so(V(_xw(-0.21) - 0.004, -0.21))]


class Wall:
    def __init__(self, cv, out, origin, angle=0.0, s0=-1.0, s1=1.5, lat=(-0.55, 1.55), slab=0.15, joints=()):
        self.cv, self.out = cv, out
        self.px, self.pxs = cv.px, cv.pxs
        self.o0 = np.asarray(origin, float)
        a = math.radians(angle)
        self.angle = angle
        self.WD = V(math.sin(a), -math.cos(a))
        self.NO = V(-math.cos(a), -math.sin(a))
        self.s0, self.s1, self.lat, self.slab, self.joints = s0, s1, lat, slab, joints

    def at(self, s, o=0.0):
        return self.o0 + self.WD * s + self.NO * o

    def station(self, p):
        """(s, o) of a world point."""
        d = np.asarray(p, float) - self.o0
        return float(np.dot(d, self.WD)), float(np.dot(d, self.NO))

    def _A(self, s):
        self.out.append(s)

    def draw(self):
        cv, px, at = self.cv, self.px, self.at
        s0, s1 = self.s0, self.s1
        Lf, Ln = self.lat
        NI = -self.NO
        face = [px(at(s0), Lf), px(at(s0), Ln), px(at(s1), Ln), px(at(s1), Lf)]
        side = [px(at(s0), Ln), px(at(s0) + NI * self.slab, Ln), px(at(s1) + NI * self.slab, Ln), px(at(s1), Ln)]
        if not any("wface" in d for d in cv.defs):
            cv.defs.append(
                '<linearGradient id="wface" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="400">'
                '<stop offset="0" stop-color="#D8DEE6"/><stop offset="0.5" stop-color="#C2CAD5"/>'
                '<stop offset="1" stop-color="#9DA7B6"/></linearGradient>'
                '<linearGradient id="wside" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="400">'
                '<stop offset="0" stop-color="#5E697B"/><stop offset="1" stop-color="#434C5C"/></linearGradient>')
        fd = poly(face)
        self._A(f'<path d="{poly(side)}" fill="url(#wside)"/>')
        self._A(f'<path d="{fd}" fill="url(#wface)"/>')
        far_edge = smooth_open([px(at(s0), Lf), px(at(s1), Lf)])
        near_edge = smooth_open([px(at(s0), Ln), px(at(s1), Ln)])
        self._A(cv.soft(fd, [(far_edge, "#77828F", 22, 9, 0.5)]))
        self._A(f'<path d="{near_edge}" stroke="#EEF2F7" stroke-width="1.3" opacity="0.95" fill="none"/>')
        dots = []
        for i, s in enumerate(np.arange(s0 + 0.08, s1, 0.26)):
            for L in np.arange(Lf + 0.25 + (0.22 if i % 2 else 0), Ln - 0.1, 0.44):
                p = px(at(s), L)
                dots.append(f'<ellipse cx="{p[0]:.1f}" cy="{p[1]:.1f}" rx="0.7" ry="1.2" '
                            f'transform="rotate({self.angle:.0f} {p[0]:.1f} {p[1]:.1f})"/>')
        self._A(f'<g fill="#566172" opacity="0.36">{"".join(dots)}</g>')
        for sj in self.joints:
            a_, b_ = px(at(sj), Lf), px(at(sj), Ln)
            c_ = px(at(sj) + NI * self.slab, Ln)
            self._A(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="#8792A2" stroke-width="1" opacity="0.75"/>'
                    f'<path d="M{b_[0]:.1f},{b_[1]:.1f} L{c_[0]:.1f},{c_[1]:.1f}" stroke="#39414F" stroke-width="1" opacity="0.8"/>')

    def _clear(self, p, min_o=0.004):
        """Keep a point of a hold on the climber's side of the wall surface."""
        s, o = self.station(p)
        return self.at(s, max(o, min_o))

    def foothold(self, s, L, w=0.034, out=None):
        """A small positive foothold: level top, rounded nose, compact body back to the wall.
        Returns the point of its top where a toe tip rests."""
        cv, px, pxs, at = self.cv, self.px, self.pxs, self.at
        A = self._A if out is None else out.append
        ln = 1.6 * w
        r = at(s)
        pr = [at(s - 0.008), r + V(-w * 0.50, 0.004), r + V(-w * 0.96, -0.001), r + V(-w - 0.004, -0.014),
              r + V(-w * 0.82, -0.034), self._clear(r + V(-w * 0.42, -ln * 0.72)), self._clear(r + V(0.004, -ln * 0.84)),
              at(s + ln)]
        sh = [px(at(s + ln * 0.5, 0.004), L), px(at(s + ln * 2.1, 0.004), L)]
        A(f'<path d="{smooth_open(sh)}" stroke="#4A5566" stroke-width="{w * cv.s * 1.0:.1f}" stroke-linecap="round" '
          f'opacity="0.42" filter="url(#{cv.blur(2.6)})"/>')
        d = smooth_closed(pxs(pr, L), corners=(0, 7))
        A(f'<path d="{d}" fill="{HOLD}"/>')
        hi = smooth_open(pxs([r + V(-w * 0.20, -0.005), r + V(-w * 0.78, -0.007), r + V(-w * 0.90, -0.018)], L))
        lo = smooth_open(pxs([r + V(-w * 0.70, -0.040), self._clear(r + V(-w * 0.30, -ln * 0.76), 0.008),
                              at(s + ln, 0.010)], L))
        A(cv.soft(d, [(lo, HOLD_SH, w * cv.s * 0.8, 1.6, 0.9), (hi, HOLD_HI, 2.0, 0.6, 0.95)]))
        b = px(self._clear(r + V(-w * 0.28, -ln * 0.38), 0.008), L)
        A(f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="{max(0.8, w * cv.s * 0.12):.2f}" fill="{HOLD_SH}"/>')
        return r + V(-w * 0.43, 0.006)

    def grip(self, s, scale=1.0):
        """Where the finger pads sit on a jug bolted at station s."""
        return self.at(s, O_GRIP * scale)

    def jug(self, s, part, L=0.06, L_far=-0.16, scale=1.0):
        """One incut jug at station s (the station of its grip). part: 'far' (shadow and far cheek,
        drawn before the far hand) or 'near' (the body, drawn after it)."""
        cv, px = self.cv, self.px
        W = lambda so, LL: px(self.at(s + so[0] * scale, so[1] * scale), LL)
        if part == "far":
            sh = [W(p, 0.0) for p in _JUG_SH]
            self._A(f'<path d="{smooth_open(sh)}" stroke="#4A5566" stroke-width="{20 * scale * cv.s / 153:.1f}" '
                    f'stroke-linecap="round" opacity="0.38" filter="url(#{cv.blur(5)})"/>')
            self._A(f'<path d="{smooth_closed([W(p, L_far) for p in _JUG], corners=(0, 11))}" fill="{HOLD_FAR}"/>')
            return self.grip(s, scale)
        d = smooth_closed([W(p, L) for p in _JUG], corners=(0, 11))
        self._A(f'<path d="{d}" fill="{HOLD}"/>')
        hi = smooth_open([W(p, L) for p in _JUG_HI])
        lo = smooth_open([W(p, L) for p in _JUG_LO])
        k = scale * cv.s / 153
        self._A(cv.soft(d, [(lo, HOLD_SH, 9 * k, 2.6, 0.95), (hi, HOLD_HI, 3.0 * k, 1.0, 0.95)]))
        b = W(_JUG_BOLT, L)
        self._A(f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="{2.3 * k:.1f}" fill="{HOLD_SH}"/>')
        return self.grip(s, scale)

    def block(self, s_a, s_b, depth, L=0.0, width=0.5):
        """A big blocky hold (a volume) between stations s_a < s_b, `depth` metres deep and `width` wide,
        centred at lateral L. The camera sees its near cheek and, beyond it, the upper face and the outer
        face; the lower face (what a knee locks under) looks away from the camera."""
        cv, px, at = self.cv, self.px, self.at
        L0, L1 = L - width / 2, L + width / 2
        r = 0.022
        prof_ = [at(s_a, 0), at(s_a + 0.02, depth - r), at(s_a + 0.02 + r, depth), at(s_b - r, depth),
                 at(s_b, depth - r), at(s_b, 0)]
        sh = [px(at(s_b + 0.04, 0.004), L), px(at(s_b + 0.34, 0.004), L)]
        self._A(f'<path d="{smooth_open(sh)}" stroke="#4A5566" stroke-width="{depth * cv.s * 1.2:.1f}" '
                f'stroke-linecap="round" opacity="0.36" filter="url(#{cv.blur(6)})"/>')
        sweep = lambda i, j: poly([px(p, L0) for p in prof_[i:j + 1]] + [px(p, L1) for p in reversed(prof_[i:j + 1])])
        self._A(f'<path d="{sweep(2, 4)}" fill="{HOLD_FAR}"/>')        # outer face, in shade
        self._A(f'<path d="{sweep(0, 2)}" fill="#5CC7BE"/>')           # upper face, lit
        d = smooth_closed([px(p, L1) for p in prof_], corners=(0, 5), k=0.12)
        self._A(f'<path d="{d}" fill="{HOLD}"/>')
        hi = smooth_open([px(at(s_a + 0.035, depth * 0.35), L1), px(at(s_a + 0.045, depth - 0.016), L1),
                          px(at(lerp(s_a, s_b, 0.5), depth - 0.010), L1)])
        lo = smooth_open([px(at(s_b - 0.012, depth * 0.85), L1), px(at(s_b - 0.010, depth * 0.15), L1)])
        self._A(cv.soft(d, [(lo, HOLD_SH, depth * cv.s * 0.30, 3.2, 0.9), (hi, HOLD_HI, 2.6, 1.2, 0.7)]))
        for f in (0.28, 0.72):
            b = px(at(lerp(s_a, s_b, f), depth * 0.42), L1)
            self._A(f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="1.8" fill="{HOLD_SH}"/>')


# ---------------------------------------------------------------- gym props
def floor_mat(cv, out, x0, x1, y=0.0, lat=(-0.45, 0.95), color="#3A455A", edge="#566178", thick=0.035):
    """An exercise mat lying on the floor, its top surface at height y."""
    px = cv.px
    top = [px(V(x0, y), lat[0]), px(V(x1, y), lat[0]), px(V(x1, y), lat[1]), px(V(x0, y), lat[1])]
    front = [px(V(x0, y), lat[1]), px(V(x1, y), lat[1]), px(V(x1, y - thick), lat[1]), px(V(x0, y - thick), lat[1])]
    c = px(V((x0 + x1) / 2, y - thick), lerp(lat[0], lat[1], 0.6))
    out.append(f'<ellipse cx="{c[0]:.1f}" cy="{c[1] + 6:.1f}" rx="{(x1 - x0) * cv.s * 0.56:.1f}" ry="11" fill="#0E131C" '
               f'opacity="0.5" filter="url(#{cv.blur(7)})"/>')
    out.append(f'<path d="{poly(front)}" fill="#2B3445"/>')
    out.append(f'<path d="{poly(top)}" fill="{color}"/>')
    out.append(f'<path d="M{top[3][0]:.1f},{top[3][1]:.1f} L{top[2][0]:.1f},{top[2][1]:.1f}" stroke="{edge}" stroke-width="1"/>')


def contact_shadow(cv, out, x0, x1, y=0.0, L=0.25, op=0.45):
    c = cv.px(V((x0 + x1) / 2, y), L)
    out.append(f'<ellipse cx="{c[0]:.1f}" cy="{c[1]:.1f}" rx="{(x1 - x0) * cv.s / 2:.1f}" ry="5.5" fill="#10151E" '
               f'opacity="{op}" filter="url(#{cv.blur(3.5)})"/>')


def bench(cv, out, x0, x1, top=0.45, lat=(-0.16, 0.16), pad=0.07):
    """A flat training bench: padded top between x0 and x1 at height `top`, two legs."""
    px = cv.px
    for xl in (x0 + 0.16, x1 - 0.16):
        for L, col in ((lat[0], STEEL_SH), (lat[1], STEEL)):
            a_, b_ = px(V(xl, top - pad), L), px(V(xl, 0.0), L)
            out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="{col}" stroke-width="5" stroke-linecap="round"/>')
        a_, b_ = px(V(xl, 0.0), lat[0] - 0.08), px(V(xl, 0.0), lat[1] + 0.08)
        out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="{STEEL}" stroke-width="5" stroke-linecap="round"/>')
    topf = [px(V(x0, top), lat[0]), px(V(x1, top), lat[0]), px(V(x1, top), lat[1]), px(V(x0, top), lat[1])]
    front = [px(V(x0, top), lat[1]), px(V(x1, top), lat[1]), px(V(x1, top - pad), lat[1]), px(V(x0, top - pad), lat[1])]
    end = [px(V(x0, top), lat[0]), px(V(x0, top), lat[1]), px(V(x0, top - pad), lat[1]), px(V(x0, top - pad), lat[0])]
    out.append(f'<path d="{poly(end)}" fill="{PAD_SH}" stroke="{PAD_SH}" stroke-width="3" stroke-linejoin="round"/>')
    out.append(f'<path d="{poly(front)}" fill="{PAD}" stroke="{PAD}" stroke-width="3" stroke-linejoin="round"/>')
    out.append(f'<path d="{poly(topf)}" fill="{PAD_HI}" stroke="{PAD_HI}" stroke-width="3" stroke-linejoin="round"/>')
    lo = smooth_open([front[3], front[2]])
    out.append(cv.soft(poly(front), [(lo, PAD_SH, 6, 2.5, 0.8)]))


def ring(cv, out, c, L, r=0.095, top=None, near=True):
    """A gymnastics ring seen face-on, hanging from a strap that leaves the picture at `top`."""
    p = cv.px(c, L)
    R = r * cv.s
    if top is not None:
        a_, b_ = cv.px(V(c[0], c[1] + r), L), cv.px(top, L)
        out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="{"#C9CED6" if near else "#8A93A1"}" '
                   f'stroke-width="{0.030 * cv.s:.1f}"/>')
    col, hi = (WOOD, WOOD_HI) if near else (WOOD_SH, WOOD)
    out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{R:.1f}" fill="none" stroke="{col}" stroke-width="{0.028 * cv.s:.1f}"/>')
    out.append(f'<path d="M{p[0] - R * 0.7:.1f},{p[1] - R * 0.7:.1f} A{R:.1f},{R:.1f} 0 0 1 {p[0] + R * 0.7:.1f},{p[1] - R * 0.7:.1f}" '
               f'fill="none" stroke="{hi}" stroke-width="1.6" opacity="{0.8 if near else 0.35}"/>')


def rope(cv, out, pts, L=0.0, width=0.011, color=ROPE):
    """A rope through world points; L is one lateral offset or one per point."""
    Ls = L if isinstance(L, (list, tuple)) else [L] * len(pts)
    d = smooth_open([cv.px(p, l) for p, l in zip(pts, Ls)])
    out.append(f'<path d="{d}" stroke="#7E3B2E" stroke-width="{width * cv.s + 1.2:.1f}" stroke-linecap="round" '
               f'stroke-linejoin="round" fill="none" opacity="0.55"/>')
    out.append(f'<path d="{d}" stroke="{color}" stroke-width="{width * cv.s:.1f}" stroke-linecap="round" '
               f'stroke-linejoin="round" fill="none"/>')


def quickdraw(cv, out, bolt, L=0.3, length=0.17):
    """A quickdraw hanging plumb from a bolt hanger on the wall. Returns the point where the rope runs."""
    px = cv.px
    top = np.asarray(bolt, float) + V(-0.022, -0.030)
    bot = top + V(0, -length)
    h = px(bolt, L)
    out.append(f'<rect x="{h[0] - 4:.1f}" y="{h[1] - 2.5:.1f}" width="7" height="6.5" rx="1.5" fill="{STEEL}"/>')
    out.append(f'<circle cx="{h[0] - 0.5:.1f}" cy="{h[1] + 0.8:.1f}" r="1.5" fill="{STEEL_SH}"/>')

    def biner(c, col):
        p = px(c, L)
        out.append(f'<rect x="{p[0] - 3.4:.1f}" y="{p[1] - 5.6:.1f}" width="6.8" height="11.2" rx="3.2" fill="none" '
                   f'stroke="{col}" stroke-width="1.7"/>')

    a_, b_ = px(top + V(0, -0.030), L), px(bot + V(0, 0.030), L)
    out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="#2B3240" stroke-width="3.6" stroke-linecap="round"/>')
    out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="#F0B24A" stroke-width="1.1" opacity="0.9"/>')
    biner(top, STEEL_HI)
    biner(bot, STEEL_HI)
    return bot + V(0, -0.012)
