"""Approve (or reject) a template after visual QA.

    python scripts/approve_template.py saree_f_01
    python scripts/approve_template.py saree_f_01 --reject
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ap = argparse.ArgumentParser()
ap.add_argument("template_code")
ap.add_argument("--reject", action="store_true", help="mark needs-correction + inactive")
args = ap.parse_args()

from app.db import queries

if args.reject:
    ok = queries.set_template_qa(args.template_code, "needs-correction", False)
    print(("rejected: " if ok else "NOT FOUND: ") + args.template_code)
else:
    ok = queries.set_template_qa(args.template_code, "approved", True)
    print(("approved + active: " if ok else "NOT FOUND: ") + args.template_code)
sys.exit(0 if ok else 1)
