# Exercise illustrations — technique recipe (C285)

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
