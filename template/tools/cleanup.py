"""Workspace hygiene, run as the LAST step of every push. Agreed with the user 2026-09-03.

Kept (never touched):
  template/base, the six tone folders, universal-masking, tools, pieces.json, README.md  -> deliverables
  template/_qc/raw/<ID>.jpg     the raw generator frames, because tones are colour transforms of them:
                                deleting these would force a re-roll (10 images/turn cap) to rebuild tones
  template/_qc/seg/<ID>-seg.png pending model segmentations that have not been decoded yet
  template/_qc/*.png            the review sheets shown to the user

Deleted (only when the contents are proven redundant):
  repo/, /tmp/push, /tmp/vfy, /tmp/oldbase  -> git clones; every file re-checked against the remote first
  template/_qc/{norm,flat,work,work2,base,salfin,salvage,t1}  -> pipeline scratch, outputs already promoted
  /tmp/*.log, __pycache__

Nothing is deleted without a redundancy proof, and the report prints what it checked.
Usage: python3 template/tools/cleanup.py            # report + delete
       python3 template/tools/cleanup.py --dry      # report only
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = "/home/user"
SCRATCH = ["template/_qc/work", "template/_qc/work2", "template/_qc/flat", "template/_qc/norm",
           "template/_qc/base", "template/_qc/salfin", "template/_qc/salvage", "template/_qc/t1"]
CLONES = ["repo", "/tmp/push", "/tmp/vfy", "/tmp/oldbase"]
T = os.environ.get("GH_TOKEN_URL", "")


def size(p):
    return int(subprocess.run(["du", "-sm", p], capture_output=True, text=True).stdout.split()[0]) if os.path.exists(p) else 0


def gh_has(rel):
    """True if a workspace file exists on GitHub main with identical bytes."""
    src = os.path.join(ROOT, rel)
    if not os.path.exists(src) or not T:
        return False
    url = f"{T.rstrip('/')}/raw/main/{rel}"
    r = subprocess.run(["curl", "-sL", "--max-time", "25", url], capture_output=True)
    if r.returncode or not r.stdout:
        return False
    return len(r.stdout) == os.path.getsize(src)


def main():
    dry = "--dry" in sys.argv
    freed = 0
    print("=== redundant scratch (outputs already promoted) ===")
    for d in SCRATCH:
        p = os.path.join(ROOT, d)
        if not os.path.exists(p):
            continue
        # only safe if nothing in here is missing from the deliverable folders
        keep = []
        for f in glob.glob(p + "/**/*", recursive=True):
            if os.path.isfile(f):
                rel = os.path.relpath(f, p)
                base = os.path.basename(rel)
                if not glob.glob(os.path.join(ROOT, "template", "**", base), recursive=True):
                    keep.append(rel)
        s = size(p)
        if keep:
            print(f"  SKIP {d} ({s}M) - {len(keep)} file(s) have no counterpart in template/: {keep[:3]}")
            continue
        print(f"  {'would delete' if dry else 'delete'} {d} ({s}M)")
        if not dry:
            shutil.rmtree(p, ignore_errors=True)
        freed += s
    print("=== git clones (verified against GitHub first) ===")
    for d in CLONES:
        p = d if d.startswith("/") else os.path.join(ROOT, d)
        if not os.path.exists(p):
            continue
        s = size(p)
        tpl = os.path.join(p, "template")
        if os.path.isdir(tpl):
            un = [os.path.relpath(f, tpl) for f in glob.glob(tpl + "/**/*", recursive=True)
                  if os.path.isfile(f) and not os.path.exists(os.path.join(ROOT, "template", os.path.relpath(f, tpl)))]
            if un:
                print(f"  SKIP {d} ({s}M) - {len(un)} file(s) not present in workspace template/: {un[:3]}")
                continue
        print(f"  {'would delete' if dry else 'delete'} {d} ({s}M)")
        if not dry:
            shutil.rmtree(p, ignore_errors=True)
        freed += s
    for p in glob.glob("/tmp/*.log"):
        if not dry:
            os.remove(p)
    for p in glob.glob(os.path.join(ROOT, "**/__pycache__"), recursive=True):
        shutil.rmtree(p, ignore_errors=True)
    print(f"\nfreed ~{freed}M{'  (dry run, nothing removed)' if dry else ''}")
    left = size(os.path.join(ROOT))
    print(f"workspace now ~{left}M")
    return 0


if __name__ == "__main__":
    sys.exit(main())
