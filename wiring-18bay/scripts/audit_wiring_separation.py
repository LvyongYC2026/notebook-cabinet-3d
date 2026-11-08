"""Exact polyline segment distances for fixed cable outer-envelope review.

Run with Blender's bundled Python/NumPy; metadata uses metres in the identity
CabinetRoot coordinate frame. This measures geometry, not EMC compliance.
"""
import json, sys, hashlib
from pathlib import Path
import numpy as np
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
p=Path(args[args.index('--metadata')+1] if '--metadata' in args else Path(__file__).resolve().parents[1]/'output/cabinet/wiring_candidate/components.json')
meta=json.loads(p.read_text());routes=meta['wiring_design']['fixed_routes']

def segment_distances(a,b,common):
    pa=np.asarray(a[:-1])[:,None,:];pb=np.asarray(b[:-1])[None,:,:]
    u=np.diff(np.asarray(a),axis=0)[:,None,:];v=np.diff(np.asarray(b),axis=0)[None,:,:]
    w=pa-pb;aa=np.sum(u*u,axis=2);bb=np.sum(u*v,axis=2);cc=np.sum(v*v,axis=2)
    dd=np.sum(u*w,axis=2);ee=np.sum(v*w,axis=2);den=aa*cc-bb*bb
    aa=np.maximum(aa,1e-20);cc=np.maximum(cc,1e-20)
    candidates=[]
    def add(s,t,valid=None):
        aclose=pa+s[...,None]*u;bclose=pb+t[...,None]*v
        d2=np.sum((aclose-bclose)**2,axis=2)
        if valid is not None:d2=np.where(valid,d2,np.inf)
        # Only electrical branches sharing the same endpoint can intentionally
        # join. Exclude the terminal volume, not the entire route pair.
        for q in common:
            joint=(np.sum((aclose-q)**2,axis=2)<.020**2)&(np.sum((bclose-q)**2,axis=2)<.020**2)
            d2=np.where(joint,np.inf,d2)
        ix=np.unravel_index(np.argmin(d2),d2.shape)
        # Endpoint parameters may broadcast along one axis.
        ash=np.broadcast_to(aclose,(*d2.shape,3));bsh=np.broadcast_to(bclose,(*d2.shape,3))
        candidates.append((float(d2[ix]),ash[ix].tolist(),bsh[ix].tolist(),list(ix)))
    zeros=np.zeros_like(bb);ones=np.ones_like(bb)
    add(zeros,np.clip(ee/cc,0,1))
    add(ones,np.clip((ee+bb)/cc,0,1))
    add(np.clip(-dd/aa,0,1),zeros)
    add(np.clip((bb-dd)/aa,0,1),ones)
    safe=np.where(np.abs(den)>1e-20,den,1)
    s=(bb*ee-cc*dd)/safe;t=(aa*ee-bb*dd)/safe
    add(s,t,(den>1e-20)&(s>=0)&(s<=1)&(t>=0)&(t<=1))
    return min(candidates,key=lambda x:x[0])

overlaps=[];nearest=[];joint_pairs=[]
for i,a in enumerate(routes):
    for b in routes[i+1:]:
        # Network and power never share an intentional electrical junction.
        cross=(a['kind']=='network')!=(b['kind']=='network')
        common=[]
        if not cross:
            for ap in [a['points_blender_m'][0],a['points_blender_m'][-1]]:
                for bp in [b['points_blender_m'][0],b['points_blender_m'][-1]]:
                    if np.linalg.norm(np.asarray(ap)-bp)<1e-6:common.append(np.asarray(ap))
        if common:joint_pairs.append([a['name'],b['name']])
        value,ap,bp,segments=segment_distances(a['points_blender_m'],b['points_blender_m'],common)
        if not np.isfinite(value):continue
        distance=float(np.sqrt(max(0,value))*1000);clearance=distance-a['radius_mm']-b['radius_mm']
        entry={'routes':[a['name'],b['name']],'different_signal_class':cross,'centerline_distance_mm':round(distance,5),
            'outer_surface_clearance_mm':round(clearance,5),'points_blender_m':[[round(x,7) for x in q] for q in [ap,bp]],'segments':[int(x) for x in segments]}
        nearest.append(entry)
        if clearance<-.05:overlaps.append(entry)
report={'method':'Exact minimum distances between every pair of polyline segments; endpoint-to-segment and interior line-line solutions',
    'metadata_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'route_count':len(routes),'pair_count':len(nearest),
    'overlaps':sorted(overlaps,key=lambda e:e['outer_surface_clearance_mm']),
    'closest_different_signal_classes':sorted([e for e in nearest if e['different_signal_class']],key=lambda e:e['outer_surface_clearance_mm'])[:12],
    'common_terminal_pairs':joint_pairs,'common_terminal_exclusion_radius_mm':20,
    'limits':'Geometric tube envelopes with 0.05mm numeric tolerance, not insulation/EMC clearance, real connector detail or manufacturing certification. Common power terminal joins within 20mm are separately excluded.'}
out=p.parent/'independent_cable_separation.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('CABLE_SEPARATION',len(routes),len(nearest),'pairs',len(overlaps),'overlaps',flush=True)
