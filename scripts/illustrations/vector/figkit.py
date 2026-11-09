"""figkit: tiny helpers to draw a profile-view athlete as SVG (pure Python + numpy).

World units are metres, x to the right, y up. `Canvas.px()` maps to SVG pixels.
A lateral coordinate L (metres toward the camera) is drawn as a small oblique
shift in x, so near and far limbs separate a little and the wall shows its face.
"""
import math
import numpy as np


def V(x, y):
    return np.array([float(x), float(y)])


def unit(a):
    n = float(np.linalg.norm(a))
    return a / n if n else a


def perp(a):
    """Left normal (world, y up)."""
    return np.array([-a[1], a[0]])


def rot(a, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([c * a[0] - s * a[1], s * a[0] + c * a[1]])


def lerp(a, b, t):
    return a + (b - a) * t


def prof(cps):
    """Smooth 1-D profile through control points [(t, value), ...] (cubic Hermite)."""
    xs = np.array([c[0] for c in cps], float)
    ys = np.array([c[1] for c in cps], float)

    def slope(j):
        if j == 0:
            return (ys[1] - ys[0]) / (xs[1] - xs[0])
        if j == len(xs) - 1:
            return (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        return (ys[j + 1] - ys[j - 1]) / (xs[j + 1] - xs[j - 1])

    def f(t):
        t = min(max(t, xs[0]), xs[-1])
        i = int(min(np.searchsorted(xs, t, side="right") - 1, len(xs) - 2))
        h = xs[i + 1] - xs[i]
        u = (t - xs[i]) / h
        m0, m1 = slope(i), slope(i + 1)
        return ((2 * u**3 - 3 * u**2 + 1) * ys[i] + (u**3 - 2 * u**2 + u) * h * m0
                + (-2 * u**3 + 3 * u**2) * ys[i + 1] + (u**3 - u**2) * h * m1)

    return f


def smooth_closed(pts, corners=(), k=1 / 6):
    """SVG path through pixel points, Catmull-Rom smoothed; indices in `corners` stay sharp."""
    n = len(pts)
    corners = set(c % n for c in corners)
    d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = p1 if i in corners else p1 + (p2 - p0) * k
        c2 = p2 if (i + 1) % n in corners else p2 - (p3 - p1) * k
        d += f" C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {p2[0]:.2f},{p2[1]:.2f}"
    return d + "Z"


def smooth_open(pts, k=1 / 6):
    n = len(pts)
    d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, n - 1)]
        c1 = p1 + (p2 - p0) * k
        c2 = p2 - (p3 - p1) * k
        d += f" C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {p2[0]:.2f},{p2[1]:.2f}"
    return d


def poly(pts):
    return "M" + " L".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts) + "Z"


class Canvas:
    def __init__(self, w, h, scale, gx, gy, kx=0.2):
        self.w, self.h, self.s, self.gx, self.gy, self.kx = w, h, scale, gx, gy, kx
        self.defs = []
        self._ids = [0]

    def sub(self, scale, gx, gy, kx=None):
        """A second coordinate system on the same picture (a small scene inside a detail circle)."""
        c = Canvas(self.w, self.h, scale, gx, gy, self.kx if kx is None else kx)
        c.defs, c._ids = self.defs, self._ids
        return c

    def px(self, p, L=0.0):
        return np.array([self.gx + self.s * (p[0] + self.kx * L), self.gy - self.s * p[1]])

    def pxs(self, pts, L=0.0):
        return [self.px(p, L) for p in pts]

    def uid(self, prefix="i"):
        self._ids[0] += 1
        return f"{prefix}{self._ids[0]}"

    def clip(self, d):
        cid = self.uid("c")
        self.defs.append(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return cid

    def blur(self, std):
        key = f"b{int(round(std * 10))}"
        tag = (f'<filter id="{key}" filterUnits="userSpaceOnUse" x="-100" y="-100" width="{self.w + 200}" '
               f'height="{self.h + 200}"><feGaussianBlur stdDeviation="{std:.2f}"/></filter>')
        if tag not in self.defs:
            self.defs.append(tag)
        return key

    def soft(self, clip_d, strokes):
        """Soft strokes clipped to a shape: strokes = [(path_d, colour, width, blur, opacity), ...]."""
        cid = self.clip(clip_d)
        out = [f'<g clip-path="url(#{cid})">']
        for d, col, w, b, op in strokes:
            flt = f' filter="url(#{self.blur(b)})"' if b > 0 else ""
            out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w:.2f}" '
                       f'stroke-linecap="round" stroke-linejoin="round" opacity="{op}"{flt}/>')
        out.append("</g>")
        return "".join(out)


def centerline(pts, r=0.05, n_seg=8, n_corner=9):
    """A polyline bone with filleted joints, as a dense list of world points."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = unit(b - a), unit(c - b)
        ra = min(r, 0.45 * float(np.linalg.norm(b - a)))
        rc = min(r, 0.45 * float(np.linalg.norm(c - b)))
        p_in, p_out = b - d1 * ra, b + d2 * rc
        start = out[-1]
        for k in range(1, n_seg + 1):
            out.append(lerp(start, p_in, k / n_seg))
        for k in range(1, n_corner + 1):
            t = k / n_corner
            out.append((1 - t) ** 2 * p_in + 2 * (1 - t) * t * b + t**2 * p_out)
    start = out[-1]
    for k in range(1, n_seg + 1):
        out.append(lerp(start, pts[-1], k / n_seg))
    return out


def tube(pts, wl, wr, r=0.05, capn=6, cap0=1.0, cap1=1.0, t0=0.0, t1=1.0):
    """Outline of a limb along a (possibly bent) bone. Returns (outline, centre points, normals, ts)."""
    c = centerline(pts, r=r)
    seg = [float(np.linalg.norm(c[i + 1] - c[i])) for i in range(len(c) - 1)]
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    ts = cum / cum[-1]
    keep = [i for i, t in enumerate(ts) if t0 - 1e-9 <= t <= t1 + 1e-9]
    c = [c[i] for i in keep]
    ts = [float(ts[i]) for i in keep]
    nrm = []
    for i in range(len(c)):
        d = unit(c[min(i + 1, len(c) - 1)] - c[max(i - 1, 0)])
        nrm.append(perp(d))
    left = [c[i] + nrm[i] * wl(ts[i]) for i in range(len(c))]
    right = [c[i] - nrm[i] * wr(ts[i]) for i in range(len(c))]
    pts_out = list(left)
    d1 = unit(c[-1] - c[-2])
    for k in range(1, capn):
        th = math.pi / 2 - math.pi * k / capn
        rr = lerp(wl(ts[-1]), wr(ts[-1]), k / capn)
        pts_out.append(c[-1] + d1 * (rr * math.cos(th) * cap1) + nrm[-1] * (rr * math.sin(th)))
    pts_out += right[::-1]
    d0 = unit(c[1] - c[0])
    for k in range(1, capn):
        th = -math.pi / 2 - math.pi * k / capn
        rr = lerp(wr(ts[0]), wl(ts[0]), k / capn)
        pts_out.append(c[0] + d0 * (rr * math.cos(th) * cap0) + nrm[0] * (rr * math.sin(th)))
    return pts_out, c, nrm, ts


def shaded_tube(cv, pts, wl, wr, base, hi, sh, light=(0.45, 0.89), Ls=None, r=0.05, cap0=1.0, cap1=1.0,
                t0=0.0, t1=1.0, hi_op=0.5, sh_op=0.65, hi_frac=0.5, sh_frac=0.95):
    """Seamless limb: flat fill, soft highlight on the lit side, soft core shadow on the other."""
    if Ls is not None:
        pts = [p + V(cv.kx * L, 0) for p, L in zip(pts, Ls)]
    outline, c, nrm, ts = tube(pts, wl, wr, r=r, cap0=cap0, cap1=cap1, t0=t0, t1=t1)
    d = smooth_closed(cv.pxs(outline))
    mid = len(c) // 2
    lit_left = float(np.dot(nrm[mid], np.array(light))) >= 0
    step = max(1, len(c) // 14)
    idx = list(range(0, len(c), step))
    if idx[-1] != len(c) - 1:
        idx.append(len(c) - 1)

    def offs(side_left, frac):
        return smooth_open(cv.pxs([c[i] + (nrm[i] if side_left else -nrm[i]) * ((wl(ts[i]) if side_left else wr(ts[i])) * frac)
                                   for i in idx]))

    tm = ts[mid]
    wavg = 0.5 * (wl(tm) + wr(tm)) * cv.s
    strokes = [(offs(not lit_left, sh_frac), sh, wavg * 1.05, wavg * 0.36, sh_op),
               (offs(lit_left, hi_frac), hi, wavg * 0.55, wavg * 0.30, hi_op)]
    return f'<path d="{d}" fill="{base}"/>' + cv.soft(d, strokes), d, (c, nrm, ts)
