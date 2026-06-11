#!/usr/bin/env python
"""Regenerate Benchmark/data/benchmark_results.{png,svg} from results/ JSON.

Run from repo root with the project python env:
  /home/hn533621/.conda/envs/amber_development/bin/python Benchmark/scripts/make_benchmark_figure.py

The DOMAIN map is a complete partition of the 68 clean studies — every clean
study lands in exactly one domain, so the domain panel sums to 68 (same as the
difficulty panel). Method-domains (QM/MM, Enh. sampling / FE) take precedence by
deliverable; otherwise a study is filed by biomolecular class.
"""
import json, glob, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
import numpy as np
sys.path.insert(0, '.')
from Benchmark.scripts import scoring

CLEAN = {'001','005','006','007','009','010','011','013','014','015','016','020','021','023','025',
 '027','028','029','030','031','032','033','035','036','038','040','041','042','043','045','046',
 '047','048','049','050','054','055','056','057','059','060','062','063','066','067','068','070',
 '071','072','074','075','076','077','081','082','083','084','085','086','087','089','090','091',
 '092','093','096','098','100'}

objs = {json.load(open(f))['study_id']: json.load(open(f)) for f in glob.glob('Benchmark/results/study_*.json')}
rows = [objs[s] for s in CLEAN if s in objs and not objs[s]['blocked']]
def sc(o): return scoring.score_study(o['checkpoints'])['total'] * 100
overall = sum(sc(o) for o in rows) / len(rows)

tiers = ['easy','medium','hard','very-hard']; tlab = ['Easy','Medium','Hard','Very-hard']
tier_s = [np.mean([sc(o) for o in rows if o['difficulty']==t]) for t in tiers]
tier_n = [sum(1 for o in rows if o['difficulty']==t) for t in tiers]

dims = ['C1','C2','C3','C4','C5']
dimlab = ['System Build','Simulation\nMethodology','Simulation\nCompletion','Analysis','Literature\nmatch']
dim_s = [100*np.mean([o['checkpoints'][c]['credit'] for o in rows if o['checkpoints'][c]['applicable']]) for c in dims]

# Complete partition of the 68 clean studies (sums to 68).
DOMAIN = {
 'Enh. sampling / FE': ['010','011','015','025','027','029','031','035','045','067','076','084','085','091','100'],
 'QM/MM':              ['028','072','074'],
 'Metalloprotein':     ['033','047','048','057','082','083'],
 'Membrane':           ['006','013','016','032','036','038','054','075','087'],
 'Carbohydrate':       ['005','040','046','060','081'],
 'DNA':                ['014','020','023','030','041','050','096'],
 'RNA':                ['001','043','056','068'],
 'Protein-ligand':     ['009','042','055','066','077','089','092','093'],
 'Protein':            ['007','021','049','059','062','063','070','071','086','090','098'],
}
# integrity check: partition must cover all 68 exactly once
_all = [i for ids in DOMAIN.values() for i in ids]
assert len(_all) == len(set(_all)) == len(CLEAN), f"DOMAIN not a clean partition: {len(_all)} ids, {len(set(_all))} unique, {len(CLEAN)} clean"
assert set(_all) == CLEAN, f"DOMAIN != CLEAN: missing {CLEAN-set(_all)}, extra {set(_all)-CLEAN}"

dom_lab, dom_s, dom_n = [], [], []
for d, ids in DOMAIN.items():
    v = [sc(objs[i]) for i in ids if i in objs and i in CLEAN and not objs[i]['blocked']]
    if v: dom_lab.append(d); dom_s.append(np.mean(v)); dom_n.append(len(v))

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.edgecolor':'#444','axes.linewidth':0.8})
TEAL='#1f8a8a'; TEAL2='#2ca5a5'; DARK='#0d3b3b'; GREY='#cfd8d8'; ORANGE='#e08a3c'
def hlabel(ax, bars, vals, xmin):
    for b, v in zip(bars, vals):
        if (v-xmin) > (ax.get_xlim()[1]-xmin)*0.18:
            ax.text(v-(ax.get_xlim()[1]-xmin)*0.015, b.get_y()+b.get_height()/2, f"{v:.1f}", va='center', ha='right', color='white', fontweight='bold', fontsize=9.5)
        else:
            ax.text(v+(ax.get_xlim()[1]-xmin)*0.015, b.get_y()+b.get_height()/2, f"{v:.1f}", va='center', ha='left', color=DARK, fontweight='bold', fontsize=9.5)

fig = plt.figure(figsize=(15,8.4)); fig.patch.set_facecolor('white')
gs = fig.add_gridspec(2,3, height_ratios=[1.15,1.0], hspace=0.40, wspace=0.40, left=0.105, right=0.965, top=0.87, bottom=0.07)

axA = fig.add_axes([0.045,0.50,0.20,0.36]); axA.set_aspect('equal'); axA.axis('off'); frac = overall/100
axA.add_artist(Wedge((0,0),1,0,360,width=0.30,fc=GREY))
axA.add_artist(Wedge((0,0),1,90-360*frac,90,width=0.30,fc=TEAL))
axA.text(0,0.05,f"{overall:.1f}",ha='center',va='center',fontsize=39,fontweight='bold',color=DARK)
axA.text(0,-0.24,"/ 100",ha='center',va='center',fontsize=14,color='#555')
axA.text(0,-1.34,"Overall score",ha='center',fontsize=13,fontweight='bold',color=DARK)
axA.set_xlim(-1.25,1.25); axA.set_ylim(-1.55,1.3)

axB = fig.add_subplot(gs[0,1:]); order = np.argsort(dom_s); yd = np.arange(len(dom_lab))
b = axB.barh(yd,[dom_s[i] for i in order],color=TEAL,height=0.66,edgecolor='white')
axB.set_yticks(yd); axB.set_yticklabels([f"{dom_lab[i]}  (n={dom_n[i]})" for i in order],fontsize=10)
axB.set_xlim(80,101); axB.set_xlabel("Mean study score (/100)")
axB.set_title("Score by biomolecular / method domain",fontweight='bold',loc='left',color=DARK,pad=8)
hlabel(axB,b,[dom_s[i] for i in order],80); axB.spines[['top','right']].set_visible(False); axB.grid(axis='x',ls=':',alpha=0.4)

axC = fig.add_subplot(gs[1,0]); yc = np.arange(len(dims))[::-1]
bc = axC.barh(yc,dim_s,color=[TEAL,TEAL,TEAL,TEAL,ORANGE],height=0.66,edgecolor='white')
axC.set_yticks(yc); axC.set_yticklabels(dimlab,fontsize=9); axC.set_xlim(80,101); axC.set_xlabel("Mean credit (/100)")
axC.set_title("Score by rubric checkpoint",fontweight='bold',loc='left',color=DARK,pad=8)
hlabel(axC,bc,dim_s,80); axC.spines[['top','right']].set_visible(False); axC.grid(axis='x',ls=':',alpha=0.4)

axD = fig.add_subplot(gs[1,1:]); yt = np.arange(len(tiers))[::-1]
bd = axD.barh(yt,tier_s,color=[TEAL2,TEAL,TEAL,DARK],height=0.62,edgecolor='white')
axD.set_yticks(yt); axD.set_yticklabels([f"{t}  (n={n})" for t,n in zip(tlab,tier_n)],fontsize=10)
axD.set_xlim(80,101); axD.set_xlabel("Mean study score (/100)")
axD.set_title("Score by difficulty tier",fontweight='bold',loc='left',color=DARK,pad=8)
hlabel(axD,bd,tier_s,80); axD.spines[['top','right']].set_visible(False); axD.grid(axis='x',ls=':',alpha=0.4)

fig.suptitle("AmberMD Agent — Autonomous Molecular Dynamics Benchmark",fontsize=18,fontweight='bold',color=DARK,x=0.5,ha='center',y=0.95)
fig.savefig('Benchmark/data/benchmark_results.png',dpi=200,facecolor='white')
fig.savefig('Benchmark/data/benchmark_results.svg',facecolor='white')
print(f"overall={overall:.2f}  domain n sum={sum(dom_n)}  tier n sum={sum(tier_n)}  clean={len(CLEAN)}")
