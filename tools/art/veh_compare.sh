#!/bin/bash
# veh_compare.sh <asset> <out.png> [distance m, default 26] [folder: vehicles|mechs] [anim]
# Godot renders of the original and the HD model side by side: front three-quarter (yaw 35) and rear
# three-quarter (yaw 200), team paint on. Every Godot run takes the swarm godot lock and the repo flock.
V=$1; OUT=$2; D=${3:-26}; F=${4:-vehicles}; AN=${5:-}
cd "$(dirname "$0")/../.."
TMP=$(mktemp -d)
L="$HOME/Code/remake-kit/bin/swarm lock godot -- flock .godot.lock $HOME/.local/bin/godot"
$L --headless --import --path game >/dev/null 2>&1
FY=$(python3 -c "print(max(1.5, $D/17))")
for n in a:35 b:200; do IFS=: read k y <<< "$n"
  for m in $V ${V}_hd; do
    $L --path game res://scenes/model_viewer.tscn -- --screenshot=$TMP/${m}_$k.png --frames=12 --cam=$y,20,$D --fov=18 --focus-y=$FY --bg=1,1,1 \
      --model=res://assets/$F/$m.glb "--paint=${m},-3638744,-12566464,-10851768" ${AN:+--anim=$AN --t=0.3} >/dev/null 2>&1
  done
done
python3 -I - "$TMP" "$V" "$OUT" <<'PY'
import sys
from PIL import Image, ImageDraw
T, V, OUT = sys.argv[1:]
labels = ["original, front 3/4", "HD, front 3/4", "original, rear 3/4", "HD, rear 3/4"]
ims = [Image.open(f"{T}/{m}_{k}.png").convert("RGB") for k in "ab" for m in (V, V + "_hd")]
w, h = ims[0].size
ims = [i.crop((w // 2 - 450, h // 2 - 330, w // 2 + 450, h // 2 + 330)).resize((600, 440)) for i in ims]
s = Image.new("RGB", (2400, 460), "white")
for k, i in enumerate(ims):
    s.paste(i, (600 * k, 0)); ImageDraw.Draw(s).text((600 * k + 6, 444), labels[k], fill="black")
s.save(OUT)
PY
rm -rf "$TMP"; echo "$OUT"
