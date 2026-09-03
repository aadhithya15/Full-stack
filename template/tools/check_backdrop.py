"""Acceptance gate for the backdrop -- written down so no frame is ever certified by eye again.

Uses the SAME background definition as flatten_backdrop.py (bgmask.background), applied to the file as
it sits on disk. A mean or std over one mixed mask is not a valid test: two greys average into a
plausible number and a corner patch misses an interior panel entirely. A per-pixel std is also not
valid: a quality-95 JPEG of a perfectly flat 128 field already carries +-0.5 of noise.

Test per file, over 96px blocks of background:
    max(block mean) - min(block mean) <= 2.0
    |mean of block means - 128|        <= 1.5
    std of 16px cell means             <= 0.30
Usage (from repo root): python3 template/tools/check_backdrop.py [garment-filter ...]   exit 1 if any fail
"""
from PIL import Image
import numpy as np
from scipy import ndimage
import os, sys, glob
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from bgmask import background

TONE=['fair','light-warm','light-tan','medium-brown','deep','ebony']
ONLY=[a for a in sys.argv[1:] if not a.startswith('-')]
BLK,CELL=96,16
files=[p for p in sorted(glob.glob('template/base/*.jpg')) for t in ['.']+TONE]
files=sorted(set([f'template/{t}/{os.path.basename(p)}' for p in sorted(glob.glob('template/base/*.jpg')) for t in ['.']+TONE]))
if ONLY: files=[f for f in files if any(o in os.path.basename(f) for o in ONLY)]
rows=[]; miss=0
for p in files:
    if not os.path.exists(p): miss+=1; continue
    X=np.asarray(Image.open(p).convert('RGB'),dtype=float); L=X.mean(2); H,W=L.shape
    bg,_=background(X)
    bg=ndimage.binary_erosion(bg,np.ones((3,3)),iterations=2)   # measure ~3px clear of the silhouette: 1-2px of JPEG
                                                   # ringing at the model's edge is not a panel, and a gate
                                                   # that chases it forces repaint passes that eat the subject
    if bg.sum()<5000: rows.append((p,99.,99.,99.,0,0.,0.)); continue
    v=[]
    for y in range(0,H,BLK):
        for x in range(0,W,BLK):
            m=bg[y:y+BLK,x:x+BLK]
            if m.sum()>200: v.append(float(L[y:y+BLK,x:x+BLK][m].mean()))
    cv=[]
    for y in range(0,H,CELL):
        for x in range(0,W,CELL):
            m=bg[y:y+CELL,x:x+CELL]
            if m.sum()>=CELL*CELL*0.6: cv.append(float(L[y:y+CELL,x:x+CELL][m].mean()))
    v=np.array(v); cv=np.array(cv)
    sp=float(v.max()-v.min()); off=abs(float(v.mean())-128.0); sd=float(cv.std()) if len(cv)>10 else 9.9
    rows.append((p,sp,off,sd,len(v),float(v.min()),float(v.max())))
bad=[r for r in rows if not (r[1]<=2.0 and r[2]<=1.5 and r[3]<=0.30)]
print(f"{len(rows)} files checked: {len(rows)-len(bad)} PASS, {len(bad)} FAIL" + (f"; {miss} tone slots not yet generated" if miss else ""))
if bad:
    print("\nFAILING  (spread of 96px block means | offset from 128 | std of 16px cell means | block min-max):")
    for p,sp,off,sd,n,lo,hi in sorted(bad,key=lambda r:-r[1])[:40]:
        print(f"  {p:46s} {sp:6.2f} {off:6.2f} {sd:6.3f}  n={n:3d}  {lo:6.1f}-{hi:6.1f}")
sys.exit(1 if bad else 0)
