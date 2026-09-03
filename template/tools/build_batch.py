"""One command per batch: raw generation -> locked catalogue frames + all six tone files, QC'd.

Order is not negotiable:
  1. normalize   centre-crop + single LANCZOS downscale to 768x1376 (pixel lock for the shared masks)
  2. flatten     paint the backdrop to exactly #808080 ONCE (re-running shaves the garment edge)
  3. re-tone base  drive the base master's own skin onto the light-tan anchor (the generator renders
                   skin at S 61-83, which reads as a fake tan; every tone file is the same transform,
                   so garment and backdrop stay byte-comparable between the six)
  4. tone files  the other five complexions, same pixels, only L/S of skin moves
  5. audit       backdrop uniformity, garment separation, sharpness, skin saturation, and a pose-lock
                 check of every tone file against its base master (a drifted frame breaks the mask)

Usage:  python3 template/tools/build_batch.py template/_qc/raw --out template
Exit 1 if any frame fails a gate; failing frames are reported, not silently shipped.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TONES = json.load(open(os.path.join(HERE, "tone-ladder.json")))["tones"]
BASE_TONE = "light-tan"


def run(cmd, env=None, quiet_fail=False):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=ROOT, env=e, capture_output=True, text=True)
    if r.returncode != 0 and not quiet_fail:
        print("FAILED:", " ".join(cmd))
        print((r.stdout + r.stderr).strip()[-3000:])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="folder of freshly generated 9:16 frames named <ID>-<desc>.jpg")
    ap.add_argument("--out", default="template")
    ap.add_argument("--work", default="template/_qc/work")
    a = ap.parse_args()
    src = os.path.join(ROOT, a.raw) if not os.path.isabs(a.raw) else a.raw
    out = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    work = os.path.join(ROOT, a.work) if not os.path.isabs(a.work) else a.work
    files = sorted(glob.glob(os.path.join(src, "*.jpg")) + glob.glob(os.path.join(src, "*.png")))
    if not files:
        print(f"no frames in {src}")
        return 2
    norm = os.path.join(work, "norm")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(norm, exist_ok=True)
    print(f"[1/5] normalize {len(files)} frames -> 768x1376")
    run([sys.executable, "template/tools/normalize.py", src, norm])
    print("[2/5] flatten backdrop to exact 128 (one pass, in place on the normalised frames)")
    run([sys.executable, "template/tools/flatten_backdrop.py"], {"TPL_BASE": norm, "TPL_ROOT": norm})
    bt = TONES[BASE_TONE]
    os.makedirs(os.path.join(out, "base"), exist_ok=True)
    print(f"[3/5] re-tone base masters onto '{BASE_TONE}' anchor (L{bt['skinL']:.0f} S{bt['skinS']:.0f})")
    for f in sorted(glob.glob(os.path.join(norm, "*.jpg"))):
        dst = os.path.join(out, "base", os.path.basename(f))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = run([sys.executable, "template/tools/tone.py", f, dst, "--L", str(bt["skinL"]),
                 "--S", str(bt["skinS"]), "--report"])
        if r.returncode:
            print(f"  !! base skin transform failed: {os.path.basename(f)}")
    print("[4/5] build the five sibling tone files per outfit (base IS the light-tan file)")
    for f in sorted(glob.glob(os.path.join(out, "base", "*.jpg"))):
        for t, v in TONES.items():
            if t == BASE_TONE:
                os.makedirs(os.path.join(out, t), exist_ok=True)
                shutil.copyfile(f, os.path.join(out, t, os.path.basename(f)))
                continue
            d = os.path.join(out, t, os.path.basename(f))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            run([sys.executable, "template/tools/tone.py", f, d, "--L", str(v["skinL"]),
                 "--S", str(v["skinS"])])
    print("[5/5] audit")
    rc = 0
    r = run([sys.executable, "template/tools/audit.py", os.path.join(out, "base"), "--iou"], quiet_fail=True)
    print(r.stdout.strip()[-2200:])
    rc |= r.returncode
    for t in TONES:
        d = os.path.join(out, t)
        if not glob.glob(os.path.join(d, "*.jpg")):
            continue
        r = run([sys.executable, "template/tools/audit.py", d, "--base", os.path.join(out, "base")],
                quiet_fail=True)
        tail = [l for l in r.stdout.splitlines() if "locked" in l or "NOT USABLE" in l or "FAIL" in l]
        print(f"  {t:14s} " + ("; ".join(tail[-3:]) if tail else "clean"))
        rc |= r.returncode
    print("\nRESULT:", "gates pass" if rc == 0 else "GATE FAILURES - see above, do not ship")
    return rc


if __name__ == "__main__":
    sys.exit(main())
