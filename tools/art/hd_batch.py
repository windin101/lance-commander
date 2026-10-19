"""Run hd_mech.py steps over many mechs, restarting the local ComfyUI when it goes bad.

    COMFY_SERVER=http://127.0.0.1:8188 python3 -I tools/art/hd_batch.py --steps 2-2 hunchback zeus ...
    ... --steps 3-5            (mesh, rig, install)
    ... --args zeus=--seed=8 --args atlas=--turn       (per-mech extra hd_mech.py flags)

On this ROCm build the Qwen edit server sometimes starts returning all-black images (NaN) after a few
good edits, and stays that way until restarted. hd_mech.py stops with "all-black image" when that
happens; this driver then restarts ComfyUI (the instance on $COMFY_SERVER's port that it can see in
original/hd/logs/comfy.pid, GPU0) and retries the mech once. It never touches other ComfyUI instances.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "original" / "hd" / "logs"
COMFY_DIR = Path("/mnt/nvme1n1p1/StabilityMatrix/linux-x64/Data/Packages/ComfyUI")
SERVER = os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188")


def up():
    try:
        urllib.request.urlopen(SERVER + "/system_stats", timeout=3)
        return True
    except OSError:
        return False


def restart_comfy():
    pidfile = LOGS / "comfy.pid"
    port = SERVER.rsplit(":", 1)[1]
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(60):
        if not up():
            break
        time.sleep(2)
    log = open(LOGS / f"comfy{port}_{int(time.time())}.log", "w")
    p = subprocess.Popen(["./venv/bin/python3", "-u", "main.py", "--cuda-device", "0", "--listen", "127.0.0.1",
                          "--port", port, "--preview-method", "none", "--use-split-cross-attention"],
                         cwd=COMFY_DIR, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    pidfile.write_text(str(p.pid))
    for _ in range(120):
        time.sleep(5)
        if up():
            print(f"  ComfyUI restarted (pid {p.pid})", flush=True)
            return
    raise RuntimeError("ComfyUI did not come back")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mechs", nargs="+")
    ap.add_argument("--steps", default="2-5")
    ap.add_argument("--args", action="append", default=[], help="mech=--flag[=value] (repeatable)")
    a = ap.parse_args()
    lo, hi = a.steps.split("-")
    extra = {}
    for kv in a.args:
        m, flag = kv.split("=", 1)
        extra.setdefault(m, []).extend(flag.split("=", 1) if flag.startswith("--") and "=" in flag else [flag])
    for m in a.mechs:
        for attempt in (1, 2):
            cmd = [sys.executable, "-I", str(Path(__file__).with_name("hd_mech.py")), m, "--from-step", lo,
                   "--to-step", hi] + extra.get(m, [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            sys.stdout.write(r.stdout)
            if r.returncode == 0:
                break
            tail = r.stderr.strip().splitlines()[-1:] if r.stderr.strip() else ["?"]
            print(f"FAIL {m} (attempt {attempt}): {tail[0]}", flush=True)
            if "all-black image" in r.stderr and attempt == 1:
                restart_comfy()
                continue
            break
        sys.stdout.flush()
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()
