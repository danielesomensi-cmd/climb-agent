#!/usr/bin/env python3
"""OpenRouter image generation with a shared spend ledger and hard budget cap.
usage: gen.py --model M --prompt-file P --out OUT.png [--ref img ...] [--aspect 16:9] [--tag label]
Prints JSON {ok, out, cost, total_spent}. Refuses when ledger total >= cap."""
import argparse, base64, fcntl, json, os, pathlib, sys, time, urllib.request, mimetypes
ROOT = pathlib.Path(os.environ.get("IMG_WORKDIR", pathlib.Path(__file__).resolve().parent / "work"))
ROOT.mkdir(parents=True, exist_ok=True)
LEDGER = ROOT / "ledger.jsonl"
CAP = float(os.environ.get("IMG_BUDGET_CAP", "4.5"))
def key():
    # OPENROUTER_API_KEY from the environment, else from the .env named by
    # OPENROUTER_ENV_FILE (default: Daniele's fin-sycophancy .env). Never printed.
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in open(os.path.expanduser(os.environ.get("OPENROUTER_ENV_FILE", "~/Projects/fin-sycophancy/.env"))):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
def live_remaining():
    """USD still spendable now: min(key daily limit left, account credits left). OpenRouter reserves a
    request's maximum cost up front, so a call can be refused while the local ledger still shows room."""
    def get(path):
        req = urllib.request.Request("https://openrouter.ai/api/v1/" + path, headers={"Authorization": "Bearer " + key()})
        return json.load(urllib.request.urlopen(req, timeout=30))["data"]
    try:
        k, c = get("key"), get("credits")
    except Exception:
        return None
    left = [c["total_credits"] - c["total_usage"]]
    if k.get("limit_remaining") is not None:
        left.append(k["limit_remaining"])
    return min(left)
def spent():
    if not LEDGER.exists(): return 0.0
    return sum(json.loads(l).get("cost") or 0 for l in LEDGER.read_text().splitlines() if l.strip())
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--prompt-file", required=True)
ap.add_argument("--out", required=True); ap.add_argument("--ref", nargs="*", default=[])
ap.add_argument("--aspect", default="16:9", help="'none' to omit image_config"); ap.add_argument("--tag", default="")
a = ap.parse_args()
lock = open(ROOT / ".lock", "w"); fcntl.flock(lock, fcntl.LOCK_EX)
s = spent()
if s >= CAP:
    print(json.dumps({"ok": False, "error": f"budget cap reached: spent {s:.3f} >= {CAP}"})); sys.exit(2)
live = live_remaining()
MIN_LEFT = float(os.environ.get("IMG_MIN_REMAINING", "0.25"))
if live is not None and live < MIN_LEFT:
    print(json.dumps({"ok": False, "error": f"OpenRouter budget left {live:.3f} < {MIN_LEFT} (key daily limit or credits)"})); sys.exit(2)
fcntl.flock(lock, fcntl.LOCK_UN)
content = [{"type": "text", "text": pathlib.Path(a.prompt_file).read_text()}]
for r in a.ref:
    mt = mimetypes.guess_type(r)[0] or "image/png"
    content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64," + base64.b64encode(open(r, "rb").read()).decode()}})
body = {"model": a.model, "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"], "usage": {"include": True},
        **({} if a.aspect == "none" else {"image_config": {"aspect_ratio": a.aspect}})}
req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
      headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"})
t0 = time.time()
try:
    resp = json.load(urllib.request.urlopen(req, timeout=300))
except urllib.error.HTTPError as e:
    print(json.dumps({"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:400]}"})); sys.exit(1)
cost = (resp.get("usage") or {}).get("cost")
msg = resp["choices"][0]["message"]; imgs = msg.get("images") or []
outp = pathlib.Path(a.out); outp.parent.mkdir(parents=True, exist_ok=True)
saved = []
for i, im in enumerate(imgs):
    url = im["image_url"]["url"]; head, data = url.split(",", 1); b = base64.b64decode(data)
    ext = {"image/svg+xml": ".svg", "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(head[5:].split(";")[0], outp.suffix)
    p = (outp if i == 0 else outp.with_name(outp.stem + f"_{i}")).with_suffix(ext)
    p.write_bytes(b); saved.append(str(p))
fcntl.flock(lock, fcntl.LOCK_EX)
with open(LEDGER, "a") as f:
    f.write(json.dumps({"t": time.time(), "model": a.model, "tag": a.tag, "out": saved, "cost": cost, "secs": round(time.time() - t0, 1)}) + "\n")
print(json.dumps({"ok": bool(saved), "out": saved, "cost": cost, "total_spent": round(spent(), 4),
                  "text": (msg.get("content") or "")[:200]}))
