# Lance Commander – Battle for the Sphere

A free, non-commercial remake of MechCommander 2 (2001) in Godot 4.7, with modern
graphics and updated gameplay (heat is back on). It is built on Microsoft's 2006
Shared Source release of MechCommander 2.

## Licence ground rules

- **Never commercial.** No sales, paid access, or payment-gated builds.
- **Branding:** no "MechCommander" or "BattleTech" in the title, logo or branding.
- **Original-derived data** (`game/data/`, converted assets) stays under
  Microsoft's Shared Source Limited Permissive License: see
  [docs/MC2-SOURCE-EULA.md](docs/MC2-SOURCE-EULA.md). Its notices must be kept.
- **Our own code** is written fresh from reading the reference code, not copied.
- **New art of BattleTech designs** depends on fan-project tolerance from the IP
  holders.

## Layout

- `game/`: the Godot project. `scripts/sim/` holds the headless rules and
  `scripts/data/game_data.gd` is the data loader.
- `tools/convert/`: Python converters (standard library only) from the source
  release to JSON.
- `docs/`: the feasibility study and plan (`feasibility.md`).
- `reference/` (gitignored): the source release and alariq's port, treated as
  read-only and untrusted.

## Commands

    ~/.local/bin/godot --path game                        # play mc2_01 (left-click/drag select, right-click move/attack, H hold, WASD/QE/wheel camera)

    python3 -I tools/convert/convert_all.py               # regenerate game/data
    python3 -I -m unittest discover -s tools/convert      # converter tests
    tools/run_tests.sh                                    # Godot tests (gdUnit4)
