"""Force every backdrop to a mathematically uniform #808080, edge to edge, without touching the subject.

Why this exists: the generator renders a "plain 50% grey seamless studio backdrop" with a few grey
levels of vertical drift and, on some frames, a lighter rectangular panel behind the model with darker
outer margins. On a large flat field that reads as a visible box edge, so it is enforced numerically.

Two rules this tool exists to get right, both learned from files the user rejected:
  * the paint window must span the WHOLE field (+-30 levels). An early version painted only pixels
    within +-14 of 128, so it flattened the outer field to 128 and left the inner panel at 137 --
    which SHARPENED the edge instead of removing it.
  * background is defined by the shared mask in bgmask.py, per file. Deriving the protection ring from
    the base file left a 1px band of raw background at each tone's silhouette (a tone edit is a pixel
    thicker), and requiring border-connectivity only left enclosed pockets (arm/torso gap, space
    between the legs, under an asymmetric hem) standing at 120-137 inside a 128 field.

Usage (from repo root):
  python3 template/tools/flatten_backdrop.py                 # whole catalogue
  python3 template/tools/flatten_backdrop.py M15-let-ai-decide
ONE PASS ONLY. The mask is taken from the file as it stands, painted to 128, and saved once: re-running
this tool on its own output creeps ~0.3% of silhouette area per pass (JPEG ringing at the model's edge
qualifies as field, gets painted, and shaves the garment). Verified: five passes moved area by 3.9% and
changed subject-core pixels by up to 44 levels. Already-uniform files are never re-encoded.
Verify with: python3 template/tools/check_backdrop.py
"""
from PIL import Image
import numpy as np
import os, sys, glob, json, statistics
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from bgmask import background

TONE=['fair','light-warm','light-tan','medium-brown','deep','ebony']
ONLY=[a for a in sys.argv[1:] if not a.startswith('-')]
def load(p): return np.asarray(Image.open(p).convert('RGB'),dtype=int)

report=[]; changed_total=0; skipped=[]; nobg=[]
ROOT=os.environ.get('TPL_ROOT','template')
bases=sorted(glob.glob(os.environ.get('TPL_BASE',ROOT+'/base')+'/*.jpg'))
if ONLY: bases=[b for b in bases if any(o in os.path.basename(b) for o in ONLY)]
for base_p in bases:
    g=os.path.basename(base_p)
    for p in [base_p]+[f'{ROOT}/{t}/{g}' for t in TONE]:
        if not os.path.exists(p): continue
        X=load(p); L=X.mean(2)
        bg,_=background(X)
        if not bg.any(): nobg.append(p); continue
        before=(float(L[bg].mean()),float(L[bg].std()),int(L[bg].min()),int(L[bg].max()),float(bg.mean()))
        Y=X.copy(); Y[bg]=128
        n_changed=int((np.abs(Y-X).max(2)>0).sum())
        if n_changed==0: skipped.append(p); continue
        changed_total+=n_changed
        Image.fromarray(Y.astype(np.uint8)).save(p,quality=95,subsampling=0,optimize=False)
        report.append({'file':p,'before_mean':round(before[0],2),'before_std':round(before[1],2),
                       'before_range':[before[2],before[3]],'repainted':n_changed,'bg_frac':round(before[4],3)})
json.dump(report,open('/tmp/flatten_report.json','w'),indent=1)
if report:
    pre=[r['before_std'] for r in report]; off=[abs(r['before_mean']-128) for r in report]
    print(f"repainted {len(report)} files, {changed_total:,} px -> exact 128;  already uniform: {len(skipped)};  no background found: {len(nobg)}")
    print(f"before the fix: field std median={statistics.median(pre):.2f} max={max(pre):.2f}   |mean-128| median={statistics.median(off):.2f} max={max(off):.2f}")
    print("\nmost-offending frames fixed:")
    for r in sorted(report,key=lambda r:-abs(r['before_mean']-128))[:10]:
        print(f"  {r['file']:46s} mean={r['before_mean']:6.1f} std={r['before_std']:5.2f} range={r['before_range']} painted={r['repainted']:8,} bg={100*r['bg_frac']:.0f}%")
else:
    print(f"nothing to do: {len(skipped)} files already uniform, {len(nobg)} with no background")
