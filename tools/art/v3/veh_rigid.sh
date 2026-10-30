#!/bin/bash
# Re-run stl_hd's fit for a vehicle (v3_rigid.py) from tools/art/v3/<unit>_veh.json. usage: veh_rigid.sh <unit> <thingId>
set -e
cd "$(dirname "$0")/../../.."
f=$(ls "$HOME"/craft/solid/mc2/tv_stl/$2/x/files/*.stl | head -1)
systemd-run --user --scope -q -p MemoryMax=14G -p MemorySwapMax=0 python3 -I tools/art/v3/v3_rigid.py "$1" --stl "$f" --joints tools/art/v3/$1_veh.json --kind vehicles 2>&1 | grep -E "fit:|mount|rigid fit"
