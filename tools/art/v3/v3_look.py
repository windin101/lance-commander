"""Look-up views for setting a mech up in v3 (pivots, segments, weapons): the raw sculpt in game mm with a grid.
    python3 -I tools/art/v3/v3_look.py <mech> NAME cx,cy,cz SPAN views [step]"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import v3_common as C, v3_mech as M
mech, name, c, span, views = sys.argv[1:6]
step = int(sys.argv[6]) if len(sys.argv) > 6 else 250
cfg = M.load_cfg(mech)
W = Path(f"/mnt/nvme1n1p1/mc2-rework/v3/{mech}"); W.mkdir(parents=True, exist_ok=True)
if not (W / "look.npz").exists():
    P, F, k = C.sculpt_in_game(Path(cfg["stl"]).expanduser(), k=cfg["k"], turn=cfg.get("turn", False), yaw=cfg.get("yaw", 0.0))
    np.savez(W / "look.npz", P=P, F=F, col=np.full((len(F), 3), 0.75))
    print("bounds", P.min(0).round(), P.max(0).round())
C.blender("views", W / "look.npz", W / name, "--views", views, "--size", "1000", "--centre", c, "--span", span)
meta = json.load(open(W / f"{name}.json"))
for v in views.split(","):
    C.grid_overlay(W / f"{name}_{v}.png", meta, v, step=step, label_every=step * 2 if step < 500 else 1000, out=W / f"{name}g_{v}.png")
print(W)
