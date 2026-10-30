#!/usr/bin/env python3
"""Tripo multiview-to-model: upload views, create the task, poll, download the GLB.   (LANCE-16 trial, drafted 2026-10-30)

    python3 -I tools/art/v3/tripo_gen.py NAME --views DIR [--out DIR] [--dry-run] [options]

DIR holds front.png and at least one of left.png, back.png, right.png (PNG or JPEG, >= 256 px, <= 20 MB each). Only
OUR OWN art may be uploaded (renders of our model, edits of those): never third-party screenshots or art.

--dry-run validates the inputs and prints the exact request bodies with placeholders. It makes NO network call and
does not open the key file.  A live run reads the key from ~/.config/tripo/api_key (or $TRIPO_API_KEY_FILE) only
inside this script; the key is held in one variable, sent only in the Authorization header, and never printed,
logged or written to task.json.

API (read from developers.tripo3d.com on 2026-10-30; v3 host https://openapi.tripo3d.ai/v3 (global; .com is the China host), Bearer auth):
  POST /files                         multipart field "file" (image <= 20 MB: PNG/JPEG)  -> data.file_token
  POST /generation/multiview-to-model {"inputs": {"front": {"file_token": ..}, "left": .., "back": .., "right": ..},
                                       "model": "v3.1-20260211", "texture": false, "pbr": false, "face_limit": N,
                                       "geometry_quality": "detailed", "model_seed": N, ...}   -> data.task_id
  GET  /tasks/{task_id}               data.status queued|running|success|failed|banned|expired|cancelled, data.progress,
                                       data.output.model_url (only on success), data.credits_consumed
  429: code 1007 rate limit, 2000 concurrency full; honour Retry-After, else back off 1..32 s.
Download URLs have no documented lifetime: the GLB is fetched immediately after success.
"""
import argparse
import json
import mimetypes
import os
import struct
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://openapi.tripo3d.ai/v3"   # global host (the SDK: .ai global, .com China)
UA = "curl/8.5.0"   # Cloudflare answers 403/1010 to the default Python-urllib agent
KEY_FILE = Path(os.environ.get("TRIPO_API_KEY_FILE", "~/.config/tripo/api_key")).expanduser()
VIEWS = ("front", "left", "back", "right")
MODELS = ("v3.1-20260211", "v3.0-20250812", "v2.5-20250123")
MAX_BYTES = 20 * 1024 * 1024
TERMINAL = {"success", "failed", "banned", "expired", "cancelled"}


def image_size(p: Path):
    b = p.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24]), "png"
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1; continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9]); return (w, h), "jpeg"
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None, None


def validate(views_dir: Path, a):
    problems, found = [], {}
    for v in VIEWS:
        for ext in ("png", "jpg", "jpeg"):
            p = views_dir / f"{v}.{ext}"
            if p.exists():
                found[v] = p; break
    if "front" not in found:
        problems.append("front view is mandatory")
    if len(found) < 2:
        problems.append("at least two views are required")
    for v, p in found.items():
        sz = p.stat().st_size
        wh, kind = image_size(p)
        if kind is None:
            problems.append(f"{p.name}: not a PNG/JPEG")
        elif min(wh) < 256:
            problems.append(f"{p.name}: {wh[0]}x{wh[1]} is below the 256 px minimum")
        if sz > MAX_BYTES:
            problems.append(f"{p.name}: {sz / 1e6:.1f} MB is over the 20 MB limit")
    if a.model not in MODELS:
        problems.append(f"model must be one of {MODELS}")
    if a.pbr and not a.texture:
        problems.append("pbr forces texture on: pass --texture too, or drop --pbr")
    if a.geometry_quality == "detailed" and a.model.startswith("v2.5"):
        problems.append("geometry_quality is not available for v2.5")
    return found, problems


def body(a, tokens):
    # the server rejected the nested {"front": {"file_token": ..}} form (code 1004); the positional list of file_tokens
    # [front, left, back, right] ("" skips a view) is what the SDK sends
    b = {"inputs": [tokens.get(v, "") for v in VIEWS], "model": a.model, "texture": bool(a.texture),
         "pbr": bool(a.pbr), "geometry_quality": a.geometry_quality, "export_orientation": "+x"}
    if a.face_limit:
        b["face_limit"] = a.face_limit
    if a.model_seed is not None:
        b["model_seed"] = a.model_seed
    return b


class Api:
    def __init__(self, key):
        self._key = key

    def _req(self, req, tries=6):
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("User-Agent", UA)
        wait = 1.0
        for _ in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf8", "replace")[:500]
                if e.code == 429:
                    time.sleep(float(e.headers.get("Retry-After") or wait)); wait = min(wait * 2, 32); continue
                raise SystemExit(f"HTTP {e.code} from {req.full_url}: {txt}")
        raise SystemExit("rate limited: gave up")

    def upload(self, path: Path):
        bnd = uuid.uuid4().hex
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{bnd}--\r\n".encode()
        r = urllib.request.Request(f"{BASE}/files", data=data, method="POST",
                                   headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
        j = self._req(r)
        if j.get("code") != 0:
            raise SystemExit(f"upload {path.name}: code {j.get('code')}")
        return j["data"]["file_token"]

    def create(self, b):
        r = urllib.request.Request(f"{BASE}/generation/multiview-to-model", data=json.dumps(b).encode(), method="POST",
                                   headers={"Content-Type": "application/json"})
        j = self._req(r)
        if j.get("code") != 0:
            raise SystemExit(f"create task: code {j.get('code')} {j.get('message', '')}")
        return j["data"]["task_id"]

    def balance(self):
        d = self._req(urllib.request.Request(f"{BASE}/account/balance"))["data"]
        return float(d["balance"]), float(d.get("frozen", 0))

    def task(self, tid):
        return self._req(urllib.request.Request(f"{BASE}/tasks/{tid}"))["data"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name")
    ap.add_argument("--views", required=True)
    ap.add_argument("--out", default=None, help="default /mnt/nvme1n1p1/mc2-rework/tripo_poc/<name>/out")
    ap.add_argument("--model", default="v3.1-20260211")
    ap.add_argument("--texture", action="store_true", help="geometry only by default: Pipeline A bakes its own textures")
    ap.add_argument("--pbr", action="store_true")
    ap.add_argument("--geometry-quality", default="detailed", choices=("standard", "detailed"))
    ap.add_argument("--face-limit", type=int, default=400000)
    ap.add_argument("--model-seed", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=900, help="max polling seconds")
    ap.add_argument("--tag", default="run", help="label for this task in the ledger (e.g. multiview, front-only)")
    ap.add_argument("--max-tasks", type=int, default=3, help="refuse to start when the ledger already has this many tasks")
    ap.add_argument("--max-credits", type=float, default=400, help="refuse to start when the ledger already spent this much")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="balance check on each API host (spends no credits); prints status and balance only")
    a = ap.parse_args()
    if a.check:
        key = KEY_FILE.read_text().strip()
        for label, url in (("v3 " + BASE, f"{BASE}/account/balance"), ("v2 https://api.tripo3d.ai/v2/openapi", "https://api.tripo3d.ai/v2/openapi/user/balance")):
            r = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": UA})
            try:
                with urllib.request.urlopen(r, timeout=30) as resp:
                    j = json.loads(resp.read()); print(label, "->", resp.status, {"code": j.get("code"), "data": j.get("data")})
            except urllib.error.HTTPError as e:
                print(label, "-> HTTP", e.code, e.read().decode("utf8", "replace")[:200])
            except Exception as e:
                print(label, "-> error", type(e).__name__)
        return 0
    out = Path(a.out or f"/mnt/nvme1n1p1/mc2-rework/tripo_poc/{a.name}/out"); out.mkdir(parents=True, exist_ok=True)
    found, problems = validate(Path(a.views), a)
    for p in problems:
        print("PROBLEM:", p)
    print("views:", {v: str(p) for v, p in found.items()})
    if a.dry_run or problems:
        print("request body (placeholders):", json.dumps(body(a, {v: f"<file_token:{v}>" for v in found}), indent=1))
        print("DRY RUN OK, no network call made" if not problems else "fix the problems above")
        return 1 if problems else 0
    ledger_p = out / "ledger.json"
    ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {"tasks": []}
    spent = sum(t.get("credits_spent") or 0 for t in ledger["tasks"])
    if len(ledger["tasks"]) >= a.max_tasks or spent >= a.max_credits:
        raise SystemExit(f"budget reached: {len(ledger['tasks'])} tasks, {spent} credits spent (limits {a.max_tasks} / {a.max_credits})")
    key = KEY_FILE.read_text().strip()     # the only place the key is read
    api = Api(key)
    bal0, frozen0 = api.balance()
    print(f"balance before: {bal0} (frozen {frozen0})")
    tokens = {v: api.upload(p) for v, p in found.items()}
    print("uploaded", len(tokens), "views")
    tid = api.create(body(a, tokens))
    rec = {"tag": a.tag, "task_id": tid, "name": a.name, "model": a.model, "params": body(a, {v: "<file_token>" for v in found}),
           "views": {v: str(p) for v, p in found.items()}, "balance_before": bal0, "credits_spent": None, "status": "created"}
    ledger["tasks"].append(rec); ledger_p.write_text(json.dumps(ledger, indent=1))
    print("task", tid)
    t0, last = time.time(), -1
    while True:
        d = api.task(tid)
        if d.get("progress") != last:
            last = d.get("progress"); print(f"  {d['status']} {last}%", flush=True)
        if d["status"] in TERMINAL:
            break
        if time.time() - t0 > a.timeout:
            raise SystemExit(f"timed out after {a.timeout} s; task {tid} may still finish: re-query it later")
        time.sleep(3)
    (out / f"result_{tid}.json").write_text(json.dumps(d, indent=1))
    bal1, _ = api.balance()
    rec.update(status=d["status"], credits_consumed=d.get("credits_consumed"), balance_after=bal1, credits_spent=round(bal0 - bal1, 2))
    ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"balance after: {bal1} (spent {rec['credits_spent']}, reported {d.get('credits_consumed')})")
    if d["status"] != "success":
        raise SystemExit(f"task ended {d['status']}: {d.get('error_code')} {d.get('error_message')}")
    url = d["output"]["model_url"]
    dst = out / f"{a.name}_{a.tag}_{tid}.glb"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=300) as r, open(dst, "wb") as f:   # no auth header on the CDN
        f.write(r.read())
    rec["glb"] = str(dst); ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"saved {dst} ({dst.stat().st_size / 1e6:.1f} MB), credits {d.get('credits_consumed')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
