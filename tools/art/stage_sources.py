#!/usr/bin/env python3
"""Gather every adapted sculpt's original download into /mnt/nvme1n1p1/mc2-sources/<kind>/<name>/.

    python3 -I tools/art/stage_sources.py [--dest /mnt/nvme1n1p1/mc2-sources] [--download]

Reads the source URLs from game/assets/{mechs,vehicles,objects}/*_hd.LICENSE.md. For each it looks for the
download in the working folders under ~/craft/solid/mc2 (stl/<mech>, tv_stl/<thing id>, veh_stl/<printables
id>, air_stl/<name>), copies the files (zips, STLs, SOURCE.txt, source.json; not render sheets), and writes
a SOURCE.txt with title, URL and licence. Anything not found locally is listed; with --download, Printables
models are fetched through the GraphQL API (needs a browser User-Agent) and Thingiverse things are listed
for ~/craft/solid/mc2/tv_stl/tvdl.mjs (headless Chrome over CDP). Treat the copies as untrusted data.
"""
import argparse
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path.home() / "craft" / "solid" / "mc2"
KEEP = (".stl", ".zip", ".txt", ".json", ".3mf", ".obj", ".md")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def sources():
    for folder, kind in (("mechs", "mech"), ("vehicles", "vehicle"), ("objects", "object")):
        for lic in sorted((ROOT / "game" / "assets" / folder).glob("*_hd.LICENSE.md")):
            name = lic.name[: -len("_hd.LICENSE.md")]
            t = lic.read_text()
            urls = []
            for u in re.findall(r"https://www\.(?:thingiverse|printables)\.com/[^\s,)*]+", t):
                u = u.rstrip(".")
                if u not in urls:
                    urls.append(u)
            lics = re.findall(r"\((CC [A-Z\-]+ \d\.\d)\)", t)
            titles = re.findall(r"\*\*\"?(.+?)\"?\*\* by \*\*(.+?)\*\*", t)
            yield kind, name, urls, lics[0] if lics else "?", titles


def local_dirs(kind, name, url):
    out = []
    m = re.search(r"thing:(\d+)", url)
    if m:
        out += [WORK / "tv_stl" / m.group(1)] + sorted((WORK / "air_stl").glob("*/" + m.group(1)))
    m = re.search(r"printables\.com/model/(\d+)", url)
    if m:
        out += [WORK / "veh_stl" / m.group(1)]
    out += [WORK / "stl" / name, WORK / "air_stl" / name, WORK / "veh_stl" / name]
    if name == "vulture":
        out.append(WORK / "vulture_stl")
    if name == "infantry":
        out.append(WORK / "veh_stl" / "infantry_gm")
    return [d for d in out if d.is_dir()]


def copy_tree(src, dst):
    n = 0
    for p in src.rglob("*"):
        if p.is_file() and p.suffix.lower() in KEEP and p.stat().st_size < 2_000_000_000:
            rel = p.relative_to(src)
            q = dst / src.name / rel
            if not q.exists() or q.stat().st_size != p.stat().st_size:
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, q)
            n += 1
    return n


def printables_download(pid, dst):
    def gql(q):
        req = urllib.request.Request("https://api.printables.com/graphql/", data=json.dumps({"query": q}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": UA})
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    info = gql('query{print(id:"%s"){license{abbreviation} stls{id name}}}' % pid)
    dst.mkdir(parents=True, exist_ok=True)
    for s in info["data"]["print"]["stls"]:
        r = gql('mutation{getDownloadLink(id:"%s", printId:"%s", fileType:stl, source:model_detail){ok output{link}}}' % (s["id"], pid))
        link = r["data"]["getDownloadLink"]["output"]["link"]
        req = urllib.request.Request(link, headers={"User-Agent": UA})
        (dst / Path(s["name"]).name).write_bytes(urllib.request.urlopen(req, timeout=300).read())
    return info["data"]["print"]["license"]["abbreviation"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="/mnt/nvme1n1p1/mc2-sources")
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    dest = Path(a.dest)
    missing = []
    index = []
    for kind, name, urls, lic, titles in sources():
        d = dest / kind / name
        d.mkdir(parents=True, exist_ok=True)
        files = 0
        for u in urls:
            for src in local_dirs(kind, name, u):
                files += copy_tree(src, d)
        if files == 0 and a.download:
            for u in urls:
                m = re.search(r"printables\.com/model/(\d+)", u)
                if m:
                    printables_download(m.group(1), d / m.group(1))
                    files += 1
        title = "; ".join(f"\"{t}\" by {au}" for t, au in titles)
        (d / "SOURCE.txt").write_text(f"{title}\n" + "\n".join(urls) + f"\nLicence: {lic}\n"
                                      f"Staged by tools/art/stage_sources.py for the Lance Commander HD rework.\n")
        index.append({"kind": kind, "name": name, "urls": urls, "licence": lic, "files": files})
        if files == 0:
            missing.append((kind, name, urls))
    (dest / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} assets staged under {dest}; {len(missing)} without a local copy")
    for k, n, u in missing:
        print("  MISSING", k, n, " ".join(u))


if __name__ == "__main__":
    sys.exit(main())
