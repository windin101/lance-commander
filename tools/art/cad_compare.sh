#!/usr/bin/env bash
# Comparison sheet for a CAD-rebuilt building: rows original | upscaled (_hdtex) | SolidCraft (_cad),
# columns game distance | close up | close up from the other side.
#
#   tools/art/cad_compare.sh <app> <focus_x>,<focus_z> <focus_y> <far_dist> <near_dist> [out.png]
#
# Renders with the model viewer under the swarm GPU lock; run `godot --headless --import --path game` first
# after writing a new .glb. Default output: swarm/gallery/cad_<app>.png.
set -euo pipefail
app=$1; xz=$2; fy=$3; far=$4; near=$5
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${6:-$root/swarm/gallery/cad_$app.png}
L="$HOME/Code/remake-kit/bin/swarm lock godot -- flock $root/.godot.lock $HOME/.local/bin/godot"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cd "$root"
row=()
for kind in "" _hdtex _cad; do
  cols=()
  for cam in "35,40,$far" "35,22,$near" "215,22,$near"; do
    f="$tmp/${kind:-_orig}_${cam//,/_}.png"
    $L --path game res://scenes/model_viewer.tscn -- --screenshot="$f" --frames=12 --cam="$cam" --fov=30 \
      --focus-y="$fy" --focus-xz="$xz" --bg=1,1,1 --model="res://assets/objects/${app}${kind}.glb" >/dev/null 2>&1
    magick "$f" -resize 800x450 "$f"
    cols+=("$f")
  done
  label=${kind:-original}; label=${label#_}
  [ "$label" = hdtex ] && label="upscaled (_hdtex)"
  [ "$label" = cad ] && label="SolidCraft (_cad)"
  magick "${cols[@]}" +append -gravity NorthWest -pointsize 28 -fill black -annotate +12+8 "$app: $label" "$tmp/row${#row[@]}.png"
  row+=("$tmp/row${#row[@]}.png")
done
mkdir -p "$(dirname "$out")"
magick "${row[@]}" -append "$out"
echo "$out"
