"""plates.py: one function per picture. Each returns a Plate; `make.py` renders them.

Poses are written in metres. Every plate states where its pose comes from (a verified
pose file or the catalog cues) so a reviewer can check the drawing against it.
"""
import numpy as np

from athlete import ARM, FOOT, FOOT_NEUTRAL, SHANK, THIGH, Athlete, e, flat_foot, foot_on_ball, ik, leg_to_toe
from figkit import V, lerp, poly, smooth_closed, smooth_open
from plate import Plate
from props import Wall, bench, contact_shadow, floor_mat, quickdraw, ring, rope


def hard_target(clean=False):
    """tech_hard_target. Pose: scripts/illustrations/poses/hard_target.json (v5), camera moved to a true
    profile: 30 degree overhang, hands matched on one jug, arms straight, body plumb, the near toe on a
    foothold about 29 cm below the hip, the far leg free, eyes on the toe."""
    pl = Plate(153.0, 318 if clean else 150, 43,
               spot=(400, 200, 215) if clean else (216, 200, 212))
    cv, out = pl.cv, pl.scene
    G, SH, HIP = V(0, 0), V(-0.035, -0.625), V(-0.075, -1.165)
    TOE = HIP + e(-17.3) * 0.990
    KNEE, ANK = leg_to_toe(HIP, TOE, plantar=52)
    FKNEE = HIP + V(0.026, -0.406)
    FANK = FKNEE + V(-0.014, -0.408)
    FTOE = FANK + e(-92 + FOOT_NEUTRAL - 36) * FOOT
    wall = Wall(cv, out, TOE + V(0.019, -0.006), angle=30)
    sg = wall.station(G)[0]
    wall.s0, wall.s1, wall.joints = sg - 0.6, 1.3, (sg + 0.56, sg + 2.22)
    wall.draw()
    wall.foothold(0.0, 0.12, 0.044)
    wall.jug(sg, "far")
    fig = Athlete(cv, out, HIP, SH).set_head(pitch=-38.0, center=V(0.078, -0.508))
    fig.arm(False, grip=G)
    wall.jug(sg, "near")
    fig.leg(False, FKNEE, FANK, FTOE, L_foot=0.09)
    fig.chalk_bag()
    face_d, hair_d = fig.head()
    torso_d = fig.torso()
    fig.leg(True, KNEE, ANK, TOE, L_foot=0.12)
    hl, tl = fig.hl, fig.tl
    fig.ponytail(path=[hl(-0.092, 0.040), hl(-0.105, -0.020), tl(-0.094, 0.565), tl(-0.124, 0.500),
                       tl(-0.130, 0.420), tl(-0.128, 0.350), tl(-0.136, 0.300)],
                 widths=[0.018, 0.023, 0.025, 0.024, 0.021, 0.014, 0.003])
    # the near arm throws a soft shadow on what it crosses
    skin_sh, hair_sh = fig.st["skin"][2], fig.st["hair"][2]
    edge = smooth_open(cv.pxs([SH + V(0.060, -0.02), lerp(SH, G, 0.25) + V(0.058, 0), lerp(SH, G, 0.5) + V(0.046, 0)], 0.136))
    out.append(cv.soft(face_d, [(edge, skin_sh, 7, 2.6, 0.55)]))
    out.append(cv.soft(hair_d, [(edge, hair_sh, 7, 2.6, 0.7)]))
    pit = smooth_open(cv.pxs([SH + V(-0.050, -0.070), SH + V(0.0, -0.082), SH + V(0.050, -0.062)], 0.136))
    out.append(cv.soft(torso_d, [(pit, "#39424E", 6, 3.0, 0.45)]))
    fig.arm(True, grip=G)
    # next targets: between hip height and mid-thigh height, clear of the working leg and of the line of sight
    for s_, L_, w_ in [(-0.160, 1.40, 0.028), (-0.200, 0.74, 0.034), (-0.245, 1.12, 0.030),
                       (-0.290, 0.60, 0.032), (-0.330, 1.42, 0.028), (-0.370, 0.96, 0.030)]:
        wall.foothold(s_, L_, w_, out=pl.extra)
    if not clean:
        toe_px = cv.px(TOE, 0.12)
        pl.gaze(cv.px(fig.eye()), toe_px)
        pl.inset(toe_px + np.array([-17.0, -2.0]), ring_at=toe_px, mark=False)
    return pl


def _centred(scale, x_mid, y_base=0.0, base_px=356.0):
    """A plate without a detail circle: world point (x_mid, y_base) sits at pixel (400, base_px)."""
    return Plate(scale, 400 - scale * x_mid, base_px + scale * y_base, spot=(400, 205, 215))


def v_sit(leg_deg=78.0):
    """v_sit / v_sit_45 (floor compression ladder). Cues: push the shoulders down and lean back, arms locked,
    legs as close to the face as you can hold; the hips hover just off the floor."""
    S = 285.0
    pl = _centred(S, 0.07, base_px=360)
    cv, out = pl.cv, pl.scene
    floor_mat(cv, out, -0.62, 0.80)
    SH = V(-0.13, 0.565)
    HIP = SH + e(-51.0) * 0.50
    KNEE = HIP + e(leg_deg) * THIGH
    ANK = KNEE + e(leg_deg - 2) * SHANK
    TOE = ANK + e(leg_deg + 8) * FOOT
    FK = HIP + e(leg_deg - 5) * THIGH
    FA = FK + e(leg_deg - 6) * SHANK
    FT = FA + e(leg_deg + 4) * FOOT
    fig = Athlete(cv, out, HIP, SH, look="man", foot="bare").set_head(pitch=16.0, neck=14.0)
    fig.arm(False, wrist=Athlete.flat_wrist(V(0.035, 0.0)), hand="flat", L_hand=0.17)
    fig.leg(False, FK, FA, FT, L_foot=0.07)
    fig.head()
    fig.torso()
    fig.leg(True, KNEE, ANK, TOE, L_foot=0.07)
    fig.arm(True, wrist=Athlete.flat_wrist(V(0.0, 0.0)), hand="flat", L_hand=0.17)
    return pl


def elevated_pike_pushup():
    """elevated_pike_pushup. Cues: feet on a bench, hips over the shoulders, head goes in front of the hands,
    elbows at 45 degrees. Drawn near the bottom of the repetition."""
    S = 262.0
    pl = _centred(S, 0.50, base_px=356)
    cv, out = pl.cv, pl.scene
    floor_mat(cv, out, -0.52, 0.42)
    bench(cv, out, 0.62, 1.42, top=0.46)
    HIP = V(0.002, 0.888)
    SH = HIP + e(250.0) * 0.50
    fig = Athlete(cv, out, HIP, SH, facing=-1, look="woman", foot="bare", hair_style="bun")
    fig.set_head(pitch=210.0, center=SH + V(-0.085, -0.135))
    an, tn = foot_on_ball(V(0.80, 0.462), -84.0, facing=-1)
    af, tf = foot_on_ball(V(0.845, 0.462), -80.0, facing=-1)
    fig.arm(False, wrist=Athlete.flat_wrist(V(0.03, 0.0), -1), hand="flat", curl=-1, bend=1, L_hand=0.17)
    fig.leg(False, ik(HIP, af, THIGH, SHANK, -1), af, tf, L_foot=0.07, toe_bend=92)
    fig.head()
    fig.torso()
    fig.leg(True, ik(HIP, an, THIGH, SHANK, -1), an, tn, L_foot=0.07, toe_bend=92)
    fig.arm(True, wrist=Athlete.flat_wrist(V(0.0, 0.0), -1), hand="flat", curl=-1, bend=1, L_hand=0.17)
    return pl


def _high(a, c, l1=0.300, l2=0.235):
    """The bend side that puts the middle joint of a -> c higher."""
    return max((1, -1), key=lambda b: ik(a, c, l1, l2, b)[1])


def _low(a, c, l1=0.300, l2=0.235):
    """The bend side that lets the middle joint of a -> c hang lower (a relaxed elbow)."""
    return min((1, -1), key=lambda b: ik(a, c, l1, l2, b)[1])


def dragon_flag_tuck():
    """dragon_flag_tuck / dragon_flag_tuck_negative / circuit ce_dragon_flag_tuck. Cues: hands grip the bench
    behind the head, weight on the shoulder blades (never the neck), hips in line with the shoulders, knees tucked."""
    S = 236.0
    pl = _centred(S, 0.02, base_px=376)
    cv, out = pl.cv, pl.scene
    x0, top = -0.53, 0.46
    contact_shadow(cv, out, x0 - 0.04, 0.72, L=0.0, op=0.5)
    bench(cv, out, x0, 0.68, top=top)
    SH = V(0.0, 0.565)
    HIP = SH + e(48.0) * 0.50
    KNEE = HIP + e(142.0) * THIGH
    ANK = KNEE + e(24.0) * SHANK
    TOE = ANK + e(56.0) * FOOT
    FK = HIP + e(136.0) * THIGH
    FA = FK + e(19.0) * SHANK
    FT = FA + e(50.0) * FOOT
    fig = Athlete(cv, out, HIP, SH, look="woman", foot="bare", hair_style="bun", bun=(-0.050, 0.126))
    fig.set_head(pitch=84.0, center=V(-0.200, 0.578))
    w = V(x0 + 0.012, top + 0.040)                      # wrist over the end of the bench, fingers wrapped round it
    fig.arm(False, wrist=w, bend=_high(SH, w), hand="open", hand_dir=e(262.0), hand_k=0.62, L_hand=0.10)
    fig.leg(False, FK, FA, FT, L_foot=0.07)
    fig.head()
    fig.torso()
    fig.leg(True, KNEE, ANK, TOE, L_foot=0.07)
    fig.arm(True, wrist=w, bend=_high(SH, w), hand="open", hand_dir=e(262.0), hand_k=0.62, L_hand=0.10)
    return pl


def ring_fallout():
    """ring_fallout. Cues: hollow body (ribs down, glutes squeezed), arms go forward and overhead, hips follow,
    come back before the lower back sags. From the feet, rings low."""
    S = 300.0
    pl = _centred(S, 0.84, base_px=356)
    cv, out = pl.cv, pl.scene
    floor_mat(cv, out, -0.28, 1.86)
    an, tn = foot_on_ball(V(0.0, 0.004), -81.0)
    af, tf = foot_on_ball(V(0.045, 0.004), -78.0)
    HIP = an + e(33.0) * 0.805
    SH = HIP + e(25.0) * 0.52
    RC = SH + e(4.0) * (ARM + 0.092) + V(0.0, 0.095 + 0.012)       # ring centre: the hand wraps its lowest arc
    grip = RC + V(0.0, -0.095 - 0.012)
    top = RC + V(-0.30, 1.60)
    fig = Athlete(cv, out, HIP, SH, look="man", foot="bare").set_head(pitch=-34.0, neck=30.0)
    ring(cv, out, RC, -0.17, top=top, near=False)
    fig.arm(False, grip=grip, curl=1, L_hand=0.17)
    fig.leg(False, ik(HIP, af, THIGH, SHANK, 1), af, tf, L_foot=0.07, toe_bend=78)
    fig.head()
    fig.torso()
    fig.leg(True, ik(HIP, an, THIGH, SHANK, 1), an, tn, L_foot=0.07, toe_bend=81)
    ring(cv, out, RC, 0.17, top=top, near=True)
    fig.arm(True, grip=grip, curl=1, L_hand=0.17)
    return pl


def pistol_squat():
    """pistol_squat. Cues: free leg straight, full depth with control, stand without bouncing. The bottom of the
    repetition: heel down, hip below the knee, arms forward as a counterweight."""
    S = 300.0
    pl = _centred(S, 0.36, base_px=356)
    cv, out = pl.cv, pl.scene
    floor_mat(cv, out, -0.50, 1.20)
    an, tn = flat_foot(0.0, 0.0)
    KNEE = an + e(56.0) * SHANK
    HIP = KNEE + e(203.0) * THIGH
    SH = HIP + e(50.0) * 0.50
    FK = HIP + e(7.0) * THIGH
    FA = FK + e(5.0) * SHANK
    FT = FA + e(5.0 + FOOT_NEUTRAL - 22.0) * FOOT
    fig = Athlete(cv, out, HIP, SH, look="woman", foot="bare", hair_style="bun").set_head(pitch=-4.0, neck=30.0)
    fig.arm(False, wrist=SH + e(7.0) * ARM, hand="open", L_hand=0.17)
    fig.leg(False, FK, FA, FT, L_foot=0.09)
    fig.head()
    fig.torso()
    fig.leg(True, KNEE, an, tn, L_foot=0.07)
    fig.arm(True, wrist=SH + e(3.0) * ARM, hand="open", L_hand=0.17)
    return pl


# ------------------------------------------------------------------ climbing plates
def _outward(wall, a, c, l1=0.300, l2=0.235):
    """The bend side that keeps the middle joint of a -> c on the climber's side of the wall."""
    return max((1, -1), key=lambda b: wall.station(ik(a, c, l1, l2, b))[1])


def glued_feet():
    """glued_feet_board (and tech_talon_feet: same position). Cues: a cut foot ends the attempt, pull with the
    toes, press with the hips. Steep board, body long, both feet on, hips held up to the wall."""
    S = 176.0
    pl = Plate(S, 100, 44, spot=(236, 200, 212))
    cv, out = pl.cv, pl.scene
    wall = Wall(cv, out, V(0, 0), angle=40.0, s0=-0.45, s1=2.6, joints=(0.62, 1.72))
    wall.draw()
    toe_n = wall.foothold(2.00, 0.14, 0.042) + V(0.010, -0.003)
    toe_f = wall.foothold(1.92, -0.14, 0.038) + V(0.010, -0.003)
    wall.foothold(1.42, 1.15, 0.030)
    wall.foothold(1.05, 0.70, 0.030)
    SH, HIP = wall.at(0.56, 0.30), wall.at(1.05, 0.34)
    g_top = wall.jug(0.0, "far", L_far=-0.30)
    wall.jug(0.52, "far", L_far=-0.04, scale=0.9)
    fig = Athlete(cv, out, HIP, SH, look="man").set_head(pitch=48.0, neck=6.0)
    fig.arm(False, grip=g_top, L_hand=0.12)
    wall.jug(0.0, "near", L=-0.08)
    fk, fa = leg_to_toe(HIP, toe_f, plantar=52)
    fig.leg(False, fk, fa, toe_f, L_foot=0.14)
    fig.chalk_bag()
    fig.head()
    fig.torso()
    nk, na = leg_to_toe(HIP, toe_n, plantar=54)
    fig.leg(True, nk, na, toe_n, L_foot=0.14)
    wall.jug(0.52, "near", L=0.16, scale=0.9)
    g_lo = wall.grip(0.52, 0.9)
    fig.arm(True, grip=g_lo, bend=_low(SH, g_lo), L_hand=0.15)
    toe_px = cv.px(toe_n, 0.14)
    pl.inset(toe_px + np.array([-16.0, -4.0]), ring_at=toe_px, center=(640.0, 200.0))
    return pl


def small_feet():
    """small_feet_press_hold. Cues: vertical wall, one foot on a tiny foothold and the other off, hips over or
    against the foot, the weight comes off the hands (down to two fingers)."""
    S = 160.0
    pl = Plate(S, 262, 388, spot=(196, 200, 212))
    cv, out = pl.cv, pl.scene
    wall = Wall(cv, out, V(0, 0), angle=0.0, s0=-2.7, s1=0.3, lat=(-0.55, 3.2), joints=(-1.30,))
    wall.draw()
    toe = wall.foothold(-0.30, 0.12, 0.017)
    wall.foothold(-0.66, 1.10, 0.018)
    wall.foothold(-0.98, 0.52, 0.020)
    wall.foothold(-0.10, 1.25, 0.018)
    wall.foothold(-1.36, 1.00, 0.030)
    wall.foothold(-2.20, 2.20, 0.030)
    wall.foothold(-0.58, 2.50, 0.022)
    HIP = V(-0.255, 1.150)
    SH = HIP + e(84.0) * 0.50
    ank = toe - e(-12.0) * FOOT
    FK = HIP + e(-97.0) * THIGH
    FA = FK + e(-105.0) * SHANK
    FT = FA + e(-50.0) * FOOT
    s_hi, s_lo = -(SH[1] + 0.535), -(SH[1] - 0.11)
    g_f = wall.jug(s_hi, "far", L_far=-0.30)
    wall.jug(s_lo, "far", L_far=-0.02, scale=0.9)
    fig = Athlete(cv, out, HIP, SH).set_head(pitch=-56.0, neck=20.0)
    fig.arm(False, grip=g_f, bend=_outward(wall, SH, g_f), L_hand=0.10)
    wall.jug(s_hi, "near", L=-0.08)
    fig.leg(False, FK, FA, FT, L_foot=0.09)
    fig.chalk_bag()
    fig.head()
    fig.torso()
    fig.leg(True, ik(HIP, ank, THIGH, SHANK, 1), ank, toe, L_foot=0.12)
    fig.ponytail()
    wall.jug(s_lo, "near", L=0.18, scale=0.9)
    g_n = wall.grip(s_lo, 0.9)
    fig.arm(True, grip=g_n, bend=_low(SH, g_n), L_hand=0.16)
    toe_px = cv.px(toe, 0.12)
    pl.inset(toe_px + np.array([-13.0, -3.0]), ring_at=toe_px, zoom=4.2)
    return pl


def kneebar():
    """rest_and_clip_drill. The kneebar rest: the toe pushes on a foothold and the padded knee locks under a
    big hold, the body sits back on a straight arm and the other arm shakes out. Kneebars only with a knee pad."""
    S = 250.0
    pl = Plate(S, 240, 54, spot=(236, 200, 215))
    cv, out = pl.cv, pl.scene
    wall = Wall(cv, out, V(0, 0), angle=35.0, s0=-0.45, s1=1.75, joints=(0.60, 1.52))
    wall.draw()
    toe_n = wall.foothold(0.93, 0.12, 0.040) + V(0.008, -0.002)
    toe_f = wall.foothold(1.36, -0.08, 0.038) + V(0.008, -0.002)
    wall.block(0.08, 0.325, 0.30, L=-0.10, width=0.52)
    SH, HIP, KNEE = wall.at(0.16, 0.60), wall.at(0.64, 0.50), wall.at(0.39, 0.185)
    g = wall.jug(-0.12, "far", L_far=-0.30)
    fig = Athlete(cv, out, HIP, SH, look="man", harness=True).set_head(pitch=-18.0, neck=14.0)
    fig.arm(False, grip=g, L_hand=0.12)
    wall.jug(-0.12, "near", L=-0.06)
    fk, fa = leg_to_toe(HIP, toe_f, plantar=34)
    fig.leg(False, fk, fa, toe_f, L_foot=0.08)
    fig.chalk_bag()
    fig.head()
    fig.torso()
    knot = fig.tie_in()
    qd = quickdraw(cv, out, wall.at(1.46), L=0.95)
    rope(cv, out, [knot, knot + V(0.05, -0.16), lerp(knot, qd, 0.55) + V(0.0, -0.10), qd, qd + V(0.10, -0.55)],
         L=[0.0, 0.0, 0.5, 0.95, 0.95])
    ank = ik(KNEE, toe_n, SHANK, FOOT, _outward(wall, KNEE, toe_n, SHANK, FOOT))
    fig.leg(True, KNEE, ank, toe_n, L_foot=0.12, pad=True)
    fig.arm(True, wrist=SH + e(-93.0) * ARM, hand="open", L_hand=0.17)
    knee_px = cv.px(wall.at(0.345, 0.20), 0.10)
    pl.inset(knee_px + np.array([6.0, 12.0]), ring_at=knee_px, zoom=2.5, ring=24.0, center=(640.0, 200.0))
    return pl


POCKET_Y = 1.928          # floor of the pocket
BOARD_X = -0.030          # face of the hangboard
POCKET_DEPTH = 0.032


def _board(cv, out, y0=1.865, y1=2.050, lintel=1.79):
    """A hangboard seen in section on the wall above a doorway; the pocket is cut open so the fingers show."""
    px = cv.px
    quad = lambda pts, col: out.append(f'<path d="{poly([px(p) for p in pts])}" fill="{col}"/>')
    quad([V(0.050, lintel), V(0.050, 2.70), V(0.230, 2.70), V(0.230, lintel)], "#AEB7C5")
    quad([V(0.230, lintel), V(0.230, 2.70), V(0.290, 2.70), V(0.290, lintel)], "#59647A")
    a_, b_ = px(V(0.050, lintel)), px(V(0.290, lintel))
    out.append(f'<path d="M{a_[0]:.1f},{a_[1]:.1f} L{b_[0]:.1f},{b_[1]:.1f}" stroke="#39414F" stroke-width="1.2"/>')
    quad([V(0.034, y0 - 0.012), V(0.034, y1 + 0.012), V(0.050, y1 + 0.012), V(0.050, y0 - 0.012)], "#3A4252")
    xf = BOARD_X
    body = [px(V(0.034, y0)), px(V(xf + 0.006, y0)), px(V(xf, y0 + 0.008)), px(V(xf, y1 - 0.030)),
            px(V(xf + 0.012, y1 - 0.008)), px(V(xf + 0.034, y1)), px(V(0.034, y1))]
    d = smooth_closed(body, corners=(0, 1, 2, 6), k=0.18)
    out.append(f'<path d="{d}" fill="#C9A77A"/>')
    grain = smooth_open([px(V(xf + 0.006, y1 - 0.045)), px(V(0.030, y1 - 0.040))])
    low = smooth_open([px(V(xf + 0.004, y0 + 0.006)), px(V(0.032, y0 + 0.006))])
    out.append(cv.soft(d, [(low, "#8E6F4A", 0.020 * cv.s, 1.2, 0.8), (grain, "#E6CBA3", 0.012 * cv.s, 1.0, 0.7)]))
    xb = xf + POCKET_DEPTH
    cav = [px(V(xf - 0.001, POCKET_Y - 0.003)), px(V(xf + 0.004, POCKET_Y)), px(V(xb, POCKET_Y + 0.001)),
           px(V(xb + 0.001, POCKET_Y + 0.025)), px(V(xf - 0.001, POCKET_Y + 0.028))]
    cd = smooth_closed(cav, corners=(0, 4), k=0.2)
    roof = smooth_open([px(V(xf, POCKET_Y + 0.025)), px(V(xb - 0.002, POCKET_Y + 0.023))])
    out.append(f'<path d="{cd}" fill="#5F4930"/>' + cv.soft(cd, [(roof, "#3F301F", 0.010 * cv.s, 0.8, 0.8)]))


def _pocket_wrist():
    """Where the wrist hangs when the last joint of the loaded finger sits at the lip of the pocket."""
    return V(BOARD_X - 0.0434, POCKET_Y - 0.1316)


def _pocket_hand(cv, out, wrist, skin, far_skin, fingers=2):
    """An open hand hanging from a pocket, seen from its little-finger side. The loaded finger drapes over
    the lip (open hand, no crimp); with fingers=2 a second one shows behind it. The unused fingers are folded
    out of the way: the little finger, plus the ring finger when a single finger is loaded."""
    from figkit import prof, shaded_tube
    base, hi, sh_ = skin
    W = np.asarray(wrist, float)
    M = W + V(0.006, 0.086)                                 # knuckles
    P = M + e(72.0) * 0.043                                 # middle joint
    D = P + e(28.0) * 0.025                                 # last joint, at the lip
    T = D + V(0.022, 0.0005)                                # fingertip, flat on the floor of the pocket
    fw = prof([(0, 0.0088), (0.45, 0.0080), (0.8, 0.0072), (1, 0.0064)])
    if fingers == 2:
        fb, fh, fs = far_skin
        svg, _, _ = shaded_tube(cv, [M + V(-0.006, -0.004), P + V(-0.005, 0.0085), D + V(0.002, 0.0042), T + V(0.009, 0.0022)],
                                fw, fw, fb, fh, fs, r=0.016, hi_op=0.25, sh_op=0.5, cap1=0.9)
        out.append(svg)
    svg, d_f, _ = shaded_tube(cv, [M + V(-0.002, -0.008), P, D, T], fw, fw, base, hi, sh_, r=0.016,
                              hi_op=0.45, sh_op=0.55, cap1=0.9)
    out.append(svg)
    back = prof([(0, 0.027), (0.5, 0.021), (1, 0.014)])
    front = prof([(0, 0.026), (0.35, 0.027), (0.75, 0.020), (1, 0.013)])
    svg, d_p, _ = shaded_tube(cv, [W + V(0.0, -0.014), W + V(0.002, 0.040), M], back, front, base, hi, sh_, r=0.03,
                              hi_op=0.4, sh_op=0.5)
    out.append(svg)

    def folded(m, l1, l2, l3, w0, w1):
        """A finger folded back on itself: up to its middle joint, then down into the palm."""
        p = m + e(70.0) * l1
        q = p + e(-52.0) * l2
        t = q + e(-128.0) * l3
        pw = prof([(0, w0), (0.5, (w0 + w1) / 2), (1, w1)])
        under = smooth_open(cv.pxs([m + V(0.006, -0.004), p + V(0.007, -0.003), q + V(0.007, -0.004), t + V(0.004, -0.006)]))
        out.append(cv.soft(d_p, [(under, sh_, 0.012 * cv.s, 0.004 * cv.s, 0.45)]))
        svg, _, _ = shaded_tube(cv, [m, p, q, t], pw, pw, base, hi, sh_, r=0.007, hi_op=0.5, sh_op=0.55)
        out.append(svg)
        q0, q1 = cv.px(p + V(-0.0035, -0.0045)), cv.px(p + V(0.0025, -0.0085))
        out.append(f'<path d="M{q0[0]:.2f},{q0[1]:.2f} L{q1[0]:.2f},{q1[1]:.2f}" stroke="{sh_}" stroke-width="0.35" '
                   f'opacity="0.7" stroke-linecap="round" fill="none"/>')

    if fingers == 1:
        folded(M + V(0.001, -0.004), 0.034, 0.021, 0.019, 0.0080, 0.0064)       # ring finger
    folded(M + V(0.003, -0.016), 0.030, 0.019, 0.018, 0.0072, 0.0058)           # little finger
    q0, q1 = cv.px(P + V(-0.0035, -0.0055)), cv.px(P + V(0.004, -0.0075))
    out.append(f'<path d="M{q0[0]:.2f},{q0[1]:.2f} L{q1[0]:.2f},{q1[1]:.2f}" stroke="{sh_}" stroke-width="0.35" '
               f'opacity="0.7" stroke-linecap="round" fill="none"/>')


def pocket_rampup(fingers=2):
    """pocket_rampup_hangboard (fingers=2) / single_finger_pocket_rampup (fingers=1). Cues: feet stay in contact
    and the legs take the load, open-hand grip in the pocket with no crimp, the unused fingers out of the way."""
    S = 168.0
    pl = Plate(S, 262, 374, spot=(206, 200, 212))
    cv, out = pl.cv, pl.scene
    jamb = [cv.px(p) for p in (V(0.050, 0.0), V(0.050, 1.79), V(0.290, 1.79), V(0.290, 0.0))]
    out.append(f'<path d="{poly(jamb)}" fill="#2A3448" opacity="0.75"/>')
    floor_mat(cv, out, -0.80, 0.50, lat=(-0.45, 0.95))
    w = _pocket_wrist()
    SH = V(-0.112, 1.296)
    HIP = SH + e(-94.0) * 0.52
    an, tn = flat_foot(-0.275, 0.0)
    af, tf = flat_foot(-0.235, 0.0)
    fig = Athlete(cv, out, HIP, SH, look="man", foot="bare").set_head(pitch=14.0, neck=44.0)
    fig.arm(False, wrist=w, hand=None, bend=-1, L_hand=0.0)
    _board(cv, out)
    fig.leg(False, ik(HIP, af, THIGH, SHANK, 1), af, tf, L_foot=0.08)
    fig.head()
    fig.torso()
    fig.leg(True, ik(HIP, an, THIGH, SHANK, 1), an, tn, L_foot=0.08)
    fig.arm(True, wrist=w, hand=None, bend=-1, L_hand=0.0)
    _pocket_hand(cv, out, w, fig.st["skin"], fig.st["far_skin"], fingers)
    hand_px = cv.px(V(BOARD_X - 0.020, POCKET_Y - 0.020))
    pl.inset(hand_px + np.array([1.0, 3.5]), ring_at=hand_px, zoom=6.0, ring=15.0, center=(628.0, 196.0))
    return pl


def fall_practice():
    """fall_practice / fall_ladder. Left: what the heights mean, the tie-in knot above the last clip (here the
    feet are level with it: knot about 1 m above). Circle: the fall itself, pushed off the wall, knees soft,
    feet toward the wall, rope tight on the last clip."""
    S = 165.0
    pl = Plate(S, 270, 338, spot=(200, 200, 212))
    cv, out = pl.cv, pl.scene
    wall = Wall(cv, out, V(0, 0), angle=0.0, s0=-2.4, s1=0.7, joints=(-1.10,))
    wall.draw()
    toe_n = wall.foothold(0.0, 0.10, 0.036)
    toe_f = wall.foothold(-0.10, -0.12, 0.034)
    wall.foothold(-0.78, 1.10, 0.030)
    HIP = V(-0.36, 0.86)
    SH = HIP + e(80.0) * 0.50
    an = toe_n - e(-18.0) * FOOT
    af = toe_f - e(-20.0) * FOOT
    s_hi, s_lo = -(SH[1] + 0.555), -(SH[1] + 0.10)
    g_hi = wall.jug(s_hi, "far", L_far=-0.28)
    wall.jug(s_lo, "far", L_far=-0.04, scale=0.9)
    fig = Athlete(cv, out, HIP, SH, harness=True).set_head(pitch=-6.0, neck=14.0)
    fig.arm(False, grip=g_hi, bend=_outward(wall, SH, g_hi), L_hand=0.10)
    wall.jug(s_hi, "near", L=-0.06)
    fig.leg(False, ik(HIP, af, THIGH, SHANK, 1), af, toe_f, L_foot=0.12)
    fig.chalk_bag()
    fig.head()
    fig.torso()
    knot = fig.tie_in()
    clip = quickdraw(cv, out, wall.at(-0.21), L=0.62)
    rope(cv, out, [knot, knot + V(0.03, -0.30), lerp(knot, clip, 0.72) + V(-0.03, 0.0), clip, clip + V(0.004, -0.9)],
         L=[0.0, 0.0, 0.40, 0.62, 0.62])
    kx, ky = cv.px(knot)
    out.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="3.4" fill="#E8795E" stroke="#7E3B2E" stroke-width="0.8"/>')
    fig.leg(True, ik(HIP, an, THIGH, SHANK, 1), an, toe_n, L_foot=0.10)
    fig.ponytail()
    wall.jug(s_lo, "near", L=0.16, scale=0.9)
    g_lo = wall.grip(s_lo, 0.9)
    fig.arm(True, grip=g_lo, bend=_low(SH, g_lo), L_hand=0.15)
    # the measure: knot to last clip
    knot_px, clip_px = cv.px(knot), cv.px(clip, 0.62)
    bx = cv.px(wall.at(0.0), 1.55)[0] + 0.15 * S + 18
    pl.dashed(knot_px + np.array([7.0, 0.0]), np.array([bx - 9, knot_px[1]]), width=1.8)
    pl.dashed(clip_px + np.array([7.0, 0.0]), np.array([bx - 9, clip_px[1]]), width=1.8)
    pl.bracket(np.array([bx, knot_px[1]]), np.array([bx, clip_px[1]]))
    pl.ring(knot_px, 7.0, 2.2)
    pl.ring(clip_px, 7.0, 2.2)

    # ---- the fall, in the circle
    pan = pl.panel(center=(628.0, 200.0), radius=118.0)
    c2 = cv.sub(106.0, 700.0, 256.0)
    pan.append(f'<rect x="500" y="72" width="256" height="256" fill="#263048"/>')
    w2 = Wall(c2, pan, V(0, 0), angle=0.0, s0=-3.0, s1=3.0, lat=(-0.55, 0.9), slab=0.4)
    w2.draw()
    clip2 = quickdraw(c2, pan, V(0.0, 1.36), L=0.30)
    H2 = V(-0.80, 0.06)
    S2 = H2 + e(102.0) * 0.50
    f2 = Athlete(c2, pan, H2, S2, harness=True).set_head(pitch=-12.0, neck=16.0)
    KN = H2 + e(14.0) * THIGH
    AN = KN + e(-58.0) * SHANK
    KF = H2 + e(-4.0) * THIGH
    AF = KF + e(-68.0) * SHANK
    f2.arm(False, wrist=S2 + V(0.33, -0.10), hand="open", bend=-1, L_hand=0.17)
    f2.leg(False, KF, AF, AF + e(22.0) * FOOT, L_foot=0.11)
    f2.chalk_bag()
    f2.head()
    f2.torso()
    knot2 = f2.tie_in()
    rope(c2, pan, [knot2, clip2], L=[0.0, 0.30])
    rope(c2, pan, [clip2, clip2 + V(0.006, -3.0)], L=0.30)
    k2 = c2.px(knot2)
    pan.append(f'<circle cx="{k2[0]:.1f}" cy="{k2[1]:.1f}" r="2.6" fill="#E8795E" stroke="#7E3B2E" stroke-width="0.6"/>')
    f2.leg(True, KN, AN, AN + e(30.0) * FOOT, L_foot=0.11)
    f2.ponytail(length=0.24)
    f2.arm(True, wrist=S2 + V(0.30, -0.16), hand="open", bend=-1, L_hand=0.17)
    a0 = c2.px(V(-1.36, 0.70))
    pl.arrow(a0, a0 + np.array([0.0, 46.0]), layer=pan)
    return pl


PLATES = {
    "hard_target_profile": dict(fn=hard_target, out="technique/hard_target_profile.webp"),
    "glued_feet": dict(fn=glued_feet, out="technique/glued_feet.webp"),
    "small_feet_press": dict(fn=small_feet, out="technique/small_feet_press.webp", mirror=True),
    "kneebar_rest": dict(fn=kneebar, out="technique/kneebar_rest.webp"),
    "fall_practice": dict(fn=fall_practice, out="technique/fall_practice.webp"),
    "pocket_rampup": dict(fn=pocket_rampup, out="strength/pocket_rampup.webp"),
    "pocket_rampup_mono": dict(fn=lambda: pocket_rampup(1), out="strength/pocket_rampup_mono.webp"),
    "v_sit": dict(fn=v_sit, out="strength/v_sit.webp"),
    "v_sit_45": dict(fn=lambda: v_sit(45.0), out="strength/v_sit_45.webp"),
    "elevated_pike_pushup": dict(fn=elevated_pike_pushup, out="strength/elevated_pike_pushup.webp"),
    "ring_fallout": dict(fn=ring_fallout, out="strength/ring_fallout.webp"),
    "pistol_squat": dict(fn=pistol_squat, out="strength/pistol_squat.webp", mirror=True),
    "dragon_flag_tuck": dict(fn=dragon_flag_tuck, out="core/41_dragon_flag_tuck.webp"),
}
