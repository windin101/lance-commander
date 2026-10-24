"""The v3 review package for one mech (stage `review` of tools/art/v3/v3_mech.py), written to
/mnt/nvme1n1p1/mc2-rework/review/v3-<mech>/:
  weapons_check.png, mech_bay_v1_v3.png, mech_lab_v1_v3.png, mission_112m_v1_v3.png, mission_612m_v1_v3.png (+ crops),
  schemes_default_steiner_liao_davion_woodland.png, studio_close_v1/v3.png, turntable.mp4, walk_close.mp4,
  walk_filmstrip.png, breakdown_uv.png, breakdown_model.png, uv_layout.png, pose_test.{md,json}, perf_*.json.
Godot runs go through the swarm lock, one at a time."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

import v3_common as C

GODOT = [str(Path.home() / "Code/remake-kit/bin/swarm"), "lock", "godot", "--", "flock", ".godot.lock",
         str(Path.home() / ".local/bin/godot")]


def godot(*args, timeout=600):
    r = subprocess.run(GODOT + list(args), cwd=C.ROOT, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def godot_import():
    godot("--headless", "--import", "--path", "game", timeout=1800)


def pair(a, b, out, crop=None, scale=1, labels=("v1 (installed)", "v3")):
    from PIL import Image, ImageDraw
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if crop:
        ia, ib = ia.crop(crop), ib.crop(crop)
    if scale != 1:
        ia = ia.resize((ia.width * scale, ia.height * scale), Image.NEAREST)
        ib = ib.resize((ib.width * scale, ib.height * scale), Image.NEAREST)
    s = Image.new("RGB", (ia.width * 2, ia.height + 30), (15, 15, 18))
    s.paste(ia, (0, 30)); s.paste(ib, (ia.width, 30))
    d = ImageDraw.Draw(s)
    d.text((10, 8), labels[0], fill=(255, 255, 200)); d.text((ia.width + 10, 8), labels[1], fill=(255, 255, 200))
    s.save(out)


def stage_review(cfg, work):
    import v3_stages as S
    from PIL import Image
    mech = cfg["name"]
    R = Path(f"/mnt/nvme1n1p1/mc2-rework/review/v3-{mech}"); R.mkdir(parents=True, exist_ok=True)
    G = work / "gal"; G.mkdir(exist_ok=True)
    scr = work / "screens"; scr.mkdir(exist_ok=True)
    godot_import()
    v3 = {"path": f"res://assets/v3/mechs/{mech}.glb", "paint_name": f"{mech}_v3", "folder": "mechs"}
    v1 = {"path": f"res://assets/mechs/{mech}_hd.glb", "paint_name": f"{mech}_hd", "folder": "mechs"}
    abz = [{"name": "a", "yaw": -28}, {"name": "b", "yaw": 152}, {"name": "z", "yaw": -22, "fill": 2.2, "focus": 0.72}]
    items = []
    for sc, pat in (("player", None), ("steiner", None), ("liao", None), ("davion", None), ("player", "woodland")):
        it = dict(v3, scheme=sc, out=str(G / f"sch_{sc}{'_' + pat if pat else ''}"), shots=abz)
        if pat:
            it["pattern"] = pat
        items.append(it)
    items.append(dict(v1, scheme="player", out=str(G / "v1"), shots=[abz[0], abz[2]]))
    wc = [{"name": "front", "yaw": 0, "pitch": 5}, {"name": "q34", "yaw": -45, "pitch": 20}, {"name": "side", "yaw": -90, "pitch": 5},
          {"name": "rside", "yaw": 90, "pitch": 5}, {"name": "top", "yaw": 0, "pitch": 85}]
    items.append(dict(v3, scheme="player", out=str(G / "wc"), shots=wc))
    tt = [{"name": f"t{k:03d}", "yaw": -28 + k * 10, "pitch": 10} for k in range(36)]
    walk = {"name": "w", "yaw": -35, "fill": 1.25, "focus": 0.45, "pitch": 12, "anim": "Walk", "times": [round(i / 30, 4) for i in range(40)]}
    items.append(dict(v3, scheme="player", out=str(G / "clip"), shots=tt + [walk]))
    job = G / "job_review.json"
    job.write_text(json.dumps({"size": [900, 900], "items": items}))
    godot("--path", "game", "res://scenes/art_gallery.tscn", "--", "--art-v3", f"--job={job}", timeout=1200)
    # screens: bay, lab, mission at both RTS distances, v1 and v3
    for v, flag in (("v3", "--art-v3"), ("v1", "--no-art-v3")):
        for sc in ("mech_bay", "mech_lab"):
            godot("--path", "game", f"res://scenes/{sc}.tscn", "--", flag, "--sample-campaign", f"--sample-chassis={mech}",
                  "--player-scheme=player_default", f"--screenshot={scr}/{sc}_{v}.png", "--size=1920x1080", "--frames=60")
        for dist in (112, 612):
            godot("--path", "game", "res://scenes/dev_force_mission.tscn", "--", flag, "--mission=mc2_01",
                  f"--lance={mech}:pmwhacksaw", "--player-scheme=player_default", f"--cam-view=-,35,{dist}", "--no-hud",
                  f"--screenshot={scr}/mission_{v}_{dist}.png", "--size=1920x1080", "--frames=90")
        godot("--path", "game", "res://scenes/dev_force_mission.tscn", "--", flag, "--mission=mc2_01",
              f"--lance={mech}:pmwhacksaw,{mech}:pmwlongshot,{mech}:pmwflash,{mech}:pmwjinx", "--player-scheme=player_default",
              "--size=1920x1080", "--frames=120", "--perf=15", f"--perf-out={R}/perf_mission_{v}.json")
    for sc in ("mech_bay", "mech_lab"):
        pair(scr / f"{sc}_v1.png", scr / f"{sc}_v3.png", R / f"{sc}_v1_v3.png")
    pair(scr / "mission_v1_112.png", scr / "mission_v3_112.png", R / "mission_112m_v1_v3.png")
    pair(scr / "mission_v1_612.png", scr / "mission_v3_612.png", R / "mission_612m_v1_v3.png")
    pair(scr / "mission_v1_112.png", scr / "mission_v3_112.png", R / "mission_112m_crop.png", crop=(660, 180, 1260, 680))
    pair(scr / "mission_v1_612.png", scr / "mission_v3_612.png", R / "mission_612m_crop_x2.png", crop=(860, 380, 1060, 580), scale=2)
    # schemes sheet
    rows = []
    for n in ("sch_player", "sch_steiner", "sch_liao", "sch_davion", "sch_player_woodland"):
        r = Image.new("RGB", (1500, 500))
        for i, v in enumerate("abz"):
            r.paste(Image.open(G / f"{n}_{v}.png").convert("RGB").resize((500, 500)), (i * 500, 0))
        rows.append(r)
    s = Image.new("RGB", (1500, 2500))
    for i, r in enumerate(rows):
        s.paste(r, (0, i * 500))
    s.save(R / "schemes_default_steiner_liao_davion_woodland.png")
    shutil.copy(G / "sch_player_z.png", R / "studio_close_v3.png")
    shutil.copy(G / "v1_z.png", R / "studio_close_v1.png")
    # clips and filmstrip
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", str(G / "clip_t%03d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "18", str(R / "turntable.mp4")])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-stream_loop", "2", "-i", str(G / "clip_w_%03d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(R / "walk_close.mp4")])
    fs = [G / f"clip_w_{i:03d}.png" for i in range(0, 40, 5)]
    st = Image.new("RGB", (400 * len(fs), 400))
    for i, f in enumerate(fs):
        st.paste(Image.open(f).convert("RGB").resize((400, 400)), (i * 400, 0))
    st.save(R / "walk_filmstrip.png")
    # weapons check with the textured row
    S.weapons_check(cfg, work, out=R / "weapons_check.png", textured=[G / f"wc_{v}.png" for v in ("front", "q34", "side", "rside", "top")])
    S.canopy_check(cfg, work, R / "canopy_check.png")
    import v3_paint as VP
    VP.make_sheets(work, R / "outline_sheets")   # plain aligned sheets (front, 3/4, sides, top) for blue outlines
    breakdown(cfg, work, R)
    for f in ("pose_test.md", "pose_test.json"):
        if (work / f).exists():
            shutil.copy(work / f, R / f)
    print("review:", R)


def breakdown(cfg, work, R):
    from PIL import Image, ImageDraw
    L = np.load(work / "tex/layers.npz"); ii = L["ii"]; res = int(L["res"])
    def img_of(v):
        a = np.zeros((res * res, 3), np.float32)
        a[ii] = v if v.ndim == 2 else np.repeat(v[:, None], 3, 1)
        return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8).reshape(res, res, 3))
    zone_pal = np.array([[0.62, 0.62, 0.6], [0.85, 0.2, 0.1], [0.2, 0.22, 0.25], [0.2, 0.6, 0.9], [1, 0.8, 0.2]])
    reg_pal = np.array([[0.6, 0.6, 0.6], [0.9, 0.8, 0.3], [0.3, 0.5, 0.9], [0.3, 0.8, 0.4], [0.2, 0.6, 0.5], [0.7, 0.4, 0.2], [1.0, 0.0, 0.85], [0.8, 0.4, 0.8]])
    z = np.round(L["zone"].astype(np.float32) * 4).astype(int); r = np.round(L["region"].astype(np.float32) * 7).astype(int)
    zc = zone_pal[z].copy(); zc[(L["piping"] > 0.5) & (z == 0)] = zone_pal[1]
    rc = reg_pal[r]; rc[z >= 2] = zone_pal[z[z >= 2]]
    trim = np.stack([L["piping"], L["stripe"], L["band"]], 1).astype(np.float32)
    bk = work / "bake"
    tiles = [("normal (bevelled sculpt)", Image.open(bk / "normal.png").convert("RGB")), ("AO (1.2 m)", Image.open(bk / "ao.png").convert("RGB")),
             ("AO short (0.15 m)", Image.open(bk / "ao_short.png").convert("RGB")),
             ("edges", img_of(np.clip(np.load(bk / "edge_wide.npy").astype(np.float32).ravel()[ii] * 3, 0, 1))),
             ("zones: paint/trim/metal/glass/lens", img_of(zc)), ("regions (weapons magenta)", img_of(rc)), ("piping R / stripe G / band B", img_of(trim)),
             ("chips", img_of(L["chips"].astype(np.float32))), ("grime", img_of(L["grime"].astype(np.float32))), ("dust", img_of(L["dust"].astype(np.float32))),
             ("albedo RGB (unpainted)", Image.open(work / "tex/albedo.png").convert("RGB")), ("ORM", Image.open(work / "tex/orm.png").convert("RGB"))]
    T = 512
    sh = Image.new("RGB", (T * 4, (T + 28) * 3), (20, 20, 22)); d = ImageDraw.Draw(sh)
    for k, (n, im) in enumerate(tiles):
        x, y = (k % 4) * T, (k // 4) * (T + 28)
        sh.paste(im.resize((T, T), Image.BILINEAR), (x, y + 28)); d.text((x + 6, y + 8), n, fill=(255, 255, 200))
    sh.save(R / "breakdown_uv.png")
    low = work / "low.npz"
    shows = [("bakes", None), ("zones", img_of(zc)), ("regions", img_of(rc)),
             ("chips", img_of(np.c_[L["chips"], L["grime"] * 0.8, L["dust"]].astype(np.float32)))]
    for name, im in shows:
        Ld = work / f"ld_{name}"; Ld.mkdir(exist_ok=True)
        if im is None:
            shutil.copy(bk / "normal.png", Ld / "normal.png"); Image.open(bk / "ao.png").convert("RGB").save(Ld / "albedo.png")
        else:
            im.save(Ld / "albedo.png")
        C.blender("lookdev", low, work / f"bd_{name}", "--maps", Ld, "--shading", work / "bake/low_shading.npz",
                  "--views", "q34,q34b", "--size", "700", "--samples", "16")
    labels = ["AO + normal bake", "zones: grey paint, red trim, dark metal, blue glass, yellow lens", "scheme regions (weapons magenta)",
              "chips R, grime G, dust B"]
    sh = Image.new("RGB", (1400 * 2, 728 * 2), (20, 20, 22)); d = ImageDraw.Draw(sh)
    for k, (n, _) in enumerate(shows):
        x, y = (k % 2) * 1400, (k // 2) * 728
        for j, v in enumerate(("q34", "q34b")):
            sh.paste(Image.open(work / f"bd_{n}_{v}.png").convert("RGB"), (x + j * 700, y + 28))
        d.text((x + 8, y + 8), labels[k], fill=(255, 255, 200))
    sh.save(R / "breakdown_model.png")
    uv = np.load(low)["uv"].reshape(-1, 3, 2); kk = np.load(low)["kind"]
    im = Image.new("RGB", (2048, 2048)); dr = ImageDraw.Draw(im)
    cols = [(200, 200, 200), (255, 0, 200), (80, 160, 255)]
    for t, k_ in zip(uv, kk):
        dr.polygon([(x * 2048, (1 - y) * 2048) for x, y in t], fill=tuple(c // 3 for c in cols[k_]), outline=cols[k_])
    im.resize((1024, 1024)).save(R / "uv_layout.png")
