#!/bin/bash
# Studio renders of v3 (and v1) models through game/scenes/art_gallery.tscn with --art-v3 (the bay's own studio,
# v3 lighting). Usage: tools/art/v3/v3_gallery.sh JOB.json [extra godot user args]
set -e
cd "$(dirname "$0")/../../.."
job="$1"; shift
timeout 600 "$HOME/Code/remake-kit/bin/swarm" lock godot -- flock .godot.lock "$HOME/.local/bin/godot" --path game \
  res://scenes/art_gallery.tscn -- --art-v3 --job="$job" "$@" 2>&1 | grep -vE "radv is not a conformant|^$" | tail -5
