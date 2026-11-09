"""athlete.py: a side-view athlete drawn from joint positions (SVG, metres, y up).

The plate computes the joints (hip, shoulder, elbows, wrists, knees, ankles, toes);
this module only draws them, always the same way: flat fill, one soft highlight on the
lit side, one soft core shadow on the other. `facing` is +1 when the athlete faces +x
(image right), -1 when it faces -x. Near limbs are drawn brighter than far ones and a
small lateral offset (toward the camera) keeps the two sides apart.
"""
import math

import numpy as np

from figkit import V, lerp, perp, poly, prof, rot, shaded_tube, smooth_closed, smooth_open, tube, unit

LIGHT = np.array([0.45, 0.89])

# ---------------------------------------------------------------- skeleton (1.66 m)
UPPER_ARM, FOREARM = 0.300, 0.235      # shoulder -> elbow, elbow -> wrist
ARM = UPPER_ARM + FOREARM
GRIP = 0.092                            # wrist -> finger pads hooked on a hold
HAND = 0.172                            # wrist -> fingertips, open hand
THIGH, SHANK, FOOT = 0.407, 0.408, 0.202   # FOOT = ankle joint -> toe tip
FOOT_NEUTRAL = 66.35                    # shin vs ankle->toe with a neutral ankle (degrees)
TORSO = 0.50                            # hip joint -> shoulder joint, arms down (0.54 arms overhead)
A_NAT, T_NAT = V(0.055, 0.075), V(0.240, -0.006)   # ankle joint and toe tip in the foot frame
BALL = V(0.190, -0.002)                 # ball of the foot in the foot frame


def e(deg):
    return V(math.cos(math.radians(deg)), math.sin(math.radians(deg)))


def ang(v):
    return math.degrees(math.atan2(v[1], v[0]))


def dist(a, b):
    return float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float)))


def ik(a, c, l1, l2, side=1):
    """Middle joint of a two-bone chain a -> b -> c. side=+1 puts b on the left of a->c."""
    a, c = np.asarray(a, float), np.asarray(c, float)
    d = c - a
    n = float(np.linalg.norm(d))
    n = min(max(n, abs(l1 - l2) + 1e-6), l1 + l2 - 1e-6)
    u = unit(d)
    x = (l1 * l1 - l2 * l2 + n * n) / (2 * n)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0))
    return a + u * x + perp(u) * (h * side)


def leg_to_toe(hip, toe, plantar=0.0, side=1):
    """Knee and ankle for a leg whose toe tip is at `toe`; the foot is plantar-flexed by `plantar` degrees."""
    off = (FOOT_NEUTRAL - plantar) * side
    b_vec = e(0) * SHANK + e(off) * FOOT
    b, phi = float(np.linalg.norm(b_vec)), ang(b_vec)
    d = np.asarray(toe, float) - np.asarray(hip, float)
    n = min(float(np.linalg.norm(d)), THIGH + b - 1e-6)
    alpha = math.degrees(math.acos((THIGH**2 + n**2 - b**2) / (2 * THIGH * n)))
    knee = np.asarray(hip, float) + e(ang(d) + alpha * side) * THIGH
    sigma = ang(np.asarray(toe, float) - knee) - phi
    return knee, knee + e(sigma) * SHANK


def flat_foot(heel_x, y0, facing=1):
    """Ankle and toe of a foot standing flat on the floor (sole at y0), heel at heel_x."""
    ank = V(heel_x + facing * 0.055, y0 + 0.081)
    return ank, ank + V(facing * 0.185, -0.081)


def foot_on_ball(ball, foot_deg, facing=1):
    """Ankle and (nominal) toe tip of a foot standing on its ball; foot_deg = direction ankle -> toe tip."""
    th = foot_deg - facing * ang(T_NAT - A_NAT)
    v = BALL - A_NAT
    ank = np.asarray(ball, float) - rot(V(v[0], facing * v[1]), th)
    return ank, ank + e(foot_deg) * FOOT


def _half(pts, p0, n):
    """The part of a convex polygon on the side of the line through p0 that its normal n points to."""
    out = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        da, db = float(np.dot(a - p0, n)), float(np.dot(b - p0, n))
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            out.append(a + (b - a) * (da / (da - db)))
    return out


# ---------------------------------------------------------------- looks
LOOKS = {
    "woman": dict(
        build=1.13, fw=1.05, skin=("#D9A17C", "#F5D2B1", "#AC7150"), far_skin=("#B27D5D", "#C69270", "#7E523A"),
        top=("#77848F", "#A6B1BC", "#4B5663"), shorts=("#3E5589", "#6783BB", "#22305A"),
        far_shorts=("#2A3A62", "#384C7B", "#1B2645"), hair=("#4A2F23", "#82583E", "#2E1C15"),
        hair_style="pony", shorts_t=0.225, lips="#9A5746"),
    "man": dict(
        build=1.24, fw=1.13, skin=("#CF9670", "#EDC6A2", "#9F6645"), far_skin=("#A87453", "#BC8865", "#744A33"),
        top=("#5F6C7C", "#8C99A8", "#3B4553"), shorts=("#3E5589", "#6783BB", "#22305A"),
        far_shorts=("#2A3A62", "#384C7B", "#1B2645"), hair=("#2A211E", "#57463D", "#17110F"),
        hair_style="short", shorts_t=0.27, lips="#8A5444"),
}
NEAR_SHOE = ("#6E7986", "#A8B2BD", "#48505C", "#23272F", "#4C535F", "#2FA7A0", "#1F7C77")
FAR_SHOE = ("#566170", "#74808E", "#3A424E", "#2C323D", "#444C59", "#27908A", "#1B6763")
BAG, BAG_HI = "#4C576A", "#6C798F"
WEB, WEB_HI = "#2B3240", "#566078"       # harness webbing

TORSO_F = [(0.070, -0.090), (0.088, 0.020), (0.086, 0.120), (0.078, 0.215), (0.090, 0.305), (0.111, 0.362),
           (0.131, 0.405), (0.114, 0.455), (0.084, 0.500), (0.060, 0.545), (0.028, 0.578), (-0.030, 0.586),
           (-0.086, 0.545), (-0.110, 0.470), (-0.112, 0.380), (-0.094, 0.280), (-0.076, 0.190), (-0.088, 0.100),
           (-0.126, 0.020), (-0.138, -0.050), (-0.114, -0.120), (-0.040, -0.150), (0.030, -0.140)]
TORSO_M = [(0.066, -0.090), (0.082, 0.020), (0.084, 0.120), (0.084, 0.215), (0.092, 0.305), (0.104, 0.365),
           (0.112, 0.420), (0.108, 0.470), (0.090, 0.512), (0.062, 0.548), (0.028, 0.578), (-0.030, 0.586),
           (-0.088, 0.545), (-0.112, 0.470), (-0.114, 0.380), (-0.100, 0.280), (-0.086, 0.190), (-0.090, 0.100),
           (-0.110, 0.020), (-0.118, -0.050), (-0.100, -0.120), (-0.040, -0.150), (0.030, -0.140)]

FACE = [(0.000, 0.106), (0.058, 0.090), (0.084, 0.050), (0.092, 0.020), (0.085, 0.006), (0.098, -0.020),
        (0.113, -0.039), (0.095, -0.049), (0.100, -0.060), (0.093, -0.067), (0.097, -0.075), (0.087, -0.086),
        (0.089, -0.103), (0.070, -0.116), (0.032, -0.106), (-0.020, -0.100), (-0.062, -0.078), (-0.092, -0.030),
        (-0.097, 0.030), (-0.064, 0.088)]
HAIR_CAP = [(0.066, 0.080), (0.036, 0.106), (0.000, 0.116), (-0.066, 0.098), (-0.104, 0.034), (-0.100, -0.034),
            (-0.070, -0.074), (-0.034, -0.050), (-0.020, -0.004), (0.026, 0.032), (0.058, 0.052)]
HAIR_SHORT = [(0.070, 0.074), (0.040, 0.108), (0.000, 0.118), (-0.064, 0.100), (-0.102, 0.036), (-0.098, -0.030),
              (-0.074, -0.062), (-0.046, -0.040), (-0.030, 0.004), (0.004, 0.022), (0.030, 0.048), (0.060, 0.050)]

# hand hooked over a lip or a bar: origin = the grip (finger pads), +y from the wrist toward the knuckles,
# +x the side the fingers curl to. The wrist is at HOOK_WRIST.
HOOK = [(-0.036, -0.097), (-0.045, -0.055), (-0.052, -0.012), (-0.047, 0.020), (-0.028, 0.041), (-0.002, 0.045),
        (0.022, 0.035), (0.036, 0.016), (0.034, -0.002), (0.018, 0.004), (0.000, 0.014), (-0.018, 0.008),
        (-0.026, -0.022), (-0.016, -0.060), (0.018, -0.097)]
HOOK_WRIST = (-0.009, -0.092)
# open, relaxed hand: origin = the wrist, +y toward the fingertips, thumb on +x
OPEN = [(-0.026, 0.000), (-0.031, 0.045), (-0.030, 0.090), (-0.022, 0.135), (-0.008, 0.166), (0.006, 0.170),
        (0.016, 0.148), (0.020, 0.112), (0.027, 0.092), (0.043, 0.086), (0.050, 0.070), (0.040, 0.052),
        (0.028, 0.040), (0.026, 0.000)]
# hand flat on the floor: origin = the floor point under the wrist, fingers toward +x
FLAT = [(-0.030, 0.000), (-0.036, 0.030), (-0.024, 0.062), (0.012, 0.066), (0.058, 0.042), (0.118, 0.026),
        (0.166, 0.016), (0.178, 0.005), (0.170, 0.000)]
FLAT_WRIST = (-0.006, 0.046)
# bare foot in the foot frame (heel at the origin, sole along +x)
BARE = [(0.243, 0.002), (0.238, 0.018), (0.214, 0.030), (0.170, 0.044), (0.128, 0.064), (0.098, 0.088),
        (0.082, 0.108), (0.050, 0.116), (0.018, 0.108), (-0.004, 0.078), (-0.016, 0.040), (-0.010, 0.010),
        (0.012, -0.004), (0.050, 0.000), (0.100, 0.010), (0.150, 0.004), (0.196, -0.004), (0.228, -0.006)]


class Athlete:
    def __init__(self, cv, out, hip, sh, facing=1, look="woman", foot="climb", harness=False, **over):
        self.cv, self.out = cv, out
        self.px, self.pxs = cv.px, cv.pxs
        self.hip, self.sh = np.asarray(hip, float), np.asarray(sh, float)
        self.f = facing
        st = dict(LOOKS[look])
        st.update(over)
        self.st, self.look, self.foot_kind, self.harness = st, look, foot, harness
        self.build = st["build"]
        self.uax = unit(self.sh - self.hip)
        self.fax = V(self.uax[1], -self.uax[0]) * facing
        self.k = dist(self.hip, self.sh) / 0.5415
        self.torso_pts = TORSO_M if look == "man" else TORSO_F
        self.front_lit = float(np.dot(self.fax, LIGHT)) > 0
        b = self.build
        P = lambda cps: (lambda f: (lambda t: f(t) * b))(prof(cps))
        self.ARM_P = P([(0, 0.062), (0.14, 0.058), (0.34, 0.048), (0.52, 0.038), (0.58, 0.037), (0.69, 0.041),
                        (0.86, 0.031), (1, 0.024)])
        self.ARM_A = P([(0, 0.052), (0.17, 0.050), (0.40, 0.043), (0.55, 0.036), (0.60, 0.036), (0.71, 0.041),
                        (0.87, 0.031), (1, 0.025)])
        self.LEG_A = P([(0, 0.092), (0.14, 0.097), (0.32, 0.082), (0.44, 0.063), (0.50, 0.058), (0.56, 0.054),
                        (0.75, 0.041), (1, 0.031)])
        self.LEG_P = P([(0, 0.098), (0.125, 0.094), (0.32, 0.073), (0.45, 0.056), (0.50, 0.054), (0.64, 0.070),
                        (0.80, 0.052), (0.93, 0.035), (1, 0.031)])
        self.NECK = P([(0, 0.049), (1, 0.043)])
        self.head_c, self.pitch, self.hk = None, 0.0, 1.07
        self.paths = {}

    # ------------------------------------------------------------ frames
    def tl(self, f, u):
        """Torso frame: f metres toward the front, u metres up the spine from the hip joint."""
        return self.hip + self.fax * (f * self.st["fw"]) + self.uax * (u * self.k)

    def set_head(self, pitch=0.0, neck=12.0, length=0.130, center=None):
        """pitch: 0 = level gaze, + = looking up. neck: forward lean of the neck from the spine (degrees)."""
        self.pitch = pitch
        nb = self.tl(0.004, 0.578)
        self.head_c = np.asarray(center, float) if center is not None else nb + rot(self.uax, -self.f * neck) * length
        return self

    def hl(self, x, y):
        return self.head_c + rot(V(self.f * x, y) * self.hk, self.f * self.pitch)

    def eye(self):
        return self.hl(0.092, 0.004)

    def _A(self, s):
        self.out.append(s)

    def _sides(self, bones, post_profile, ant_profile, straight=None):
        """(wl, wr, posterior_is_left) for a 2- or 3-point limb: the thicker (posterior) profile goes on the
        inside of the bend; when the limb is straight, on `straight` (True = left) or away from the front."""
        if len(bones) == 3:
            a, b = bones[1] - bones[0], bones[2] - bones[1]
            turn = float(a[0] * b[1] - a[1] * b[0])
        else:
            turn = 0.0
        if abs(turn) > 0.004:
            post_left = turn > 0
        elif straight is not None:
            post_left = straight
        else:
            d = unit(bones[-1] - bones[0])
            post_left = float(np.dot(perp(d), self.fax)) < 0
        return (post_profile, ant_profile, True) if post_left else (ant_profile, post_profile, False)

    # ------------------------------------------------------------ arms
    def arm(self, near, wrist=None, elbow=None, grip=None, hand="hook", curl=1, bend=1, L_hand=None, L_sh=0.17,
            hand_dir=None, hand_k=1.0, lines=True):
        """Draw one arm. Give `grip` (hand hooked on a hold: the wrist is derived) or `wrist`.
        elbow: explicit point, or None = solved from the lengths (bend = which side the elbow goes).
        hand_k < 1 foreshortens an open hand whose fingers curl away from the camera (wrapped round an edge)."""
        s = 1 if near else -1
        skin = self.st["skin"] if near else self.st["far_skin"]
        base, hi, sh_ = skin
        L0 = s * L_sh
        L1 = s * (0.06 if L_hand is None else L_hand)
        if grip is not None:
            # the hooked hand lines up with the forearm, which depends on the elbow: settle both together
            grip = np.asarray(grip, float)
            fixed = elbow is not None
            ref = np.asarray(elbow, float) if fixed else self.sh
            for _ in range(4):
                d = unit(grip - ref)
                xd = V(d[1], -d[0]) * curl
                wrist = grip + xd * HOOK_WRIST[0] + d * HOOK_WRIST[1]
                if fixed or dist(self.sh, wrist) >= ARM - 0.012:
                    break
                elbow = ik(self.sh, wrist, UPPER_ARM, FOREARM, bend)
                ref = elbow
        wrist = np.asarray(wrist, float)
        if elbow is None and dist(self.sh, wrist) < ARM - 0.012:
            elbow = ik(self.sh, wrist, UPPER_ARM, FOREARM, bend)
        bones = [self.sh, wrist] if elbow is None else [self.sh, np.asarray(elbow, float), wrist]
        Ls = [L0, lerp(L0, L1, 0.9)] if len(bones) == 2 else [L0, lerp(L0, L1, 0.5), lerp(L0, L1, 0.9)]
        wl, wr, post_left = self._sides(bones, self.ARM_P, self.ARM_A)
        svg, d_arm, (cc, nn, tt) = shaded_tube(self.cv, bones, wl, wr, base, hi, sh_, Ls=Ls, r=0.05,
                                               hi_op=0.5 if near else 0.2, sh_op=0.6)
        self._A(svg)
        if near and lines:
            sg = 1 if post_left else -1
            tri = smooth_open(self.pxs([cc[i] + nn[i] * (sg * self.ARM_P(tt[i]) * 0.22) for i in range(len(cc))
                                        if 0.06 <= tt[i] <= 0.40]))
            fore = smooth_open(self.pxs([cc[i] + nn[i] * (sg * self.ARM_P(tt[i]) * 0.15) for i in range(len(cc))
                                         if 0.62 <= tt[i] <= 0.88]))
            self._A(self.cv.soft(d_arm, [(tri, sh_, 1.5, 1.0, 0.28), (fore, sh_, 1.2, 0.8, 0.22)]))
        fd = unit(bones[-1] - bones[-2]) if hand_dir is None else unit(np.asarray(hand_dir, float))
        if hand == "hook" and grip is not None:
            self._hook(grip, unit(grip - (bones[-2] if len(bones) == 3 else self.sh)), curl, L1, skin, near)
        elif hand == "open":
            self._open(wrist, fd, curl, L1, skin, near, hand_k)
        elif hand == "flat":
            self._flat(wrist, curl, L1, skin, near)
        self.paths["near_arm" if near else "far_arm"] = d_arm
        return d_arm

    def _hook(self, grip, d, curl, L, skin, near):
        base, hi, sh_ = skin
        xd = V(d[1], -d[0]) * curl
        W = lambda x, y: grip + xd * x + d * y
        hd = smooth_closed(self.pxs([W(x, y) for x, y in HOOK], L))
        self._A(f'<path d="{hd}" fill="{base}"/>')
        knuck = smooth_open(self.pxs([W(-0.046, -0.012), W(-0.041, 0.020), W(-0.024, 0.036), W(0.002, 0.039)], L))
        under = smooth_open(self.pxs([W(0.034, 0.000), W(0.018, 0.006), W(0.000, 0.014), W(-0.018, 0.008),
                                      W(-0.024, -0.030)], L))
        self._A(self.cv.soft(hd, [(under, sh_, 4.0, 1.3, 0.8), (knuck, hi, 3.0, 1.2, 0.5 if near else 0.2)]))
        if near:
            for a0, a1 in [((-0.034, 0.035), (-0.025, 0.014)), ((-0.018, 0.043), (-0.011, 0.022)),
                           ((0.002, 0.044), (0.007, 0.023))]:
                c = self.pxs([W(*a0), W(*a1)], L)
                self._A(f'<path d="M{c[0][0]:.1f},{c[0][1]:.1f} L{c[1][0]:.1f},{c[1][1]:.1f}" stroke="{sh_}" '
                        f'stroke-width="0.8" opacity="0.6" stroke-linecap="round" fill="none"/>')

    def _open(self, wrist, d, side, L, skin, near, k=1.0):
        base, hi, sh_ = skin
        xd = V(d[1], -d[0]) * side
        W = lambda x, y: wrist + xd * x + d * (y * k)
        hd = smooth_closed(self.pxs([W(x, y) for x, y in OPEN], L), corners=(0, 13))
        self._A(f'<path d="{hd}" fill="{base}"/>')
        lit = smooth_open(self.pxs([W(0.004, 0.02), W(0.004, 0.09), W(0.002, 0.15)], L))
        drk = smooth_open(self.pxs([W(-0.026, 0.02), W(-0.028, 0.09), W(-0.016, 0.15)], L))
        self._A(self.cv.soft(hd, [(drk, sh_, 3.2, 1.3, 0.55), (lit, hi, 2.6, 1.2, 0.4 if near else 0.15)]))

    def _flat(self, wrist, side, L, skin, near):
        base, hi, sh_ = skin
        p0 = wrist - V(side * FLAT_WRIST[0], FLAT_WRIST[1])
        W = lambda x, y: p0 + V(side * x, y)
        hd = smooth_closed(self.pxs([W(x, y) for x, y in FLAT], L), corners=(0, 8))
        self._A(f'<path d="{hd}" fill="{base}"/>')
        lit = smooth_open(self.pxs([W(0.0, 0.058), W(0.05, 0.040), W(0.12, 0.022)], L))
        self._A(self.cv.soft(hd, [(lit, hi, 2.4, 1.1, 0.4 if near else 0.15)]))

    @staticmethod
    def flat_wrist(p0, side=1):
        """Wrist joint of a hand lying flat with its heel at floor point p0."""
        return np.asarray(p0, float) + V(side * FLAT_WRIST[0], FLAT_WRIST[1])

    # ------------------------------------------------------------ legs
    def leg(self, near, knee, ankle, toe, L_foot=None, pad=False, toe_bend=0.0):
        s = 1 if near else -1
        st = self.st
        skin = st["skin"] if near else st["far_skin"]
        base, hi, sh_ = skin
        col, hcol, scol = st["shorts"] if near else st["far_shorts"]
        Lf = s * (0.11 if L_foot is None else L_foot)
        L0 = s * 0.085
        bones = [self.hip, np.asarray(knee, float), np.asarray(ankle, float)]
        Ls = [L0, lerp(L0, Lf, 0.5), Lf]
        wl, wr, post_left = self._sides(bones, self.LEG_P, self.LEG_A, straight=(self.f == -1))
        sg = 1 if post_left else -1          # posterior side = sg * normal
        svg, d, (c, nrm, ts) = shaded_tube(self.cv, bones, wl, wr, base, hi, sh_, Ls=Ls, r=0.07,
                                           hi_op=0.5 if near else 0.2, sh_op=0.6)
        self._A(svg)
        if near:
            m = len(c) // 2
            k = self.px(c[m] - nrm[m] * (sg * self.LEG_A(0.5) * 0.55))
            quad = smooth_open(self.pxs([c[i] + nrm[i] * (sg * self.LEG_P(ts[i]) * 0.28) for i in range(len(c))
                                         if 0.22 <= ts[i] <= 0.44]))
            calf = smooth_open(self.pxs([c[i] + nrm[i] * (sg * self.LEG_P(ts[i]) * 0.30) for i in range(len(c))
                                         if 0.58 <= ts[i] <= 0.84]))
            self._A(self.cv.soft(d, [(f"M{k[0] - 3:.1f},{k[1]:.1f} L{k[0] + 3:.1f},{k[1] + 1:.1f}", hi, 5, 2.4, 0.45),
                                     (quad, sh_, 1.6, 1.0, 0.30), (calf, sh_, 1.4, 0.9, 0.28)]))
        if self.foot_kind == "bare":
            self._bare(bones[2], np.asarray(toe, float), Lf, skin, near, toe_bend)
        else:
            self._shoe(bones[2], np.asarray(toe, float), Lf, near)
        # fitted shorts leg
        wa = lambda t: wl(t) + 0.004
        wp = lambda t: wr(t) + 0.004
        shifted = [p + V(self.cv.kx * L, 0) for p, L in zip(bones, Ls)]
        T1 = st["shorts_t"]
        o, c2, n2, t2 = tube(shifted, wa, wp, r=0.07, t1=T1, cap1=0.10)
        sd = smooth_closed(self.pxs(o))
        self._A(f'<path d="{sd}" fill="{col}"/>')
        lit_left = float(np.dot(n2[len(n2) // 2], LIGHT)) >= 0
        w_lit, w_drk, sl = (wa, wp, 1) if lit_left else (wp, wa, -1)
        lit = smooth_open(self.pxs([c2[i] + n2[i] * (sl * w_lit(t2[i]) * 0.45) for i in range(1, len(c2))]))
        drk = smooth_open(self.pxs([c2[i] - n2[i] * (sl * w_drk(t2[i]) * 0.98) for i in range(len(c2))]))
        self._A(self.cv.soft(sd, [(drk, scol, 13, 4.5, 0.9), (lit, hcol, 6, 3.4, 0.5 if near else 0.2)]))
        e1 = c2[-1] + unit(c2[-1] - c2[-2]) * 0.010
        hem = smooth_open(self.pxs([e1 + n2[-1] * wa(T1), e1 - n2[-1] * wp(T1)]))
        self._A(self.cv.soft(d, [(hem, sh_, 3.0, 1.2, 0.5)]))
        if self.harness:      # leg loop
            i0 = min(range(len(t2)), key=lambda i: abs(t2[i] - 0.085))
            a_, b_ = c2[i0] + n2[i0] * (wa(t2[i0]) + 0.004), c2[i0] - n2[i0] * (wp(t2[i0]) + 0.004)
            loop = smooth_open(self.pxs([a_, b_]))
            self._A(self.cv.soft(sd, [(loop, WEB if near else "#20262F", 0.040 * self.cv.s, 0, 1.0),
                                      (loop, WEB_HI, 0.8, 0, 0.5 if near else 0.2)]))
        if pad:                # knee pad: a sleeve cut out of the leg itself, split along the crease of the knee
            up, down = (0.14, 0.06) if pad is True else pad      # metres above / below the knee
            hp, kn, an_ = shifted
            u1, u2 = unit(hp - kn), unit(an_ - kn)
            crease = u1 + u2
            crease = unit(crease) if float(np.linalg.norm(crease)) > 0.05 else perp(u1)
            big = 0.4

            def sleeve(u, length):
                n = perp(u)
                rect = [kn + u * length + n * big, kn + u * length - n * big, kn - u * big - n * big, kn - u * big + n * big]
                h = perp(crease)
                return _half(rect, kn, h if float(np.dot(h, u)) > 0 else -h)

            body = "".join(f'<path d="{poly(self.pxs(q))}" fill="#2B313C" stroke="#2B313C" stroke-width="0.6"/>'
                           for q in (sleeve(u1, up), sleeve(u2, down)) if len(q) >= 3)
            ridge = smooth_open(self.pxs([c[i] - nrm[i] * (sg * self.LEG_A(ts[i]) * 0.45) for i in range(len(ts))
                                          if 0.38 <= ts[i] <= 0.53]))
            self._A(f'<g clip-path="url(#{self.cv.clip(d)})">{body}'
                    f'<path d="{ridge}" fill="none" stroke="#566073" stroke-width="4" stroke-linecap="round" '
                    f'opacity="0.6" filter="url(#{self.cv.blur(2.2)})"/></g>')
        self.paths["near_leg" if near else "far_leg"] = d
        return d

    def _foot_q(self, ank, toe, L, toe_bend=0.0):
        """Map the foot frame onto ankle -> toe. The sole is on the right of that direction when the athlete
        faces +x and on the left when it faces -x. toe_bend lifts the toes about the ball (tiptoe)."""
        k = float(np.linalg.norm(toe - ank) / np.linalg.norm(T_NAT - A_NAT))
        m = self.f
        th = ang(toe - ank) - m * ang(T_NAT - A_NAT)

        def q(x, y):
            p = V(x, y)
            if toe_bend and x > 0.188:
                p = BALL + rot(p - BALL, toe_bend)
            v = p - A_NAT
            return self.px(ank + rot(V(v[0], m * v[1]), th) * k, L)
        return q

    def _shoe(self, ank, toe, L, near, flip=False):
        """Climbing shoe drawn in its own frame (sole along x, heel at the origin) and mapped ankle -> toe."""
        q = self._foot_q(ank, toe, L)
        cv = self.cv
        body = [q(0.240, -0.006), q(0.229, 0.013), q(0.204, 0.030), q(0.165, 0.046), q(0.122, 0.064),
                q(0.092, 0.082), q(0.080, 0.094), q(0.056, 0.100), q(0.030, 0.096), q(0.012, 0.100), q(0.000, 0.072),
                q(-0.005, 0.036), q(0.006, 0.006), q(0.032, -0.003), q(0.070, 0.006), q(0.105, 0.014),
                q(0.140, 0.008), q(0.175, -0.001), q(0.215, -0.009)]
        d = smooth_closed(body, corners=(0,))
        up, hi, sh_, rb, rbh, st, sts = NEAR_SHOE if near else FAR_SHOE
        cid = cv.clip(d)
        upper = [q(0.214, 0.020), q(0.192, 0.010), q(0.160, 0.012), q(0.120, 0.022), q(0.085, 0.022), q(0.058, 0.030),
                 q(0.040, 0.050), q(0.028, 0.075), q(0.024, 0.120), q(0.270, 0.120), q(0.270, 0.030)]
        ud = smooth_closed(upper, corners=(0, 8, 9, 10))
        strap_a = poly([q(0.126, 0.074), q(0.155, 0.060), q(0.166, 0.014), q(0.139, 0.016)])
        strap_b = poly([q(0.090, 0.094), q(0.117, 0.078), q(0.128, 0.019), q(0.102, 0.021)])
        self._A(f'<path d="{d}" fill="{rb}"/>')
        self._A(f'<g clip-path="url(#{cid})"><path d="{ud}" fill="{up}"/>'
                f'<path d="{strap_a}" fill="{st}"/><path d="{strap_b}" fill="{st}"/>'
                f'<path d="{poly([q(0.152, 0.062), q(0.158, 0.059), q(0.168, 0.013), q(0.162, 0.014)])}" fill="{sts}"/>'
                f'<path d="{poly([q(0.114, 0.080), q(0.120, 0.077), q(0.130, 0.018), q(0.124, 0.019)])}" fill="{sts}"/>'
                f'</g>')
        top = smooth_open([q(0.096, 0.074), q(0.125, 0.057), q(0.165, 0.040), q(0.204, 0.024)])
        low = smooth_open([q(0.040, 0.046), q(0.070, 0.030), q(0.120, 0.027), q(0.180, 0.016)])
        toe_spec = smooth_open([q(0.222, 0.012), q(0.232, 0.002)])
        heel_spec = smooth_open([q(0.004, 0.060), q(0.002, 0.030)])
        sole_line = smooth_open([q(0.214, 0.020), q(0.192, 0.010), q(0.160, 0.012), q(0.120, 0.022), q(0.085, 0.022),
                                 q(0.058, 0.030), q(0.040, 0.050), q(0.028, 0.075)])
        self._A(cv.soft(d, [(low, sh_, 4.0, 1.5, 0.75), (top, hi, 2.4, 0.9, 0.8 if near else 0.4),
                            (toe_spec, rbh, 2.0, 0.6, 0.9), (heel_spec, rbh, 2.2, 0.8, 0.8),
                            (sole_line, rbh, 0.8, 0.0, 0.9)]))
        tab = smooth_open([q(0.016, 0.098), q(0.004, 0.118), q(0.022, 0.116), q(0.028, 0.098)])
        self._A(f'<path d="{tab}" stroke="{st}" stroke-width="1.5" fill="none" stroke-linecap="round"/>')

    def _bare(self, ank, toe, L, skin, near, toe_bend=0.0):
        base, hi, sh_ = skin
        q = self._foot_q(ank, toe, L, toe_bend)
        d = smooth_closed([q(x, y) for x, y in BARE])
        self._A(f'<path d="{d}" fill="{base}"/>')
        top = smooth_open([q(0.092, 0.080), q(0.130, 0.056), q(0.175, 0.036), q(0.215, 0.022)])
        sole = smooth_open([q(0.000, 0.004), q(0.060, 0.004), q(0.110, 0.012), q(0.160, 0.006), q(0.225, -0.002)])
        self._A(self.cv.soft(d, [(sole, sh_, 3.6, 1.4, 0.6), (top, hi, 2.6, 1.1, 0.5 if near else 0.2)]))
        if near:
            a_, b_ = q(0.206, 0.024), q(0.212, 0.004)
            self._A(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="{sh_}" stroke-width="0.7" '
                    f'opacity="0.5" stroke-linecap="round" fill="none"/>')

    # ------------------------------------------------------------ torso
    def torso(self, top="auto"):
        st, cv, tl, px = self.st, self.cv, self.tl, self.px
        base, hi, sh_ = st["skin"]
        T = self.torso_pts
        d = smooth_closed([px(tl(f, u)) for f, u in T])
        self._A(f'<path d="{d}" fill="{base}"/>')
        fl = self.front_lit
        back = smooth_open([px(tl(f - 0.002, u)) for f, u in T[12:19]])
        front = smooth_open([px(tl(f - 0.034, u)) for f, u in T[1:9]])
        front_edge = smooth_open([px(tl(f - 0.004, u)) for f, u in T[1:9]])
        back_in = smooth_open([px(tl(f + 0.030, u)) for f, u in T[12:19]])
        absl = smooth_open([px(tl(0.050, 0.310)), px(tl(0.044, 0.240)), px(tl(0.050, 0.170))])
        if fl:
            self._A(cv.soft(d, [(back, sh_, 10, 4.2, 0.6), (front, hi, 8, 3.6, 0.5), (absl, sh_, 1.4, 0.9, 0.26)]))
        else:
            self._A(cv.soft(d, [(front_edge, sh_, 10, 4.2, 0.6), (back_in, hi, 8, 3.6, 0.5),
                                (absl, sh_, 1.4, 0.9, 0.2)]))
        cid = cv.clip(d)
        tcol, thi, tsh = st["top"]
        kind = ("tank" if self.look == "man" else "bra") if top == "auto" else top
        if kind == "bra":
            pts = [px(tl(0.25, 0.328)), px(tl(-0.25, 0.328)), px(tl(-0.25, 0.600)), px(tl(-0.070, 0.600)),
                   px(tl(-0.058, 0.520)), px(tl(-0.030, 0.462)), px(tl(0.012, 0.452)), px(tl(0.048, 0.476)),
                   px(tl(0.080, 0.512)), px(tl(0.25, 0.530))]
            hem_u, corners, sh_rng, hi_rng = 0.328, (0, 1, 2, 3, 9), (12, 15), (4, 9)
        elif kind == "tank":
            pts = [px(tl(0.25, 0.150)), px(tl(-0.25, 0.150)), px(tl(-0.25, 0.600)), px(tl(-0.066, 0.600)),
                   px(tl(-0.056, 0.520)), px(tl(-0.034, 0.445)), px(tl(0.012, 0.428)), px(tl(0.050, 0.462)),
                   px(tl(0.074, 0.520)), px(tl(0.25, 0.545))]
            hem_u, corners, sh_rng, hi_rng = None, (0, 1, 2, 3, 9), (12, 18), (1, 9)
        else:
            pts = None
        if pts is not None:
            self._A(f'<g clip-path="url(#{cid})"><path d="{smooth_closed(pts, corners=corners)}" fill="{tcol}"/></g>')
            tb = smooth_open([px(tl(f + 0.002, u)) for f, u in T[sh_rng[0]:sh_rng[1]]])
            tf = smooth_open([px(tl(f - 0.030, u)) for f, u in T[hi_rng[0]:hi_rng[1]]])
            tfe = smooth_open([px(tl(f - 0.004, u)) for f, u in T[hi_rng[0]:hi_rng[1]]])
            tbi = smooth_open([px(tl(f + 0.030, u)) for f, u in T[sh_rng[0]:sh_rng[1]]])
            strokes = [(tb, tsh, 14, 5, 0.8), (tf, thi, 7, 3.2, 0.6)] if fl else [(tfe, tsh, 14, 5, 0.8), (tbi, thi, 7, 3.2, 0.55)]
            if hem_u is not None:
                strokes += [(smooth_open([px(tl(-0.25, hem_u + 0.006)), px(tl(0.25, hem_u + 0.006))]), tsh, 2.0, 0.5, 0.75),
                            (smooth_open([px(tl(-0.25, hem_u - 0.007)), px(tl(0.25, hem_u - 0.007))]), sh_, 1.6, 0.8, 0.28)]
            self._A(cv.soft(d, strokes))
        scol, shi, ssh = st["shorts"]
        band = poly([px(tl(-0.3, -0.3)), px(tl(0.3, -0.3)), px(tl(0.3, 0.158)), px(tl(-0.3, 0.158))])
        self._A(f'<g clip-path="url(#{cid})"><path d="{band}" fill="{scol}"/></g>')
        sb = smooth_open([px(tl(f + 0.004, u)) for f, u in T[17:21]])
        sf = smooth_open([px(tl(0.050, 0.125)), px(tl(0.056, 0.030)), px(tl(0.045, -0.050))])
        sfe = smooth_open([px(tl(0.084, 0.125)), px(tl(0.086, 0.030)), px(tl(0.070, -0.070))])
        sbi = smooth_open([px(tl(-0.056, 0.110)), px(tl(-0.090, 0.020)), px(tl(-0.096, -0.050))])
        strokes = [(sb, ssh, 15, 5.2, 0.9), (sf, shi, 7, 3.6, 0.45)] if fl else [(sfe, ssh, 14, 5.0, 0.85), (sbi, shi, 7, 3.6, 0.4)]
        strokes += [(smooth_open([px(tl(-0.3, 0.149)), px(tl(0.3, 0.149))]), ssh, 2.4, 0.4, 0.9)]
        if kind != "tank":
            strokes += [(smooth_open([px(tl(-0.3, 0.166)), px(tl(0.3, 0.166))]), sh_, 2.0, 1.0, 0.32)]
        self._A(cv.soft(d, strokes))
        if self.harness:
            belt = smooth_open([px(tl(-0.3, 0.192)), px(tl(0.3, 0.176))])
            self._A(cv.soft(d, [(belt, WEB, 0.050 * cv.s, 0, 1.0), (belt, WEB_HI, 0.9, 0, 0.55)]))
        self.paths["torso"] = d
        return d

    def tie_in(self):
        """Belay loop and knot at the front of the harness; returns the knot point (world)."""
        px, tl = self.px, self.tl
        a_, b_ = tl(0.084, 0.176), tl(0.098, 0.030)
        self._A(f'<path d="{smooth_open([px(a_), px(b_)])}" stroke="{WEB}" stroke-width="{0.022 * self.cv.s:.1f}" '
                f'stroke-linecap="round" fill="none"/>')
        return tl(0.118, 0.105)

    def chalk_bag(self):
        px, tl = self.px, self.tl
        top = tl(-0.088, 0.128)
        c = top + V(-0.050 * self.f, -0.060)
        ax = unit(V(-0.34 * self.f, -1.0))
        nx = perp(ax) * self.f
        q = lambda a, b: px(c + ax * a + nx * b)
        body = [q(-0.050, -0.032), q(-0.054, 0.030), q(-0.020, 0.042), q(0.036, 0.040), q(0.060, 0.018),
                q(0.060, -0.020), q(0.036, -0.041), q(-0.018, -0.043)]
        d = smooth_closed(body)
        self._A(f'<path d="{d}" fill="{BAG}"/>')
        self._A(self.cv.soft(d, [(smooth_open([q(-0.04, -0.040), q(0.03, -0.043), q(0.058, -0.02)]), "#2C3442", 9, 3.2, 0.85),
                                 (smooth_open([q(-0.03, 0.032), q(0.03, 0.036)]), BAG_HI, 4, 2, 0.5)]))
        rim = smooth_open([q(-0.052, -0.032), q(-0.056, 0.029)])
        self._A(f'<path d="{rim}" stroke="{BAG_HI}" stroke-width="2.6" stroke-linecap="round" fill="none"/>')
        self._A(f'<path d="{smooth_open([px(top + V(0.012 * self.f, 0.006)), q(-0.056, 0.004)])}" stroke="#D2D8E0" '
                f'stroke-width="1.0" opacity="0.7" fill="none"/>')

    # ------------------------------------------------------------ head
    def head(self):
        st, cv, px, hl = self.st, self.cv, self.px, self.hl
        if self.head_c is None:
            self.set_head()
        base, hi, sh_ = st["skin"]
        hcol, hhi, _ = st["hair"]
        nb = self.tl(0.004, 0.578)
        nh = hl(-0.012, -0.088)
        svg, _, _ = shaded_tube(cv, [nb, nh], self.NECK, self.NECK, base, hi, sh_, cap0=0.4, cap1=0.4,
                                hi_op=0.25, sh_op=0.5)
        self._A(svg)
        d = smooth_closed([px(hl(x, y)) for x, y in FACE], corners=(6,))
        self._A(f'<path d="{d}" fill="{base}"/>')
        jaw = smooth_open([px(hl(0.066, -0.112)), px(hl(0.030, -0.102)), px(hl(-0.02, -0.096))])
        cheek = smooth_open([px(hl(0.060, 0.044)), px(hl(0.072, 0.004)), px(hl(0.066, -0.040))])
        self._A(cv.soft(d, [(jaw, sh_, 5, 2, 0.65), (cheek, hi, 5, 2.4, 0.55)]))
        eye = [px(hl(0.064, 0.008)), px(hl(0.075, 0.002)), px(hl(0.084, 0.005))]
        brow = [px(hl(0.060, 0.028)), px(hl(0.075, 0.030)), px(hl(0.088, 0.023))]
        self._A(f'<path d="{smooth_open(eye)}" stroke="#36201A" stroke-width="1.5" stroke-linecap="round" fill="none"/>')
        self._A(f'<path d="{smooth_open(brow)}" stroke="{hcol}" stroke-width="1.1" stroke-linecap="round" fill="none" '
                f'opacity="0.85"/>')
        lips = [px(hl(0.083, -0.066)), px(hl(0.094, -0.067))]
        self._A(f'<path d="{smooth_open(lips)}" stroke="{st["lips"]}" stroke-width="1.1" stroke-linecap="round" fill="none"/>')
        cap = HAIR_SHORT if st["hair_style"] == "short" else HAIR_CAP
        hd = smooth_closed([px(hl(x, y)) for x, y in cap])
        self._A(f'<path d="{hd}" fill="{hcol}"/>')
        sheen = smooth_open([px(hl(0.03, 0.094)), px(hl(-0.03, 0.094)), px(hl(-0.078, 0.05))])
        self._A(cv.soft(hd, [(sheen, hhi, 3.5, 1.6, 0.7)]))
        if st["hair_style"] == "short":
            ear = px(hl(-0.006, -0.012))
            self._A(f'<ellipse cx="{ear[0]:.1f}" cy="{ear[1]:.1f}" rx="2.1" ry="3.3" fill="{sh_}" opacity="0.75" '
                    f'transform="rotate({-self.f * self.pitch:.0f} {ear[0]:.1f} {ear[1]:.1f})"/>')
        if st["hair_style"] == "bun":
            b = px(hl(*st.get("bun", (-0.118, 0.052))))
            self._A(f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="{0.040 * cv.s:.1f}" fill="{hcol}"/>')
            self._A(cv.soft(f'M{b[0] - 8:.1f},{b[1]:.1f} a8,8 0 1,0 16,0 a8,8 0 1,0 -16,0',
                            [(f'M{b[0] - 3:.1f},{b[1] - 4:.1f} L{b[0] + 3:.1f},{b[1] - 5:.1f}', hhi, 2.6, 1.2, 0.6)]))
        self.paths["face"], self.paths["hair"] = d, hd
        return d, hd

    def ponytail(self, path=None, length=0.30, widths=None):
        """A ponytail hanging from the back of the head: by default it falls with gravity."""
        if self.st["hair_style"] != "pony":
            return
        hcol, hhi, _ = self.st["hair"]
        if path is None:
            tie = self.hl(-0.092, 0.040)
            back = V(-self.f, 0.0)
            path = [tie, self.hl(-0.108, -0.016)]
            p = path[-1]
            for i, t in enumerate(np.linspace(0, 1, 5)[1:]):
                p = p + back * (0.012 * (1 - t)) + V(0, -length / 4)
                path.append(p)
        n = len(path)
        wid = widths or ([0.018, 0.023] + [lerp(0.025, 0.003, (i / max(n - 3, 1)) ** 1.6) for i in range(n - 2)])
        left, right = [], []
        for i, p in enumerate(path):
            t = unit(path[min(i + 1, n - 1)] - path[max(i - 1, 0)])
            nn = perp(t)
            left.append(p + nn * wid[i])
            right.append(p - nn * wid[i])
        d = smooth_closed(self.pxs(left + right[::-1]))
        self._A(f'<path d="{d}" fill="{hcol}"/>')
        self._A(self.cv.soft(d, [(smooth_open(self.pxs([p + V(0.007 * self.f, 0.0) for p in path[2:n - 1]])),
                                  hhi, 2.6, 1.3, 0.6)]))
