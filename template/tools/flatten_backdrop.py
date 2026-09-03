"""Force every backdrop to a mathematically uniform #808080.

Why this exists: image-generation models render the "plain 50% grey seamless studio backdrop"
with a few grey levels of vertical drift and, on some frames, a lighter/darker rectangular panel
behind the subject. On a large flat field that reads as a visible box edge or fade, so it is
enforced numerically instead of hoped for.

Method (no resampling, nothing inside the subject is touched):
  1. from base/<garment>.jpg, take pixels that are near-neutral and near-128;
  2. keep only the component connected to the image border  -> true outside field (never interior
     fabric-fold shadows, which can share that value range);
  3. erode 1px so anti-aliased silhouette edges are left alone;
  4. repaint only pixels that are also field-grey in the variant (|L-128|<=14, sat<=10) so skin,
     light-grey cloth (L~213) and dark footwear (L~60) can never be flattened;
  5. re-save at quality 95, 4:4:4.

Run after generating new tone variants, before committing:  python3 tools/flatten_backdrop.py
Post-fix invariant across all 161 current files: background mean 128.00 (+-0.005), std <=0.11.
"""

from PIL import Image
import numpy as np
from scipy import ndimage
import os, glob, json

TONE=['fair','light-warm','light-tan','medium-brown','deep','ebony']
def load(p): return np.asarray(Image.open(p).convert('RGB'),dtype=int)
def grey(L): return (np.abs(L.max(2)-L.min(2))<=6)&(np.abs(L.mean(2)-128)<=8)

report=[]; changed_total=0
for base_p in sorted(glob.glob('template/base/*.jpg')):
    g=os.path.basename(base_p)
    B=load(base_p); Lb=B.mean(2)
    m=grey(B)
    lab,n=ndimage.label(m)
    border=set(np.unique(np.concatenate([lab[0,:],lab[-1,:],lab[:,0],lab[:,-1]])))-{0}
    bg=np.isin(lab,list(border)) if border else np.zeros_like(m)
    bg=ndimage.binary_erosion(bg,structure=np.ones((3,3)),iterations=1)   # 1px safety ring at silhouette
    for p in [base_p]+[f'template/{t}/{g}' for t in TONE]:
        if not os.path.exists(p): continue
        X=load(p); Lx=X.mean(2); sat=X.max(2)-X.min(2)
        fill=bg&(np.abs(Lx-128)<=14)&(sat<=10)      # only repaint pixels that are field-grey in BOTH
        if not fill.any(): continue
        before=(float(Lx[fill].mean()),float(Lx[fill].std()),float(Lx[fill].min()),float(Lx[fill].max()))
        Y=X.copy(); Y[fill]=128
        n_changed=int((np.abs(Y-X).max(2)>0).sum())
        changed_total+=n_changed
        Image.fromarray(Y.astype(np.uint8)).save(p,quality=95,subsampling=0,optimize=False)
        report.append({'file':p,'bg_before_mean':round(before[0],2),'bg_before_std':round(before[1],2),
                       'bg_before_minmax':[int(before[2]),int(before[3])],'pixels_repainted':n_changed,
                       'frac_bg':round(float(fill.mean()),3)})
json.dump(report,open('/tmp/flatten_report.json','w'),indent=1)
import statistics
pre_std=[r['bg_before_std'] for r in report]
print(f"files processed: {len(report)}   total pixels repainted: {changed_total:,}")
print(f"before fix, background std across files: median={statistics.median(pre_std):.2f} max={max(pre_std):.2f}")
worst=sorted(report,key=lambda r:-r['bg_before_std'])[:12]
print("\nworst offenders fixed (std = uniformity error in grey levels):")
for r in worst: print(f"  {r['file']:46s} mean={r['bg_before_mean']:6.1f} std={r['bg_before_std']:5.2f} range={r['bg_before_minmax']} repainted={r['pixels_repainted']:7,}")
