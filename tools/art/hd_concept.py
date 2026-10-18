"""Step 1 of the HD mech pipeline: restyle an original-model render into an HD
concept image with the same pose and silhouette (Qwen-Image-Edit 2509).
    python3 -I tools/art/hd_concept.py <render.png> <out.png> [seed]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comfy  # noqa: E402

PROMPT = ("Transform this crude low-polygon video game model into a high-end modern 3D render of the same giant "
          "military walking robot, as in a 2025 AAA game. Keep the exact same pose, camera angle, proportions and overall "
          "silhouette, and keep every part in the same place. Replace the flat blocky surfaces with intricate mechanical "
          "detail: many layered armour plates with deep panel seams, recessed vents and grilles, exposed hydraulic pistons "
          "and cables at the knees and hips, articulated toe claws, missile launcher tubes, gun barrels with muzzle brakes, "
          "rivets, warning stencils, scratched and weathered gunmetal grey paint. Physically based materials, crisp studio "
          "lighting, plain white background.")
VEHICLE_PROMPT = ("Transform this crude low-polygon video game model into a high-end modern 3D render of the same "
                  "futuristic military combat vehicle, as in a 2025 AAA game. Keep the exact same shape, proportions, "
                  "silhouette, camera angle and every part in the same place (hull, turret, weapons, wheels, tracks or "
                  "hover skirts). Add intricate mechanical detail: layered armour plates with deep panel seams, vents and "
                  "grilles, hatches, sensor domes, weapon barrels and missile tubes, rivets, warning stencils, scratched "
                  "and weathered gunmetal grey paint. Physically based materials, crisp studio lighting, plain white background.")
BUILDING_PROMPT = ("Transform this crude low-polygon video game model into a high-end modern 3D render of the same "
                   "military outpost building, as in a 2025 AAA game. Keep the exact same shape, proportions, silhouette, "
                   "camera angle and every part in the same place (walls, roof, doors, windows, antennas). Do not add any new "
                   "structures, masts, antennas, pipes or objects beside or on top of it. Add realistic surface "
                   "detail: corrugated or riveted metal panels, concrete and weathered paint, door frames, window frames, "
                   "flush vents, rivets, rust streaks and grime. Keep the original colours. Physically based "
                   "materials, crisp studio lighting, plain white background.")
NEGATIVE = ("different pose, different silhouette, extra limbs, extra weapons, humanoid face, human, person, anime, cartoon, "
            "low poly, blurry, text, watermark, logo, background scenery, ground, floor, cropped")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1234
    name = comfy.upload(src)
    imgs = comfy.images(comfy.run(comfy.edit_graph(name, PROMPT, NEGATIVE, seed)))
    out.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].convert("RGB").save(out)
    print("saved", out, imgs[0].size)


if __name__ == "__main__":
    main()
