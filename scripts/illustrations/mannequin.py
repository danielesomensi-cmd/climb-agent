#!/usr/bin/env python3
"""
mannequin.py - 3D climbing mannequin, pose-reference renderer (Blender, headless).

  /Applications/Blender.app/Contents/MacOS/Blender -b -q --factory-startup \
      -P mannequin.py -- POSE.json -o OUT.png [--views] [--sheet] [--check]

or simply:  bin/mannequin POSE.json -o OUT.png --views --sheet

Writes OUT.png (+ OUT_front/_side/_top.png with --views, OUT_sheet.png with
--sheet) and OUT.report.json (reach, joint directions, wall penetrations).
Schema and conventions: MANNEQUIN.md (same folder).
"""
import sys, os, json, math, argparse

try:
    import bpy, bmesh
    from mathutils import Vector, Matrix
except ImportError:  # pragma: no cover
    sys.exit("mannequin.py must run inside Blender: Blender -b -P mannequin.py -- pose.json -o out.png")


def log(*a):
    print("[mannequin]", *a, flush=True)


# ----------------------------------------------------------------- palette
PALETTE = {
    "left": "#1d6fe0", "left_joint": "#1450a8",
    "right": "#e02f28", "right_joint": "#a01d18",
    "torso_front": "#ececec", "torso_back": "#454a53",
    "neck": "#a3a6ab",
    "knee": "#ffd60a",
    "shoe_out": "#ff8800", "shoe_in": "#ffffff", "sole": "#1d1e22",
    "nose": "#141414",
    "wall": "#d3d6da", "wall_side": "#9aa0a8", "floor": "#767c86",
    "bg": "#2e3648", "fill": "#c9ced6",
}

HOLD_TYPES = {
    #           width   height  depth  (m, size=1)      grip = (along lip, out of wall) fractions
    "jug":    dict(w=0.17, h=0.10, d=0.10, color="#22a35a", grip=(0.45, 0.66)),
    "edge":   dict(w=0.15, h=0.045, d=0.045, color="#8b5cf6", grip=(0.5, 0.75)),
    "crimp":  dict(w=0.09, h=0.022, d=0.022, color="#8b5cf6", grip=(0.5, 0.8)),
    "sloper": dict(w=0.22, h=0.16, d=0.075, color="#0f9f94", grip=(0.30, 0.7)),
    "chip":   dict(w=0.065, h=0.04, d=0.032, color="#16a34a", grip=(0.45, 0.6)),
}
HOLD_ALIASES = {"foot": "chip", "foot_chip": "chip", "foothold": "chip", "bucket": "jug", "rail": "edge"}

LIPS = {"up": 90, "down": 270, "left": 180, "right": 0,
        "up-left": 135, "left-up": 135, "up-right": 45, "right-up": 45,
        "down-left": 225, "left-down": 225, "down-right": 315, "right-down": 315}

# foot contact points in the shoe frame, metres for a 1.78 m figure:
# (forward heel->toe, up sole->instep, lateral = little-toe side)
FOOT_CONTACT = {
    "toe": (0.205, -0.060, -0.010),
    "front": (0.205, -0.060, -0.010),
    "inside": (0.150, -0.062, -0.040),
    "outside": (0.120, -0.062, 0.042),
    "heel": (-0.072, -0.045, 0.0),
    "toe_hook": (0.150, -0.012, 0.0),
    "smear": (0.140, -0.078, 0.0),
}


def hex2lin(h, mul=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = min(1.0, int(h[i:i + 2], 16) / 255.0 * mul)
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, axis)


def frame(R):
    """right, up, back columns of a body rotation."""
    return R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0)), R @ Vector((0, 0, 1))


def any_perp(n):
    a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    return (a - n * a.dot(n)).normalized()


# ----------------------------------------------------------------- wall frame
class Wall:
    """Wall coords: x along the wall to the climber's right, y up the wall surface
    from its base, z out of the wall towards the climber (0 = surface)."""

    def __init__(self, spec):
        self.spec = spec
        self.angle = float(spec.get("angle_deg", spec.get("angle", 0.0)))
        a = math.radians(self.angle)
        self.X = Vector((1, 0, 0))
        self.U = Vector((0, -math.sin(a), math.cos(a)))
        self.N = Vector((0, -math.cos(a), -math.sin(a)))

    def p(self, xyz):
        x, y = float(xyz[0]), float(xyz[1])
        z = float(xyz[2]) if len(xyz) > 2 and xyz[2] is not None else 0.0
        return self.X * x + self.U * y + self.N * z

    v = p

    def w(self, world):
        return Vector((world.dot(self.X), world.dot(self.U), world.dot(self.N)))

    def lip(self, lip):
        if lip is None:
            return None
        if isinstance(lip, (int, float)):
            a = math.radians(lip)
        elif isinstance(lip, (list, tuple)):
            return (self.X * lip[0] + self.U * lip[1]).normalized()
        else:
            key = str(lip).lower().replace("_", "-").replace(" ", "")
            if key not in LIPS:
                raise ValueError(f"unknown lip '{lip}' (use {sorted(LIPS)} or degrees, 90=up)")
            a = math.radians(LIPS[key])
        return (self.X * math.cos(a) + self.U * math.sin(a)).normalized()


def words_of(W, vec, thr=0.25):
    """Human description of a world vector in wall terms."""
    if vec.length < 1e-9:
        return "none"
    v = W.w(vec.normalized())
    names = [("right", "left", v.x), ("up", "down", v.y), ("away-from-wall", "into-wall", v.z)]
    parts = [(abs(c), pos if c > 0 else neg) for pos, neg, c in names if abs(c) >= thr]
    parts.sort(reverse=True)
    return ", ".join(f"{n} {m:.2f}" for m, n in parts) or "mixed"


def body_words(vec, r, u, b, thr=0.25):
    v = vec.normalized()
    names = [("body-right", "body-left", v.dot(r)), ("body-up", "body-down", v.dot(u)),
             ("body-back", "body-front", v.dot(b))]
    parts = [(abs(c), pos if c > 0 else neg) for pos, neg, c in names if abs(c) >= thr]
    parts.sort(reverse=True)
    return ", ".join(f"{n} {m:.2f}" for m, n in parts) or "mixed"


def wl(W, p):
    return [round(c, 3) for c in W.w(p)]


# ----------------------------------------------------------------- body dims
def body_dims(pose):
    fig = pose.get("figure", "man")
    woman = fig == "woman"
    H = float(pose.get("height") or (1.66 if woman else 1.78))
    ape = float(pose.get("ape_index", 1.0))
    arm_k = 1.0 + (ape - 1.0) * 0.5 / 0.44
    k = H / 1.78
    lim = 0.92 if woman else 1.0
    D = dict(H=H, k=k, fig=fig, woman=woman,
             hip_half=(0.055 if woman else 0.050) * H,
             pelvis_len=0.09 * H, abd_len=0.08 * H,
             sh_up=0.12 * H, sh_half=(0.095 if woman else 0.105) * H,
             neck_base=0.135 * H, neck_len=0.036 * H,
             upper=0.186 * H * arm_k, fore=0.146 * H * arm_k,
             palm=0.058 * H * arm_k, fingers=0.05 * H * arm_k,
             thigh=0.245 * H, shin=0.246 * H)
    D["r"] = {
        "thigh": (0.078 * k * lim, 0.054 * k * lim), "shin": (0.052 * k * lim, 0.036 * k * lim),
        "upper": (0.050 * k * lim, 0.040 * k * lim), "fore": (0.042 * k * lim, 0.030 * k * lim),
        "hip": 0.072 * k * lim, "knee": 0.056 * k * lim, "ankle": 0.038 * k * lim,
        "shoulder": 0.060 * k * lim, "elbow": 0.043 * k * lim, "wrist": 0.031 * k * lim,
        "neck": 0.030 * H,
    }
    D["ell"] = {  # semi-axes (width, depth, height)
        "pelvis": ((0.104 if woman else 0.095) * H, 0.058 * H, 0.062 * H),
        "abdomen": ((0.074 if woman else 0.078) * H, 0.050 * H, 0.085 * H),
        "chest": ((0.094 if woman else 0.105) * H, 0.060 * H, 0.092 * H),
        "head": (0.044 * H, 0.055 * H, 0.065 * H),
    }
    return D


# ----------------------------------------------------------------- holds
def build_holds(pose, W):
    holds = {}
    for name, h in (pose.get("holds") or {}).items():
        t = HOLD_ALIASES.get(h.get("type", "jug"), h.get("type", "jug"))
        if t not in HOLD_TYPES:
            raise ValueError(f"hold {name}: unknown type '{t}' (use {sorted(HOLD_TYPES)})")
        base = HOLD_TYPES[t]
        s = float(h.get("size", 1.0))
        L = W.lip(h.get("lip", "up"))
        A = L.cross(W.N).normalized()
        c = W.p((h["pos"][0], h["pos"][1], 0.0))
        g0, g1 = base["grip"]
        grip = c + L * (base["h"] * s * g0) + W.N * (base["d"] * s * g1)
        if "grip_offset" in h:
            grip = grip + W.v(h["grip_offset"])
        holds[name] = dict(name=name, type=t, center=c, L=L, A=A, s=s, grip=grip,
                           lip_spec=h.get("lip", "up"), color=h.get("color", base["color"]),
                           w=base["w"] * s, h=base["h"] * s, d=base["d"] * s)
    return holds


# ----------------------------------------------------------------- IK
def two_bone(root, target, a, b, pole_dir):
    v = target - root
    dist = v.length
    n = v.normalized() if dist > 1e-9 else Vector((0, 0, -1))
    reached, short = True, 0.0
    maxr, minr = (a + b) * 0.9995, abs(a - b) + 1e-3
    end = target.copy()
    if dist > maxr:
        reached, short = False, dist - (a + b)
        end = root + n * maxr
    elif dist < minr:
        end = root + n * minr
    dd = (end - root).length
    x = (a * a - b * b + dd * dd) / (2 * dd)
    h = math.sqrt(max(0.0, a * a - x * x))
    q = pole_dir - n * pole_dir.dot(n)
    if q.length < 1e-6:
        q = any_perp(n)
    q.normalize()
    mid = root + n * x + q * h
    ang = math.degrees((root - mid).angle(end - mid)) if h > 1e-6 else 180.0
    return mid, end, reached, short, ang, q, dist / (a + b)


def parse_dir(spec, words, W):
    if spec is None:
        return None
    if isinstance(spec, (list, tuple)):
        return W.v(spec)
    total = Vector((0, 0, 0))
    for term in str(spec).replace(" ", "").replace("-", "+-").split("+"):
        if not term:
            continue
        neg = term.startswith("-")
        term = term.lstrip("-")
        w = 1.0
        if "*" in term:
            ws, term = term.split("*", 1)
            w = float(ws)
        if term not in words:
            raise ValueError(f"unknown direction word '{term}' (known: {sorted(words)})")
        total += words[term] * (-w if neg else w)
    return total


def limb_words(W, s, r, u, b):
    return {"left": -W.X, "right": W.X, "up": W.U, "down": -W.U, "in": -W.N, "away": W.N,
            "outward": W.X * s, "inward": -W.X * s,
            "fwd": -b, "back": b, "bodyup": u, "bodydown": -u, "bodyout": r * s, "bodyin": -r * s}


def target_of(spec, W, holds):
    if not spec:
        return None, None
    hold, pt = None, None
    if spec.get("hold") is not None:
        if spec["hold"] not in holds:
            raise ValueError(f"unknown hold '{spec['hold']}'")
        hold = holds[spec["hold"]]
        pt = hold["grip"].copy()
    elif spec.get("pos") is not None:
        pt = W.p(spec["pos"])
    if pt is not None and spec.get("offset") is not None:
        pt = pt + W.v(spec["offset"])
    return pt, hold


def orthonorm(f, u):
    f = f.normalized()
    u = u - f * u.dot(f)
    if u.length < 1e-6:
        u = any_perp(f)
    return f, u.normalized()


def solve_arm(side, spec, J, W, D, holds, Rc):
    s = 1 if side == "right" else -1
    spec = spec or {}
    cr, cu, cb = frame(Rc)
    sh0 = J["sh_r" if s > 0 else "sh_l"]
    H = D["H"]
    words = limb_words(W, s, cr, cu, cb)
    L = D["upper"] + D["fore"]
    contact, hold = target_of(spec, W, holds)
    has_target = contact is not None
    if not has_target:
        wrist_t = sh0 - cu * L * 0.985 + cr * s * 0.035 * H
        d = (wrist_t - sh0).normalized()
        d, p = orthonorm(d, -cr * s)
        curl = float(spec.get("curl_deg", 20))
        contact = wrist_t + d * (D["palm"] + 0.45 * D["fingers"])
    else:
        lip = W.lip(spec["lip"]) if spec.get("lip") is not None else (hold["L"] if hold else None)
        if lip is not None and not spec.get("open", False):
            bw = math.radians(float(spec.get("wrap_deg", 35)))
            d = lip * math.cos(bw) - W.N * math.sin(bw)
            p = -W.N * math.cos(bw) - lip * math.sin(bw)
            curl = float(spec.get("curl_deg", 75))
        else:
            d = (contact - sh0).normalized()
            p = -W.N
            curl = float(spec.get("curl_deg", 12))
        if spec.get("fingers") is not None:
            d = W.v(spec["fingers"])
        if spec.get("palm") is not None:
            p = W.v(spec["palm"])
        d, p = orthonorm(d, p)
        wrist_t = contact - d * (D["palm"] + 0.45 * D["fingers"]) - p * 0.012 * H
    if spec.get("roll_deg"):
        p = Matrix.Rotation(math.radians(spec["roll_deg"]), 3, d) @ p
    # scapula: let the shoulder travel up to 3.5% H towards an out-of-reach hand
    dist0 = (wrist_t - sh0).length
    sh = sh0.copy()
    if has_target and dist0 > L * 0.985:
        m = min(dist0 - L * 0.985, 0.035 * H)
        sh = sh0 + (wrist_t - sh0).normalized() * m
    pole = parse_dir(spec.get("pole"), words, W)
    if spec.get("pole_point") is not None:
        pole = W.p(spec["pole_point"]) - (sh + wrist_t) * 0.5
    if pole is None:
        pole = -cu * 1.0 + cr * s * 0.5 + cb * 0.3
    elbow, wrist, reached, short, ang, q, ext = two_bone(sh, wrist_t, D["upper"], D["fore"], pole)
    off = wrist - wrist_t
    rep = dict(has_target=has_target, reached=reached, shortfall_cm=round(short * 100, 1),
               extension=round(dist0 / L, 3), elbow_angle_deg=round(ang, 1),
               elbow_points=words_of(W, q), elbow_points_body=body_words(q, cr, cu, cb),
               shoulder_shift_cm=round((sh - sh0).length * 100, 1),
               target=wl(W, contact) if has_target else None,
               hold=hold["name"] if hold else None)
    return dict(side=s, sh=sh, elbow=elbow, wrist=wrist, d=d, p=p, curl=curl,
                contact=contact + off, pole_q=q, report=rep, ratio=dist0 / L, has_target=has_target,
                straight=bool(spec.get("straight")),
                pref=float(spec.get("reach", 0.995 if spec.get("straight") else 0.9)))


def foot_frame(spec, s, W, hold, Rp):
    out = W.X * s
    edge = spec.get("edge", "front")
    if edge not in FOOT_CONTACT:
        raise ValueError(f"unknown foot edge '{edge}' (use {sorted(FOOT_CONTACT)})")
    a = math.radians(float(spec.get("turn_deg", 55)))
    if edge in ("toe", "front"):
        f, u = -W.N, W.U
    elif edge == "inside":
        f, u = -W.N * math.cos(a) + out * math.sin(a), W.U
    elif edge == "outside":
        f, u = -W.N * math.cos(a) - out * math.sin(a), W.U
    elif edge == "heel":
        f, u = (out + W.U * 0.25), W.N
    elif edge == "toe_hook":
        f, u = (out + W.U * 0.2), -W.N
    else:  # smear
        f, u = W.U, W.N
    if spec.get("toe_dir") is not None:
        f = W.v(spec["toe_dir"])
    if spec.get("sole_up") is not None:
        u = W.v(spec["sole_up"])
    f, u = orthonorm(f, u)
    if spec.get("roll_deg"):  # roll about the toe axis (+ = little-toe edge down)
        u = Matrix.Rotation(math.radians(spec["roll_deg"]) * s, 3, f) @ u
    return edge, f, u


def solve_leg(side, spec, J, W, D, holds, Rp):
    s = 1 if side == "right" else -1
    spec = spec or {}
    pr, pu, pb = frame(Rp)
    hip = J["hip_r" if s > 0 else "hip_l"]
    k, H = D["k"], D["H"]
    words = limb_words(W, s, pr, pu, pb)
    L = D["thigh"] + D["shin"]
    contact, hold = target_of(spec, W, holds)
    has_target = contact is not None
    if not has_target:
        ankle_t = hip - pu * L * 0.95 - pb * 0.05 * H
        f, u = orthonorm(-pb * 0.6 - pu * 0.8, pu - pb * 0.3)
        edge = "front"
        c = FOOT_CONTACT[edge]
        lat = f.cross(u) * s
        contact = ankle_t + (f * c[0] + u * c[1] + lat * c[2]) * k
    else:
        edge, f, u = foot_frame(spec, s, W, hold, Rp)
        c = FOOT_CONTACT[edge]
        lat = f.cross(u) * s
        ankle_t = contact - (f * c[0] + u * c[1] + lat * c[2]) * k
    pole = parse_dir(spec.get("pole"), words, W)
    if spec.get("pole_point") is not None:
        pole = W.p(spec["pole_point"]) - (hip + ankle_t) * 0.5
    if pole is None:
        pole = -pb * 1.0 + pr * s * 0.6 + pu * 0.2
    knee, ankle, reached, short, ang, q, ext = two_bone(hip, ankle_t, D["thigh"], D["shin"], pole)
    auto_ank = (has_target and spec.get("ankle", "auto") == "auto" and edge not in ("heel", "toe_hook")
                and spec.get("toe_dir") is None and spec.get("sole_up") is None)
    lim_deg = float(spec.get("ankle_limit_deg", 40))
    f0 = f.copy()
    for _ in range(4 if auto_ank else 0):
        # roll/tilt the shoe about its contact so the ankle stays within lim_deg of neutral
        shin = (knee - ankle).normalized()
        ex = math.degrees(u.angle(shin)) - lim_deg
        if ex < 1.0:
            break
        ax = u.cross(shin)
        if ax.length < 1e-6:
            break
        u = Matrix.Rotation(math.radians(ex), 3, ax.normalized()) @ u
        u.normalize()
        fn = f0 - u * f0.dot(u)  # keep the toes as close as possible to the requested direction
        if fn.length < 1e-6:
            break
        f = fn.normalized()
        lat = f.cross(u) * s
        ankle_t = contact - (f * c[0] + u * c[1] + lat * c[2]) * k
        knee, ankle, reached, short, ang, q, ext = two_bone(hip, ankle_t, D["thigh"], D["shin"], pole)
    off = ankle - ankle_t
    dist0 = (ankle_t - hip).length
    # ankle sanity: angle between shin and the foot's up axis
    shin_dir = (knee - ankle).normalized()
    ank = math.degrees(shin_dir.angle(u))
    rep = dict(has_target=has_target, reached=reached, shortfall_cm=round(short * 100, 1),
               extension=round(dist0 / L, 3), knee_angle_deg=round(ang, 1),
               knee_points=words_of(W, q), knee_points_body=body_words(q, pr, pu, pb),
               knee_height_vs_foot_cm=round((W.w(knee).y - W.w(contact + off).y) * 100, 1),
               edge=edge, toes_point=words_of(W, f), ankle_shin_vs_sole_normal_deg=round(ank, 1),
               target=wl(W, contact) if has_target else None,
               hold=hold["name"] if hold else None)
    return dict(side=s, hip=hip, knee=knee, ankle=ankle, f=f, u=u, contact=contact + off,
                pole_q=q, report=rep, ratio=dist0 / L, has_target=has_target, ank=ank,
                straight=bool(spec.get("straight")),
                pref=float(spec.get("reach", 0.995 if spec.get("straight") else 0.78)))


def build(pose, W, D, holds, ppos):
    H = D["H"]
    warn = []
    pel = pose.get("pelvis") or {}
    M0 = Matrix((W.X, W.U, W.N)).transposed()
    Rp = M0 @ rot("Y", pel.get("yaw", 0)) @ rot("X", -pel.get("pitch", 0)) @ rot("Z", -pel.get("roll", 0))
    ch = pose.get("chest") or {}
    tw, bd, sd = ch.get("twist", 0), ch.get("bend", 0), ch.get("side", 0)
    Ra = Rp @ rot("Y", tw / 2) @ rot("X", -bd / 2) @ rot("Z", -sd / 2)
    Rc = Rp @ rot("Y", tw) @ rot("X", -bd) @ rot("Z", -sd)
    pr, pu, pb = frame(Rp)
    ar, au, ab = frame(Ra)
    cr, cu, cb = frame(Rc)
    J = {}
    J["hipC"] = W.p(ppos)
    J["hip_l"] = J["hipC"] - pr * D["hip_half"]
    J["hip_r"] = J["hipC"] + pr * D["hip_half"]
    J["waist"] = J["hipC"] + pu * D["pelvis_len"]
    J["chestB"] = J["waist"] + au * D["abd_len"]
    J["sh_l"] = J["chestB"] + cu * D["sh_up"] - cr * D["sh_half"]
    J["sh_r"] = J["chestB"] + cu * D["sh_up"] + cr * D["sh_half"]
    J["neckB"] = J["chestB"] + cu * D["neck_base"]
    arms = {sd_: solve_arm(sd_, pose.get(f"{sd_}_hand"), J, W, D, holds, Rc) for sd_ in ("left", "right")}
    legs = {sd_: solve_leg(sd_, pose.get(f"{sd_}_foot"), J, W, D, holds, Rp) for sd_ in ("left", "right")}
    # head
    hd = pose.get("head") or {}
    approx = J["neckB"] + cu * (D["neck_len"] + 0.055 * H)
    tgt = hd.get("look_at")
    tp = None
    if isinstance(tgt, str):
        if tgt in holds:
            tp = holds[tgt]["center"] + W.N * holds[tgt]["d"] * 0.5
        elif tgt.endswith("_hand") and tgt[:-5] in arms:
            tp = arms[tgt[:-5]]["contact"]
        elif tgt.endswith("_foot") and tgt[:-5] in legs:
            tp = legs[tgt[:-5]]["contact"]
        else:
            raise ValueError(f"look_at '{tgt}': not a hold or left/right_hand/foot")
    elif isinstance(tgt, (list, tuple)):
        tp = W.p(tgt)
    clamped = False
    if tp is not None:
        fc = Rc.transposed() @ (tp - approx).normalized()
        yaw = math.degrees(math.atan2(-fc.x, -fc.z))
        pitch = math.degrees(math.atan2(fc.y, math.hypot(fc.x, fc.z)))
    else:
        yaw, pitch = float(hd.get("yaw", 0)), float(hd.get("pitch", 10))
    yaw_c = max(-80.0, min(80.0, yaw))
    if tp is not None and abs(yaw_c - yaw) > 0.5:
        # neck at its limit: tilt the head to the closest reachable gaze instead
        hz = fc.x * -math.sin(math.radians(yaw_c)) + fc.z * -math.cos(math.radians(yaw_c))
        pitch = math.degrees(math.atan2(fc.y, max(hz, 0.0)))
    pitch_c = max(-55.0, min(65.0, pitch))
    if abs(yaw_c - yaw) > 0.5 or abs(pitch_c - pitch) > 0.5:
        clamped = True
        warn.append(f"head turn clamped (wanted yaw {yaw:.0f}, pitch {pitch:.0f} vs chest; limits +-80 / -55..65)")
    Rh = Rc @ rot("Y", yaw_c) @ rot("X", pitch_c) @ rot("Z", -float(hd.get("tilt", 0)))
    hr, hu, hb = frame(Rh)
    J["neckT"] = J["neckB"] + (cu + hu).normalized() * D["neck_len"]
    J["headC"] = J["neckT"] + hu * 0.052 * H - hb * 0.012 * H
    sk = dict(J=J, Rp=Rp, Ra=Ra, Rc=Rc, Rh=Rh, arms=arms, legs=legs, warn=warn,
              head=dict(yaw=round(yaw_c, 1), pitch=round(pitch_c, 1), clamped=clamped,
                        gaze=words_of(W, -hb)))
    sk["pen"] = penetrations(sk, W, D)
    return sk


# ----------------------------------------------------------------- checks
def ell_parts(sk, D):
    J = sk["J"]
    E = D["ell"]
    pr, pu, pb = frame(sk["Rp"])
    ar, au, ab = frame(sk["Ra"])
    cr, cu, cb = frame(sk["Rc"])
    hr, hu, hb = frame(sk["Rh"])
    H = D["H"]
    return [
        ("pelvis", J["hipC"] + pu * 0.030 * H + pb * 0.008 * H, (pr, -pb, pu), E["pelvis"]),
        ("abdomen", J["waist"] + au * 0.030 * H, (ar, -ab, au), E["abdomen"]),
        ("chest", J["chestB"] + cu * 0.058 * H, (cr, -cb, cu), E["chest"]),
        ("head", J["headC"], (hr, -hb, hu), E["head"]),
    ]


def capsule_parts(sk, D):
    R = D["r"]
    out = []
    for nm, a in sk["arms"].items():
        out.append((f"{nm}_upper_arm", a["sh"], a["elbow"], R["upper"]))
        out.append((f"{nm}_forearm", a["elbow"], a["wrist"], R["fore"]))
    for nm, l in sk["legs"].items():
        out.append((f"{nm}_thigh", l["hip"], l["knee"], R["thigh"]))
        out.append((f"{nm}_shin", l["knee"], l["ankle"], R["shin"]))
    return out


def penetrations(sk, W, D):
    pen = []
    for name, c, axes, semi in ell_parts(sk, D):
        ext = math.sqrt(sum((s_ * ax.dot(W.N)) ** 2 for s_, ax in zip(semi, axes)))
        z = c.dot(W.N) - ext
        if z < -0.015:
            pen.append((name, -z))
    for name, a, b, (r0, r1) in capsule_parts(sk, D):
        worst = 0.0
        for i in range(6):
            t = i / 5
            p = a.lerp(b, t)
            z = p.dot(W.N) - (r0 + (r1 - r0) * t)
            worst = min(worst, z)
        if worst < -0.015:
            pen.append((name, -worst))
    return pen


def cost_of(sk, W, D, zpref, xpref):
    c = 0.0
    for lim in list(sk["arms"].values()) + list(sk["legs"].values()):
        if lim["has_target"]:
            r, pref = lim["ratio"], lim["pref"]
            wu = 4.0 if lim["straight"] else 0.4
            c += wu * max(0.0, pref - r) ** 2 + 3.0 * max(0.0, r - pref) ** 2 + 60 * max(0.0, r - 0.995) ** 2
    for _, depth in sk["pen"]:
        c += 3000 * depth ** 2
    hc = W.w(sk["J"]["hipC"])
    c += 1.0 * (hc.z - zpref) ** 2
    if xpref is not None:
        c += 0.3 * (hc.x - xpref) ** 2
    return c


def solve_pelvis(pose, W, D, holds):
    pel = pose.get("pelvis") or {}
    pos = list(pel.get("pos") or [None, None, None])
    while len(pos) < 3:
        pos.append(None)
    free = [i for i, v in enumerate(pos) if v is None]
    if pel.get("auto"):
        free = [0, 1, 2] if pel["auto"] is True else ["xyz".index(a) for a in pel["auto"]]
    if not free:
        return [float(v) for v in pos], False
    # start point from targets
    pts = []
    for nm in ("left_hand", "right_hand", "left_foot", "right_foot"):
        p, _ = target_of(pose.get(nm), W, holds)
        if p is not None:
            pts.append((nm, W.w(p)))
    feet = [p for nm, p in pts if nm.endswith("foot")]
    hands = [p for nm, p in pts if nm.endswith("hand")]
    x0 = sum(p.x for _, p in pts) / len(pts) if pts else 0.0
    xpref = pel.get("x_pref", x0 if pts else None)
    if feet:
        y0 = sum(p.y for p in feet) / len(feet) + 0.45 * D["H"]
    elif hands:
        y0 = sum(p.y for p in hands) / len(hands) - 0.55 * D["H"]
    else:
        y0 = 0.53 * D["H"]
    zpref = float(pel.get("z_pref", 0.30 + 0.25 * math.sin(math.radians(max(0.0, W.angle)))))
    start = [x0, y0, zpref]
    x = [float(pos[i]) if pos[i] is not None and i not in free else start[i] for i in range(3)]
    best = cost_of(build(pose, W, D, holds, x), W, D, zpref, xpref)
    step = 0.16
    while step > 0.0015:
        improved = False
        for i in free:
            for sg in (1, -1):
                y = list(x)
                y[i] += sg * step
                if i == 2 and y[2] < 0.08:
                    continue
                c = cost_of(build(pose, W, D, holds, y), W, D, zpref, xpref)
                if c < best - 1e-10:
                    x, best, improved = y, c, True
        if not improved:
            step *= 0.5
    return [round(v, 3) for v in x], True


# ----------------------------------------------------------------- geometry
MATS = {}


def mat(key, hexcol, emit=0.0, rough=0.65, mul=1.0):
    key = f"{key}:{hexcol}:{mul}"
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(key)
    col = hex2lin(hexcol, mul)
    m.diffuse_color = col
    m.roughness = rough
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        nt.nodes.clear()
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        outn = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], outn.inputs[0])
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = rough
    for nm, val in (("Specular IOR Level", 0.25), ("Specular", 0.25)):
        if nm in bsdf.inputs:
            bsdf.inputs[nm].default_value = val
    if emit:
        for nm in ("Emission Color", "Emission"):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = col
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit
    MATS[key] = m
    return m


def bm_lathe(profile, seg=32):
    """Revolve (r, z) profile around local z; profile runs pole to pole."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-9:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * j / seg),
                                        r * math.sin(2 * math.pi * j / seg), z)) for j in range(seg)])
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for j in range(seg):
            j2 = (j + 1) % seg
            if len(a) == 1:
                bm.faces.new((a[0], b[j], b[j2]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[j2], b[0]))
            else:
                bm.faces.new((a[j], a[j2], b[j2], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def prof_capsule(r0, r1, L, n=8):
    pr = [(0.0, -r0)]
    for i in range(1, n + 1):
        a = -math.pi / 2 + (math.pi / 2) * i / n
        pr.append((r0 * math.cos(a), r0 * math.sin(a)))
    for i in range(0 if L > 1e-6 else 1, n):
        a = (math.pi / 2) * i / n
        pr.append((r1 * math.cos(a), L + r1 * math.sin(a)))
    pr.append((0.0, L + r1))
    return pr


def M4(o, x, y, z, sx=1.0, sy=1.0, sz=1.0):
    return Matrix(((x.x * sx, y.x * sy, z.x * sz, o.x),
                   (x.y * sx, y.y * sy, z.y * sz, o.y),
                   (x.z * sx, y.z * sy, z.z * sz, o.z),
                   (0, 0, 0, 1)))


def seg_matrix(o, zdir, xhint=None, sx=1.0, sy=1.0):
    z = zdir.normalized()
    x = xhint if xhint is not None else any_perp(z)
    x = x - z * x.dot(z)
    if x.length < 1e-6:
        x = any_perp(z)
    x.normalize()
    y = z.cross(x)
    return M4(o, x, y, z, sx, sy, 1.0)


def add_obj(name, bm, matrix, mats, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = matrix
    return ob


def capsule(name, a, b, r0, r1, m, xhint=None):
    L = (b - a).length
    bm = bm_lathe(prof_capsule(r0, r1, L))
    return add_obj(name, bm, seg_matrix(a, (b - a) if L > 1e-6 else Vector((0, 0, 1)), xhint), [m])


def sphere(name, c, r, m):
    bm = bm_lathe(prof_capsule(r, r, 0.0))
    return add_obj(name, bm, Matrix.Translation(c), [m])


def ellipsoid_split(name, c, axes, semi, m_front, m_back, seg=40):
    """axes = (right, front, up) unit vectors; local +y half gets m_front."""
    bm = bm_lathe(prof_capsule(1.0, 1.0, 0.0, n=12), seg=seg)
    for f in bm.faces:
        f.material_index = 0 if f.calc_center_median().y > 0 else 1
    r, fw, u = axes
    return add_obj(name, bm, M4(c, r, fw, u, semi[0], semi[1], semi[2]), [m_front, m_back])


def ellipsoid(name, c, axes, semi, m, seg=32):
    bm = bm_lathe(prof_capsule(1.0, 1.0, 0.0, n=10), seg=seg)
    x, y, z = axes
    return add_obj(name, bm, M4(c, x, y, z, semi[0], semi[1], semi[2]), [m])


def disc(name, c, normal, r, t, m):
    bm = bm_lathe([(0.0, 0.0), (r, 0.0), (r, t), (0.0, t)], seg=32)
    return add_obj(name, bm, seg_matrix(c, normal), [m], smooth=False)


def cone(name, base, direction, r, h, m):
    bm = bm_lathe([(0.0, 0.0), (r, 0.0), (r * 0.25, h * 0.85), (0.0, h)], seg=24)
    return add_obj(name, bm, seg_matrix(base, direction), [m])


def box(name, c, axes, half, mats, top_axis=1):
    """axes = (x, y, z) unit, half extents; face whose normal is +top_axis gets mats[1]."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.material_index = 1 if (len(mats) > 1 and f.normal[top_axis] > 0.9) else 0
    x, y, z = axes
    return add_obj(name, bm, M4(c, x, y, z, half[0], half[1], half[2]), mats, smooth=False)


def shoe(name, ankle, f, u, s, k, limb_mat):
    """Climbing shoe in frame (x = f x u, y = f, z = u), origin at the ankle joint.
    s = +1 right / -1 left: lateral (little-toe) side is +x*s."""
    bm = bmesh.new()
    NS, NR = 26, 24
    sole = -0.077
    rows = []
    for i in range(NS + 1):
        t = i / NS
        y = -0.068 + t * 0.278
        ef = max(0.0, 1.0 - abs(2 * t - 1) ** 6) ** 0.35  # round both ends
        w = (0.033 + 0.016 * math.sin(math.pi * min(t / 0.72, 1.0) * 0.5))
        if t > 0.72:
            w *= math.sqrt(max(0.0, 1 - ((t - 0.72) / 0.30) ** 2)) * 0.6 + 0.4
        w *= ef
        top = 0.092 if t < 0.38 else 0.092 - (t - 0.38) / 0.62 * 0.060
        hgt = top * (0.35 + 0.65 * ef)
        xc = -s * 0.013 * max(0.0, (t - 0.45) / 0.55) ** 2
        zc = sole + hgt / 2 + (1 - ef) * 0.02
        if w < 1e-4:
            rows.append([bm.verts.new((xc * k, y * k, zc * k))])
            continue
        ring = []
        for j in range(NR):
            a = 2 * math.pi * j / NR
            ca, sa = math.cos(a), math.sin(a)
            ex = 2.0 / (3.0 if sa < 0 else 2.2)
            px = xc + w * math.copysign(abs(ca) ** ex, ca)
            pz = zc + hgt / 2 * math.copysign(abs(sa) ** ex, sa)
            ring.append(bm.verts.new((px * k, y * k, pz * k)))
        rows.append(ring)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(NR):
            j2 = (j + 1) % NR
            if len(a) == 1:
                bm.faces.new((a[0], b[j], b[j2]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[j2], b[0]))
            else:
                bm.faces.new((a[j], a[j2], b[j2], b[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for fc in bm.faces:
        n, c = fc.normal, fc.calc_center_median()
        if n.z < -0.55 and c.z < (sole + 0.02) * k:
            fc.material_index = 2  # sole
        elif -0.012 * k < c.y < 0.035 * k and n.z > -0.3:
            fc.material_index = 3  # strap in limb colour
        else:
            fc.material_index = 0 if c.x * s > 0 else 1  # lateral orange / medial white
    x = f.cross(u)
    mats = [mat("shoe_out", PALETTE["shoe_out"], emit=0.15), mat("shoe_in", PALETTE["shoe_in"]),
            mat("sole", PALETTE["sole"]), limb_mat]
    return add_obj(name, bm, M4(ankle, x, f, u), mats)


def hand(name, arm, D, m, mj):
    s = arm["side"]
    d, p = arm["d"], arm["p"]
    k = D["k"] * (0.92 if D["woman"] else 1.0)
    w = arm["wrist"]
    t = (d.cross(p) if s > 0 else p.cross(d)).normalized()  # thumb side
    side = p.cross(d)  # x axis for right-handed (x, p, d)
    palm_len, fl = D["palm"], D["fingers"]
    ellipsoid(name + "_palm", w + d * palm_len * 0.5, (side, p, d),
              (0.043 * k, 0.016 * k, palm_len * 0.55), m)
    kn = w + d * palm_len
    prox = fl * 0.5
    cr = math.radians(arm["curl"])
    ob = capsule(name + "_fing1", kn, kn + d * prox, 0.0105 * k, 0.0100 * k, m, xhint=side)
    ob.matrix_world = seg_matrix(kn, d, side, sx=3.7, sy=1.0)
    cdir = (d * math.cos(cr) + p * math.sin(cr)).normalized()
    a2 = kn + d * prox
    ob = capsule(name + "_fing2", a2, a2 + cdir * fl * 0.45, 0.0100 * k, 0.0085 * k, m, xhint=side)
    ob.matrix_world = seg_matrix(a2, cdir, side, sx=3.5, sy=1.0)
    tb = w + d * palm_len * 0.25 + t * 0.032 * k
    tdir = (d * 0.65 + t * 0.55 + p * 0.5).normalized()
    capsule(name + "_thumb", tb, tb + tdir * 0.05 * k, 0.012 * k, 0.010 * k, mj)


# ----------------------------------------------------------------- scene
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear()


def draw_wall(pose, W, holds, sk):
    ws = pose.get("wall") or {}
    width = float(ws.get("width", 7.0))
    height = float(ws.get("height", 5.0))
    xc = float(ws.get("x_center", 0.0))
    thick = 0.08
    # two pieces split at hip level: the top check view hides the upper one so an overhang cannot cover the body
    ysplit = min(max(W.w(sk["J"]["hipC"]).y, 0.3), height - 0.3)
    wm = [mat("wall_side", PALETTE["wall_side"], rough=0.9), mat("wall", ws.get("color", PALETTE["wall"]), rough=0.9)]
    for nm, y0, y1 in (("wall_lower", 0.0, ysplit), ("wall_upper", ysplit, height)):
        c = W.p((xc, (y0 + y1) / 2, -thick / 2))
        box(nm, c, (W.X, W.U, W.N), (width / 2, (y1 - y0) / 2, thick / 2), wm, top_axis=2)
    if ws.get("floor", True):
        fl = Vector((xc, -4.0, -0.02))
        box("floor", fl, (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))), (width / 2 + 3.0, 4.5, 0.02),
            [mat("floor", PALETTE["floor"], rough=0.95)])
    for nm, h in holds.items():
        col = h["color"]
        m, md = mat("hold", col, rough=0.5), mat("hold_lip", col, rough=0.5, mul=0.55)
        L, A, N = h["L"], h["A"], W.N
        c = h["center"]
        if h["type"] == "jug":
            ellipsoid(f"hold_{nm}", c + N * h["d"] * 0.2, (A, L, N), (h["w"] / 2, h["h"] / 2, h["d"] * 0.8), m)
            mid = c + L * h["h"] * 0.36 + N * h["d"] * 0.62
            capsule(f"hold_{nm}_lip", mid - A * h["w"] * 0.33, mid + A * h["w"] * 0.33, 0.017 * h["s"], 0.017 * h["s"], md)
        elif h["type"] in ("edge", "crimp"):
            box(f"hold_{nm}", c + N * h["d"] / 2, (A, L, N), (h["w"] / 2, h["h"] / 2, h["d"] / 2), [m, md], top_axis=1)
        elif h["type"] == "sloper":
            ellipsoid(f"hold_{nm}", c, (A, L, N), (h["w"] / 2, h["h"] / 2, h["d"]), m)
        else:  # chip
            ellipsoid(f"hold_{nm}", c + N * h["d"] * 0.15, (A, L, N), (h["w"] / 2, h["h"] / 2, h["d"] * 0.85), m)
            mid = c + L * h["h"] * 0.32 + N * h["d"] * 0.55
            capsule(f"hold_{nm}_lip", mid - A * h["w"] * 0.25, mid + A * h["w"] * 0.25, 0.007 * h["s"], 0.007 * h["s"], md)


def draw_body(sk, D, W):
    J = sk["J"]
    R = D["r"]
    H = D["H"]
    tf, tb = mat("torso_front", PALETTE["torso_front"]), mat("torso_back", PALETTE["torso_back"])
    for name, c, axes, semi in ell_parts(sk, D):
        ellipsoid_split(name, c, axes, semi, tf, tb)
    capsule("neck", J["neckB"], J["neckT"], R["neck"], R["neck"] * 0.92, mat("neck", PALETTE["neck"]))
    hr, hu, hb = frame(sk["Rh"])
    cone("nose", J["headC"] - hb * D["ell"]["head"][1] * 0.9 - hu * 0.006 * H, -hb, 0.011 * H, 0.04 * H,
         mat("nose", PALETTE["nose"]))
    knee_m = mat("knee", PALETTE["knee"], emit=0.6, rough=0.4)
    for side, arm in sk["arms"].items():
        m, mj = mat(side, PALETTE[side]), mat(side + "_joint", PALETTE[side + "_joint"])
        sphere(f"{side}_shoulder", arm["sh"], R["shoulder"], mj)
        capsule(f"{side}_upper_arm", arm["sh"], arm["elbow"], *R["upper"], m)
        sphere(f"{side}_elbow", arm["elbow"], R["elbow"], mj)
        capsule(f"{side}_forearm", arm["elbow"], arm["wrist"], *R["fore"], m)
        sphere(f"{side}_wrist", arm["wrist"], R["wrist"], mj)
        hand(f"{side}_hand", arm, D, m, mj)
    for side, leg in sk["legs"].items():
        m, mj = mat(side, PALETTE[side]), mat(side + "_joint", PALETTE[side + "_joint"])
        sphere(f"{side}_hip", leg["hip"], R["hip"], mj)
        capsule(f"{side}_thigh", leg["hip"], leg["knee"], *R["thigh"], m)
        sphere(f"{side}_knee", leg["knee"], R["knee"], mj)
        capsule(f"{side}_shin", leg["knee"], leg["ankle"], *R["shin"], m)
        sphere(f"{side}_ankle", leg["ankle"], R["ankle"], mj)
        q = leg["pole_q"]
        disc(f"{side}_kneecap", leg["knee"] + q * R["knee"] * 0.80, q, 0.042 * D["k"], 0.014 * D["k"], knee_m)
        shoe(f"{side}_shoe", leg["ankle"], leg["f"], leg["u"], leg["side"], D["k"] * (0.94 if D["woman"] else 1.0), m)


def frame_points(sk, holds, W):
    J = sk["J"]
    pts = [v for v in J.values()]
    pts += [J["headC"] + Vector((0, 0, 0.13))]
    for a in sk["arms"].values():
        pts += [a["elbow"], a["wrist"], a["contact"]]
    for l in sk["legs"].values():
        pts += [l["knee"], l["ankle"], l["contact"], l["ankle"] + l["f"] * 0.21]
    for h in holds.values():
        pts.append(h["center"])
    for key in ("hipC", "headC"):
        p = J[key]
        pts.append(p - W.N * (p.dot(W.N) + 0.05))  # point just behind the wall surface
    return pts


def setup_world_and_lights(pose, args):
    sc = bpy.context.scene
    world = bpy.data.worlds.new("world")
    sc.world = world
    bg = hex2lin((pose.get("render") or {}).get("background", PALETTE["bg"]))
    fill = hex2lin(PALETTE["fill"])
    world.color = bg[:3]
    try:
        world.use_nodes = True
    except Exception:
        pass
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    b_cam = nt.nodes.new("ShaderNodeBackground")
    b_cam.inputs[0].default_value = bg
    b_light = nt.nodes.new("ShaderNodeBackground")
    b_light.inputs[0].default_value = fill
    b_light.inputs[1].default_value = float((pose.get("render") or {}).get("ambient", 0.55))
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(b_light.outputs[0], mix.inputs[1])
    nt.links.new(b_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    ls = pose.get("light") or {}
    az, el = math.radians(float(ls.get("azimuth", -35))), math.radians(float(ls.get("elevation", 48)))
    src = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    key = bpy.data.lights.new("key", "SUN")
    key.energy = float(ls.get("strength", 3.2))
    key.angle = math.radians(float(ls.get("softness_deg", 6)))
    try:
        key.use_shadow = True
    except Exception:
        pass
    ko = bpy.data.objects.new("key", key)
    sc.collection.objects.link(ko)
    ko.rotation_euler = (-src).to_track_quat("-Z", "Y").to_euler()
    return src


def setup_render(args, light_src):
    sc = bpy.context.scene
    rx, ry = (int(v) for v in args.size.lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.film_transparent = False
    if args.engine == "eevee":
        ok = False
        for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try:
                sc.render.engine = e
                ok = True
                break
            except TypeError:
                continue
        if not ok:
            raise RuntimeError("EEVEE not available")
        ee = sc.eevee
        for attr, val in (("taa_render_samples", args.samples), ("use_shadows", True), ("use_gtao", True),
                          ("use_raytracing", False), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                          ("use_soft_shadows", True)):
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
    elif args.engine == "cycles":
        sc.render.engine = "CYCLES"
        sc.cycles.samples = args.samples
        try:
            sc.cycles.use_denoising = True
        except Exception:
            pass
    else:
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_shadows = True
        sh.shadow_intensity = 0.45
        sh.show_cavity = True
        sh.cavity_type = "WORLD"
        sh.background_type = "WORLD"
        sc.display.light_direction = tuple(light_src.normalized())
        try:
            sc.display.render_aa = "16"
        except Exception:
            pass
    try:
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
    except Exception:
        pass


def camera_basis(direction):
    """direction: unit vector from target to camera."""
    fwd = -direction
    up_ref = Vector((0, 0, 1))
    if abs(fwd.dot(up_ref)) > 0.995:
        up_ref = Vector((0, 1, 0))  # top view: image-up = into the wall
    right = fwd.cross(up_ref).normalized()
    up = right.cross(fwd).normalized()
    return right, up, fwd


def place_camera(cam_ob, spec, W, sk, holds, aspect, view=None):
    pts = frame_points(sk, holds, W)
    margin = float(spec.get("margin", 0.86))
    if view == "front":
        az, el, ortho = 0.0, 0.0, True
    elif view == "side":
        az, el, ortho = 90.0, 0.0, True
    elif view == "top":
        az, el, ortho = 0.0, 90.0, True
    else:
        az, el = float(spec.get("azimuth", 35)), float(spec.get("elevation", 8))
        ortho = bool(spec.get("ortho", False))
    a, e = math.radians(az), math.radians(el)
    direction = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))).normalized()
    if view is None and spec.get("position") is not None:
        cpos = W.p(spec["position"])
    else:
        cpos = None
    tgt_spec = spec.get("target", "auto") if view is None else "auto"
    if isinstance(tgt_spec, (list, tuple)):
        target = W.p(tgt_spec)
    elif tgt_spec == "pelvis":
        target = sk["J"]["hipC"].copy()
    else:
        target = sum(pts, Vector()) / len(pts)
    if cpos is not None:
        direction = (cpos - target).normalized()
    right, up, fwd = camera_basis(direction)
    cam = cam_ob.data
    lens = float(spec.get("lens", 50)) if view is None else 50.0
    cam.lens = lens
    cam.sensor_fit = "AUTO"
    cam.sensor_width = 36.0
    tanh = 18.0 / lens
    tanv = tanh / aspect
    if tgt_spec == "auto" and cpos is None:
        for _ in range(3):  # re-centre on the bbox in the image plane
            xs = [(p - target).dot(right) for p in pts]
            ys = [(p - target).dot(up) for p in pts]
            target = target + right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
    xs = [(p - target).dot(right) for p in pts]
    ys = [(p - target).dot(up) for p in pts]
    zs = [(p - target).dot(direction) for p in pts]
    if ortho:
        cam.type = "ORTHO"
        wspan = max(max(abs(x) for x in xs) * 2, max(abs(y) for y in ys) * 2 * aspect) / margin
        cam.ortho_scale = max(wspan, float(spec.get("min_ortho_span", 1.6)))
        dist = 12.0
    else:
        cam.type = "PERSP"
        dist = spec.get("distance") if view is None else None
        if dist is None:
            dist = max(max(z + abs(x) / (tanh * margin), z + abs(y) / (tanv * margin)) for x, y, z in zip(xs, ys, zs))
            dist = max(dist, 1.0)
        dist = float(dist)
    pos = cpos if cpos is not None else target + direction * dist
    cam.clip_start = 0.05
    cam.clip_end = 200.0
    if view == "top":
        top_z = max(p.z for p in pts) + 0.12
        cam.clip_start = max(0.05, pos.z - top_z)
    M = Matrix(((right.x, up.x, -fwd.x, pos.x), (right.y, up.y, -fwd.y, pos.y),
                (right.z, up.z, -fwd.z, pos.z), (0, 0, 0, 1)))
    cam_ob.matrix_world = M
    return dict(view=view or "main", azimuth=az, elevation=el, ortho=ortho,
                position=wl(W, pos), target=wl(W, target), lens=lens,
                distance=round((pos - target).length, 3))


def render_to(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def make_sheet(paths, out, size):
    import numpy as np
    rx, ry = size
    hw, hh = rx // 2, ry // 2
    canvas = np.zeros((ry, rx, 4), dtype=np.float32)
    canvas[..., 3] = 1.0
    slots = [(0, 1), (1, 1), (0, 0), (1, 0)]  # (col, row-from-bottom): main TL, front TR, side BL, top BR
    for pth, (cx, cy) in zip(paths, slots):
        img = bpy.data.images.load(pth)
        img.scale(hw, hh)
        px = np.empty(hw * hh * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        canvas[cy * hh:(cy + 1) * hh, cx * hw:(cx + 1) * hw] = px.reshape(hh, hw, 4)
        bpy.data.images.remove(img)
    canvas[hh - 1:hh + 1, :, :3] = 1.0
    canvas[:, hw - 1:hw + 1, :3] = 1.0
    im = bpy.data.images.new("sheet", rx, ry, alpha=False)
    im.pixels.foreach_set(canvas.ravel())
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()


# ----------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="mannequin")
    ap.add_argument("pose", help="pose JSON file")
    ap.add_argument("-o", "--out", help="output PNG (default: next to the pose, .png)")
    ap.add_argument("--size", default="1536x1024")
    ap.add_argument("--views", action="store_true", help="also render _front, _side, _top check views (ortho)")
    ap.add_argument("--sheet", action="store_true", help="also write _sheet.png (main/front/side/top 2x2); implies --views")
    ap.add_argument("--engine", default="eevee", choices=["eevee", "workbench", "cycles"])
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--az", type=float)
    ap.add_argument("--el", type=float)
    ap.add_argument("--dist", type=float)
    ap.add_argument("--lens", type=float)
    ap.add_argument("--check", action="store_true", help="solve + report only, no render")
    ap.add_argument("--strict", action="store_true", help="exit 3 if a target is out of reach or a part pierces the wall")
    ap.add_argument("--blend", help="also save the scene as .blend")
    args = ap.parse_args(argv)
    if args.sheet:
        args.views = True

    with open(args.pose) as fh:
        pose = json.load(fh)
    out = os.path.abspath(args.out or os.path.splitext(args.pose)[0] + ".png")
    base = out[:-4] if out.lower().endswith(".png") else out
    W = Wall(pose.get("wall") or {})
    D = body_dims(pose)
    holds = build_holds(pose, W)
    ppos, solved = solve_pelvis(pose, W, D, holds)
    sk = build(pose, W, D, holds, ppos)

    warnings = list(sk["warn"])
    limbs = {}
    for side in ("left", "right"):
        limbs[f"{side}_hand"] = sk["arms"][side]["report"]
        limbs[f"{side}_foot"] = sk["legs"][side]["report"]
    for nm, r in limbs.items():
        if r["has_target"] and not r["reached"]:
            warnings.append(f"{nm}: target OUT OF REACH by {r['shortfall_cm']} cm (limb drawn straight, hand/foot off the hold)")
        if nm.endswith("_foot") and r.get("ankle_shin_vs_sole_normal_deg", 0) > 75:
            warnings.append(f"{nm}: ankle bent {r['ankle_shin_vs_sole_normal_deg']} deg from neutral (check toe_dir/edge)")
    for part, depth in sk["pen"]:
        warnings.append(f"{part} goes {depth * 100:.1f} cm into the wall")
    J = sk["J"]
    pr, pu, pb = frame(sk["Rp"])
    cr, cu, cb = frame(sk["Rc"])
    zl, zr = W.w(J["hip_l"]).z, W.w(J["hip_r"]).z
    report = dict(
        pose=os.path.abspath(args.pose), figure=D["fig"], height=D["H"], wall_angle_deg=W.angle,
        pelvis=dict(pos=ppos, auto_solved=solved, faces=words_of(W, -pb), up=words_of(W, pu)),
        hips=dict(left_hip_wall_dist_cm=round(zl * 100, 1), right_hip_wall_dist_cm=round(zr * 100, 1),
                  closer_to_wall=("right" if zr < zl - 0.02 else "left" if zl < zr - 0.02 else "square")),
        chest=dict(faces=words_of(W, -cb), up=words_of(W, cu)),
        head=sk["head"], limbs=limbs,
        joints={k: wl(W, v) for k, v in J.items()},
        penetrations=[dict(part=p, depth_cm=round(d * 100, 1)) for p, d in sk["pen"]],
        warnings=warnings, outputs=[], cameras=[])
    for k_, v in (("left_elbow", sk["arms"]["left"]["elbow"]), ("right_elbow", sk["arms"]["right"]["elbow"]),
                  ("left_knee", sk["legs"]["left"]["knee"]), ("right_knee", sk["legs"]["right"]["knee"])):
        report["joints"][k_] = wl(W, v)

    log(f"pelvis {'(auto) ' if solved else ''}{ppos}  faces: {report['pelvis']['faces']}  hips closer to wall: {report['hips']['closer_to_wall']}")
    log(f"chest faces: {report['chest']['faces']}  gaze: {sk['head']['gaze']}")
    for nm, r in limbs.items():
        jn = "knee" if nm.endswith("foot") else "elbow"
        log(f"{nm:10s} reached={r['reached']!s:5s} ext={r['extension']:.2f} {jn} {r[jn + '_angle_deg']:.0f}deg points: {r[jn + '_points']}"
            + (f"  edge={r['edge']} toes: {r['toes_point']}" if "edge" in r else ""))
    for w_ in warnings:
        log("WARNING", w_)

    if not args.check:
        clear_scene()
        draw_wall(pose, W, holds, sk)
        draw_body(sk, D, W)
        light_src = setup_world_and_lights(pose, args)
        setup_render(args, light_src)
        cam = bpy.data.cameras.new("cam")
        cam_ob = bpy.data.objects.new("cam", cam)
        bpy.context.scene.collection.objects.link(cam_ob)
        bpy.context.scene.camera = cam_ob
        rx, ry = (int(v) for v in args.size.lower().split("x"))
        cspec = dict(pose.get("camera") or {})
        for a_, k_ in ((args.az, "azimuth"), (args.el, "elevation"), (args.dist, "distance"), (args.lens, "lens")):
            if a_ is not None:
                cspec[k_] = a_
        jobs = [(None, base + ".png")]
        if args.views:
            jobs += [(v, f"{base}_{v}.png") for v in ("front", "side", "top")]
        for view, path in jobs:
            up_wall = bpy.data.objects.get("wall_upper")
            if up_wall is not None:
                up_wall.hide_render = (view == "top")
            info = place_camera(cam_ob, cspec, W, sk, holds, rx / ry, view)
            render_to(path)
            report["outputs"].append(path)
            report["cameras"].append(info)
            log("wrote", path)
        if args.sheet:
            sp = base + "_sheet.png"
            make_sheet([p for _, p in jobs], sp, (rx, ry))
            report["outputs"].append(sp)
            log("wrote", sp)
        if args.blend:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
    rp = base + ".report.json"
    with open(rp, "w") as fh:
        json.dump(report, fh, indent=1)
    log("report", rp)
    bad = any(r["has_target"] and not r["reached"] for r in limbs.values()) or sk["pen"]
    if args.strict and bad:
        sys.exit(3)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # make failures visible and non-zero in -b mode
        import traceback
        traceback.print_exc()
        log("ERROR", e)
        sys.exit(2)
