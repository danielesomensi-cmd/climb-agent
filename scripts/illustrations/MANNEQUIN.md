# mannequin.py: 3D pose reference for climbing drills

Renders a colour-coded 3D mannequin on a climbing wall with headless Blender (5.2, EEVEE).
Its purpose is a **pose reference** for image generation, where text prompts and 2D sketches get depth
rotations wrong (drop knee vs high step, hip turned in vs square). The geometry comes from analytic
two-bone IK with pole vectors, so knee and elbow directions are explicit and checkable.

## Command line

```bash
IMG=/private/tmp/claude-501/-Users-danielesomensi-Projects-climb-agent/fd279fef-aa87-45f0-82b3-b23725dda4a4/scratchpad/imggen
$IMG/bin/mannequin POSE.json -o OUT.png [--views] [--sheet] [--check] [--strict]
                   [--size 1536x1024] [--engine eevee|workbench|cycles] [--samples 48]
                   [--az DEG] [--el DEG] [--dist M] [--lens MM] [--blend scene.blend]

# equivalent raw call (the wrapper adds -q --factory-startup and < /dev/null)
/Applications/Blender.app/Contents/MacOS/Blender -b -q --factory-startup --python-exit-code 2 \
    -P $IMG/bin/mannequin.py -- POSE.json -o OUT.png --sheet < /dev/null
```

| flag | effect |
|---|---|
| `--views` | also writes `OUT_front.png` (orthographic, from straight behind the climber), `OUT_side.png` (orthographic, from the climber's right, wall on the image right) and `OUT_top.png` (orthographic, from above, wall at the image top, wall above hip height hidden so an overhang cannot cover the body) |
| `--sheet` | implies `--views`, plus `OUT_sheet.png`: a 2x2 grid with main at top-left, front at top-right, side at bottom-left and top at bottom-right. It is the cheapest single image to Read for a check. |
| `--check` | solves and writes the report only, with no render (about 1.5 s) |
| `--strict` | exits 3 if any target is out of reach or a body part pierces the wall |
| `--az/--el/--dist/--lens` | override the JSON camera |

Always written: `OUT.report.json`, plus `[mannequin] ...` lines on stdout (pelvis, chest, gaze, every
limb's reach and joint direction, and WARNINGs). Exit codes: 0 ok, 2 error (bad JSON, unknown hold or word),
3 `--strict` failure. Render time is about 2 s per view at 1536x1024 with EEVEE.

## Conventions

**Left and right are always the climber's own.** The default camera stands behind the climber, so the
climber's left appears on the image left.

**Wall coordinates** `[x, y, z]`, in metres:
- `x`: along the wall, + toward the climber's right (when the climber faces the wall).
- `y`: **up the wall surface** from its base (the floor line). On an overhang this axis is tilted with the wall.
- `z`: perpendicular out of the wall toward the climber. 0 is the wall surface. Hip centres usually sit at 0.25-0.45.

**Wall angle** `angle_deg`: 0 = vertical, + = overhanging (the top leans over the climber, 90 = roof),
− = slab.

**Body angles** are in degrees, relative to the wall. At 0 the climber faces the wall squarely.
- `pelvis.yaw` + = the pelvis turns to the climber's **left**, so the **right hip goes into the wall**
  (hip-turn / backstep / drop-knee side). − = left hip into the wall.
- `pelvis.pitch` + = leans forward, top of the pelvis toward the wall. `pelvis.roll` + = tilts to the climber's right.
- `chest.twist`, `chest.bend`, `chest.side` use the same signs, measured relative to the pelvis. The abdomen
  takes half of each.
- `head.yaw` + = looks left, `head.pitch` + = looks up (relative to the chest), `head.tilt` + = ear to the right shoulder.
  The neck is clamped to ±80° yaw and −55..+65° pitch, and the report says when it clamps.

**Direction words**, used for poles. Combine them with `+`, and weight them with `0.5*word`. A leading `-` negates.
- Wall frame: `left right up down in` (= into the wall) `away` (= away from the wall).
- Limb side: `outward` / `inward` (along wall x, away from or toward the body midline, for that limb's side).
- Body frame (pelvis for legs, chest for arms): `fwd back bodyup bodydown bodyout bodyin`.
- Instead of words you can pass a raw vector `[dx, dy, dz]` in wall coordinates.

**Hold lip** `lip`: the direction the gripping surface **faces**: `"up"` (jug or edge you pull down on),
`"down"` (undercling), `"left"`, `"right"`, `"up-left"`, and so on, or degrees in the wall plane (0 = right, 90 = up).
A sidepull or layback on your left faces **left** (away from you). A gaston faces **toward** the body.

### Colour code (how to read a render)
| element | colour | what it tells you |
|---|---|---|
| left arm, leg, hand | blue (joints darker blue) | |
| right arm, leg, hand | red (joints darker red) | |
| torso, pelvis, head **front** | light grey | rotation: the more light grey you see from behind, the more that side is turned toward the camera |
| torso, pelvis, head **back** | dark grey | |
| nose cone on the face | black | gaze direction |
| kneecap disc | bright yellow | where the knee points. Facing down = drop knee. Facing up or out = high step or frog. Invisible from behind = the knee points into the wall. |
| shoe **outside** (little-toe) half | orange | |
| shoe **inside** (big-toe) half | white | |
| shoe sole / strap | near-black / limb colour | |
| holds | green jug/chip, purple edge/crimp, teal sloper; the darker strip or face marks the lip | |

Reading feet from behind: on an **inside edge** the white half faces the wall, so you see **orange**.
On an **outside edge** (backstep, drop knee) you see **white**.

## JSON schema

Keys starting with `_` (for example `_comment`) are ignored. Every field is optional except where noted.

```jsonc
{
  "figure": "man",              // "man" (default height 1.78) | "woman" (1.66, narrower shoulders, wider pelvis)
  "height": 1.78,               // metres; scales everything
  "ape_index": 1.0,             // span / height; lengthens or shortens the arms only

  "wall": {
    "angle_deg": 0,             // + overhang, − slab
    "width": 7.0, "height": 5.0, "x_center": 0.0,
    "color": "#d3d6da",
    "floor": true               // floor plane at the wall base (y = 0)
  },

  "holds": {                    // name -> hold; names are referenced by limbs, look_at
    "R": {
      "type": "jug",            // jug | edge | crimp | sloper | chip  (aliases: foot, foot_chip, foothold -> chip; bucket -> jug; rail -> edge)
      "pos": [0.35, 2.05],      // REQUIRED, wall x, y of the hold's base centre
      "lip": "up",              // direction the gripping face points (see Conventions)
      "size": 1.0,              // scale factor
      "color": "#22a35a",
      "grip_offset": [0, 0, 0]  // shift the grip point (wall coords)
    }
  },

  "pelvis": {
    "pos": [0.0, 1.3, 0.32],    // hip-joint centre, wall coords. Any component may be null -> solved
    "auto": true,               // true = solve x, y, z; or a string like "yz" for those axes only
    "yaw": 0, "pitch": 0, "roll": 0,
    "z_pref": 0.30,             // solver's preferred distance from the wall (default 0.30 + 0.25*sin(overhang))
    "x_pref": 0.0               // solver's preferred x (default: mean x of all limb targets)
  },
  "chest": {"twist": 0, "bend": 0, "side": 0},
  "head":  {"look_at": "T"},    // hold name | "left_hand"/"right_hand"/"left_foot"/"right_foot" | [x,y,z]
                                // or {"yaw": 0, "pitch": 10, "tilt": 0}

  "left_hand": {                // same keys for right_hand. Omit the hand -> the arm hangs at the side
    "hold": "R",                // OR "pos": [x, y, z] (where the finger pads are; z = 0 is the wall surface)
    "offset": [0, 0, 0],        // added to the target point
    "pole": "down+0.5*outward", // where the ELBOW points. Default: bodydown + 0.5*bodyout + 0.3*back
    "pole_point": [x, y, z],    // alternative: the elbow aims at this point
    "lip": "up",                // overrides the hold's lip for the hand orientation
    "open": false,              // true = flat open hand, fingers pointing along the reach
    "wrap_deg": 35,             // how far the fingers wrap into the wall over the lip
    "curl_deg": 75,             // finger curl (default 75 on a hold, 12 open, 20 hanging)
    "fingers": [dx,dy,dz],      // explicit finger direction (wall coords)
    "palm":    [dx,dy,dz],      // explicit palm-facing direction
    "roll_deg": 0,              // roll the hand about the finger axis
    "straight": false,          // pelvis solver tries hard to make this arm straight
    "reach": 0.9                // solver's preferred extension (distance / arm length)
  },

  "left_foot": {                // same keys for right_foot. Omit the foot -> the leg hangs
    "hold": "F",                // OR "pos": [x, y, z] (contact point; z = 0 = smearing on bare wall)
    "offset": [0, 0, 0],
    "edge": "inside",           // toe|front | inside | outside | heel | toe_hook | smear: which part of the shoe touches
    "turn_deg": 55,             // inside/outside: how far the toes turn from pointing into the wall
    "pole": "down+0.3*left",    // where the KNEE points. Default: fwd + 0.6*bodyout + 0.2*bodyup
    "pole_point": [x, y, z],
    "toe_dir": [dx,dy,dz],      // explicit toe direction (wall coords)
    "sole_up": [dx,dy,dz],      // explicit sole -> instep direction
    "roll_deg": 0,              // roll about the toe axis (+ = little-toe edge down)
    "ankle": "auto",            // "auto": the shoe rolls about the contact so the ankle stays within
                                //  ankle_limit_deg (default 40) of the shin; "fixed" keeps the edge default
    "straight": false, "reach": 0.78
  },

  "camera": {
    "azimuth": 35,              // 0 = straight behind the climber, + = toward the climber's right, 90 = side
    "elevation": 8,             // degrees above horizontal
    "distance": null,           // null = auto-fit the body, used holds and wall in frame
    "target": "auto",           // "auto" (frame centre) | "pelvis" | [x, y, z]
    "position": [x, y, z],      // explicit camera position (wall coords), overrides azimuth and elevation
    "lens": 50, "ortho": false, "margin": 0.86, "min_ortho_span": 1.6
  },
  "light":  {"azimuth": -35, "elevation": 48, "strength": 3.2, "softness_deg": 6},  // key sun, comes FROM there
  "render": {"background": "#2e3648", "ambient": 0.55}
}
```

Camera presets that match the coach specs:
"rear three-quarter from the climber's right, about 40°, lens at hip height" -> `{"azimuth": 40, "elevation": 3, "target": "pelvis"}`.
"Straight rear view shifted about 15° right" -> `{"azimuth": 15, "elevation": 3}`.

## Example: right drop knee on a 20° overhang

`imggen/poses/selftest_dropknee.json`:

```json
{
 "figure": "woman",
 "wall": {"angle_deg": 20},
 "holds": {
  "LH": {"type": "jug",  "pos": [-0.35, 1.95], "lip": "up"},
  "T":  {"type": "jug",  "pos": [ 0.35, 2.30], "lip": "up"},
  "LF": {"type": "chip", "pos": [-0.42, 0.62]},
  "RF": {"type": "chip", "pos": [ 0.40, 0.85]}
 },
 "pelvis": {"auto": true, "yaw": 50},
 "chest": {"twist": 10},
 "left_hand":  {"hold": "LH", "straight": true},
 "right_hand": {"hold": "T"},
 "left_foot":  {"hold": "LF", "edge": "inside"},
 "right_foot": {"hold": "RF", "edge": "outside", "pole": "down+0.3*left"},
 "head": {"look_at": "T"},
 "camera": {"azimuth": 15, "elevation": 5}
}
```

stdout: `right_foot reached=True ext=0.57 knee 69deg points: left 0.76, down 0.60 edge=outside` and
`knee_height_vs_foot_cm: 1.2`: the knee points at the floor, level with the foot. That is a drop knee, not a high step.

Recipes for the depth-critical poses. Drop knee was checked by render and high step by `--check`. The others are
starting points: always verify them with `--sheet`.
- **Drop knee (right)**: `pelvis.yaw` +40..+60, right foot `edge: "outside"`, right knee `pole: "down+0.3*left"` (or `"down+in"`).
  Check `knee_points` starts with `down` and `knee_height_vs_foot_cm` is about 0 (never negative for a moderate drop).
- **High step (right)**: right foot high, `pole: "up+0.5*outward"` or `"up+away"`. The yellow disc faces up or out.
- **Hip turned in / backstep (right)**: `pelvis.yaw` about +70..+90, right foot `edge: "outside"`, knee `pole: "left+0.3*down"`.
  Report: `hips.closer_to_wall = "right"`, `chest.faces` starts with `left`.
- **Frog / square**: `yaw: 0`, both feet `edge: "inside"`, knees `pole: "outward+0.3*away"`.
- **Twist-lock arm**: put the hand near the shoulder with `pole: "down+0.3*in"`. A straight hang uses `straight: true`.
- **Flag**: free foot `"pos": [x, y, 0]` (bare wall), `edge: "inside"`, and a pole that keeps the leg from crossing.

## Report (`OUT.report.json`)

- `pelvis.pos` (solved or given), `pelvis.auto_solved`, `pelvis.faces`, `hips.left_hip_wall_dist_cm` and `right_…`, `hips.closer_to_wall`.
- `chest.faces`, `head.{yaw,pitch,clamped,gaze}`.
- `limbs.<name>`: `reached`, `shortfall_cm`, `extension`, `elbow_angle_deg`/`knee_angle_deg` (180 = straight),
  `elbow_points`/`knee_points` (in wall words: `left/right/up/down/into-wall/away-from-wall` with weights),
  the `…_points_body` equivalent, `knee_height_vs_foot_cm`, `edge`, `toes_point`, `ankle_shin_vs_sole_normal_deg`,
  `shoulder_shift_cm` (scapular reach used, at most 3.5 % of height), `target`, `hold`.
- `joints`: every joint in wall coordinates. `penetrations`: body parts more than 1.5 cm into the wall.
- `warnings`: out of reach (the limb is drawn straight, with the hand or foot visibly off its hold), extreme ankle,
  wall penetration, head clamp. `cameras`: the camera used for each output.

Workflow: write the pose, run `--check`, and read the limb lines (reach, `knee_points`). Then render with `--sheet`
and Read `OUT_sheet.png`, using the side and top views to confirm depth (hip to wall, knee direction).
Use `OUT.png` (or a `--views` file) as the reference image.

## Known limitations

- The mannequin is made of capsules and ellipsoids. The torso is three stacked ellipsoids (pelvis, abdomen, chest),
  with no clavicles, scapulae, spine curve or breasts. Hands are a palm, one finger block and a thumb nub, with no
  per-finger grips (pinch, pocket and gaston thumb positions are only approximate). There is no hair and there are no clothes.
- IK is per limb. The pelvis solver is a simple pattern search on reach comfort, wall clearance and preferred
  distance. It does not do balance or centre of gravity, so it is not a physics check: an unbalanced pose renders happily.
- Collision is checked only against the wall plane, never against holds or between body parts. A limb can pass
  through another limb, so check the side and top views.
- Joint limits are not enforced except for the neck (clamped) and the ankle (auto-roll, warning beyond 75°).
  Elbows and knees bend whichever way the pole says, including anatomically impossible hyperextension directions.
- Foot defaults (toe direction per edge) are heuristics. For heel hooks, toe hooks and unusual smears, give `toe_dir`/`sole_up`.
- Holds are simple primitives (no volumes, pockets or pinches), and `lip` only orients them in the wall plane.
- The wall is a single flat panel: no arêtes, dihedrals, kickers or multi-angle boards.
- Top check view: the wall above hip height is hidden so the body stays visible. On overhangs the hand holds
  appear on the climber's side of the wall line, which is correct in projection.
- `--engine workbench` works but looks flat (weak wall contrast). EEVEE is the default and the one that was validated.
