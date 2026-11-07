"""Build pose_composite_side.png: mannequin render (navy bg, narrow wall panel) -> navy #1F2633 + soft spotlight,
wall panel cut a little below the lowest foothold (projected from the camera in the report)."""
import json, math, sys
import numpy as np
from PIL import Image

src, rep, out = sys.argv[1], sys.argv[2], sys.argv[3]
ycut = float(sys.argv[4]) if len(sys.argv) > 4 else 0.14
im = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
H, Wd = im.shape[:2]
r = json.load(open(rep))
cam = r['cameras'][0]
a = math.radians(20)
X = np.array([1, 0, 0.]); U = np.array([0, -math.sin(a), math.cos(a)]); N = np.array([0, -math.cos(a), -math.sin(a)])
P = lambda w: X * w[0] + U * w[1] + N * w[2]
pos, tgt = P(cam['position']), P(cam['target'])
d = (pos - tgt); d /= np.linalg.norm(d)
fwd = -d
right = np.cross(fwd, [0, 0, 1.]); right /= np.linalg.norm(right)
up = np.cross(right, fwd)
tanh = 18.0 / cam['lens']; tanv = tanh / (Wd / H)

def proj(w):
    v = P(w) - pos
    xc, yc, zc = v @ right, v @ up, v @ fwd
    return (xc / zc / tanh * Wd / 2 + Wd / 2, H / 2 - yc / zc / tanv * H / 2)

# bottom edge line of the cut panel
x0, y0 = proj((-2.0, ycut, 0)); x1, y1 = proj((2.0, ycut, 0))
yy, xx = np.mgrid[0:H, 0:Wd].astype(np.float32)
# signed distance below the line (pixels)
nx, ny = -(y1 - y0), (x1 - x0)
L = math.hypot(nx, ny); nx, ny = nx / L, ny / L
if ny < 0: nx, ny = -nx, -ny
sd = (xx - x0) * nx + (yy - y0) * ny
below = np.clip(sd + 0.5, 0, 1)  # 1 = below the cut line

navy = np.array([31, 38, 51], np.float32)
spot_c = np.array([49, 58, 75], np.float32)
dist = np.linalg.norm(im - navy, axis=2)
bgness = np.clip(1 - dist / 38.0, 0, 1)
bgness = np.maximum(bgness, below)
cx, cy, rx, ry = Wd / 2, H / 2, 640.0, 590.0
t = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
s = np.clip((1.0 - t) / 0.45, 0, 1); s = s * s * (3 - 2 * s)
bg = navy[None, None] + (spot_c - navy)[None, None] * s[..., None]
base = np.where(below[..., None] > 0, bg, im)
res = base * (1 - bgness[..., None]) + bg * bgness[..., None]
# keep exact pixels for non-background
Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8)).save(out)
print('cut line', (round(x0), round(y0)), (round(x1), round(y1)))
