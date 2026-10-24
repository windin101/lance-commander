#!/bin/bash
# Re-run the paint and write stages for a v3 mech and re-import it in Godot. Usage: tools/art/v3/v3_install.sh atlas
set -e
cd "$(dirname "$0")/../../.."
python3 -I tools/art/v3/v3_mech.py "$1" --steps "${2:-paint,write}" | tail -3
"$HOME/Code/remake-kit/bin/swarm" lock godot -- flock .godot.lock "$HOME/.local/bin/godot" --headless --import --path game > /dev/null 2>&1
echo imported
