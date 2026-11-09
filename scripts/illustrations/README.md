# Exercise illustrations — the two recipes (C285)

Two ways to make a picture, both kept here:

- **S3 editorial** (below, "Why a 3D mannequin" onward): a 3D mannequin pose painted by an image model.
  Richest look; costs credit; the model can still get a gaze or a grip wrong.
- **Vector plates** (`vector/`, last section): a script draws the athlete in true profile from the joint
  positions. Free, exact, repeatable, plain look. Use it when the lesson reads in profile.


How the `frontend/public/exercises/technique/` pictures are made. Earlier sets (C280-C282) used a local
Z-Image + ControlNet pipeline whose scripts were lost with the session scratchpad: this folder keeps the
C285 tools in the repo on purpose.

## Why a 3D mannequin

Text prompts and 2D stick sketches fail on depth rotations: every model drew the drop knee as a high step
(knee up and out) and the backstep with square hips. A rendered 3D pose fixes it.

## Steps

1. **Pose** — write a pose JSON (schema and conventions in `MANNEQUIN.md`, examples in `poses/`) and render it:
   `./mannequin poses/drop_knee.json -o /tmp/dk.png --sheet --strict` (needs Blender:
   `brew install --cask blender`). The colour code reads the pose: left limbs blue, right red, yellow
   disc = kneecap direction, orange = outside shoe edge, light torso = front.
2. **Camera** — for drills about the hip turned into the wall (backstep, drop knee, hip turn) shoot from the
   OPEN side, front three-quarter (the side the chest faces). From behind, image models always paint a square,
   symmetric pelvis and the lesson disappears.
3. **Coach check** — an adversarial review of the mannequin render against the spec before spending money.
4. **Composite** — mannequin on navy `#1F2633` with a soft spotlight and the grey wall panel (`composite.py`).
5. **Generate** — `gen_images.py --model openai/gpt-image-2` in EDIT framing: IMAGE 1 = the composite,
   IMAGE 2 = a style swatch from `style/` (WebP: the repo ignores PNG). The style swatch must not show legs or a full pose: the model
   copies the pose of a full reference. Prompts in `prompts/` (mannequin colour legend, the pose from this
   viewpoint, known mistakes, outfit). Medium ≈ $0.065, high ≈ $0.19 per image (OpenRouter, Nov 2026).
   Gemini 3 Pro Image copies the reference pose; Gemini Flash and Recraft vector were unusable.
6. **Verify** — an independent adversarial coach tries to refute each candidate (technique, anatomy,
   readability at phone width). Only a candidate that survives ships.
7. **Ship** — 800x400 WebP, whole image fitted and padded with `#1F2633`, mapped in
   `frontend/src/lib/exercise-images.ts` (`CATALOG_EXERCISE_IMAGES`, extra positions in
   `CATALOG_EXERCISE_EXTRA_PANELS`).

## Style

"S3 editorial", chosen by Daniele on 2026-11-07: rich semi-realistic editorial illustration, crisp painterly
rendering, navy background with a soft circular spotlight, teal holds. Attractive, very fit, confident
athletes in real climbing attire (sports-bra crop top and fitted shorts for women; tank top or shirtless for
men), tasteful and never sexualised: the pose is dictated by the technique. Women and men alternate.

## Spend control

`gen.py` / `gen_images.py` append every call to `work/ledger.jsonl` (or `$IMG_WORKDIR`) and refuse once
`$IMG_BUDGET_CAP` (USD) is reached; before every call they also read the live OpenRouter budget (key daily limit and account credits) and refuse below `$IMG_MIN_REMAINING` (default 0.25), because OpenRouter reserves a request's maximum cost against the daily limit up front (C285: a call was refused at $4.45 logged of $5). The key comes from `$OPENROUTER_API_KEY` or the `.env` named by
`$OPENROUTER_ENV_FILE`; it is never printed or committed.

## Vector plates (`vector/`)

Added in the C285 vector batch (2026-11-10) after the image credit ran out and the hard target came back
seen from behind. A plate is a Python function that places the joints in metres and lets the kit draw:

```bash
cd scripts/illustrations/vector
python3 make.py                        # every plate -> frontend/public/exercises/...
python3 make.py pistol_squat v_sit     # only these
python3 make.py --out /tmp/x --png     # elsewhere, with 2x PNG previews to review at full size
```

Needs `numpy`, `Pillow` and `playwright` with Chromium. The SVG is deterministic; the WebP bytes depend on
the Chromium and libwebp versions, so regenerate a picture only when its plate changes.

| File | What it holds |
|---|---|
| `figkit.py` | Geometry and SVG helpers: tapered limbs, soft clipped shading, the canvas (`px`, lateral offset). |
| `athlete.py` | The athlete: skeleton lengths (1.66 m), two looks (woman, man), arms, legs, hands, shoes, harness, knee pad. |
| `props.py` | Wall (any angle, in wall coordinates `s` down / `o` out), footholds, jugs, a volume, mat, bench, rings, rope, quickdraw. |
| `plate.py` | The 800x400 picture and the amber marks: line of sight, ring, magnified detail, measuring bracket, arrow, second small scene. |
| `plates.py` | One function per picture, each with the catalog cues it draws, and the `PLATES` registry (output path, `mirror`). |
| `make.py` | Renders SVG -> WebP (quality 88) and the mirrored `_l` file for one-sided plates. |

Conventions: metres, y up, the athlete faces +x with the wall on the right; overhang angle positive; `L` is
the offset toward the camera (near limbs positive), drawn as a small shift in x. Draw far limbs first.

Rules learned on this batch:

- **Profile or nothing.** If the lesson needs depth (straddle, heel hook, thread the needle) this kit cannot
  show it: leave the exercise without a picture or use the S3 recipe.
- **Keep the face in view.** With both arms overhead the near arm hides the head. Put the far arm high and
  the near hand at chest height with the elbow down (`_low`), or accept the arm across the head.
- **Mark the lesson.** The figure is about 2 cm tall in the player (pictures are at most 140 px high): the
  magnified detail is what the athlete actually reads. One ring, one detail, no text.
- **One picture per claim.** `pocket_rampup_hangboard` says "never a mono": the one-finger drill has its own
  plate (`pocket_rampup_mono`) instead of sharing a profile where two fingers look like one.
- **A picture that changes gets a new file name.** The service worker keeps `/_next/image` responses for
  7 days by URL (`climb-agent-images-v1`), so the same name would keep showing the old drawing
  (`hard_target.webp` -> `hard_target_profile.webp`, `31_dragon_flag_tuck.webp` -> `41_dragon_flag_tuck.webp`).
- **Review at full size.** Open every 2x preview next to the exercise's description and cues before it ships.
  The vector batch had no independent coach review (the S3 plates did): say so when you ship one.

Where the files go: technique drills in `technique/`, strength and non-circuit core moves in `strength/`,
core-circuit exercises in `core/` (every file there must be referenced by `circuit-exercises.ts`). Map them
in `frontend/src/lib/exercise-images.ts`; a one-sided plate also needs its `LEFT_SIDE` entry.
