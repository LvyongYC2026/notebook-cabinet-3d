"""Read-only rear door clearance audit against original and hybrid fixed wiring and supports."""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=bpy.data.objects['CabinetRoot']
input_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
doors=[o for o in bpy.context.scene.objects if o.name.startswith('RearDoorPivot_')]
def under(o,p):
    while o:
        if o==p:return True
        o=o.parent
    return False
def shape(objects):
    pts=[];faces=[];dg=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        ev=o.evaluated_get(dg);m=ev.to_mesh()
        if not m:continue
        n=len(pts);pts.extend(ev.matrix_world@v.co for v in m.vertices)
        faces.extend(tuple(n+i for i in p.vertices) for p in m.polygons);ev.to_mesh_clear()
    if not pts:return None
    return [Vector([min(p[i] for p in pts) for i in range(3)]),Vector([max(p[i] for p in pts) for i in range(3)]),BVHTree.FromPolygons(pts,faces)]
def hit(a,b):return bool(a and b and not any(a[1][i]<b[0][i] or b[1][i]<a[0][i] for i in range(3)) and a[2].overlap(b[2]))
bpy.context.scene.frame_set(1)
for d in doors:d.animation_data_clear()
fixed=[o for o in bpy.context.scene.objects if o.type=='MESH' and under(o,root) and (o.get('wiring_design') or o.get('hybrid_role')) and not any(under(o,d) for d in doors)]
bpy.context.view_layer.update();fixed_shapes={o.name:shape([o]) for o in fixed}
door_parts={d.name:[o for o in bpy.context.scene.objects if o.type=='MESH' and under(o,d)] for d in doors}
results=[]
for a in range(0,106,5):
    for d in doors:d.rotation_euler.z=math.radians(a)
    bpy.context.view_layer.update();hits=[]
    for d in doors:
        ds=shape(door_parts[d.name])
        for name,fs in fixed_shapes.items():
            if hit(ds,fs):hits.append([d.name,name])
    results.append({'rear_door_degrees':a,'intersections':hits})
report={'method':'Evaluated mesh BVH, three rear doors at 22 simultaneous angles in 5 degree intervals',
    'blend_sha256':input_hash,
    'fixed_wiring_parts':len(fixed),'poses':results,'intersecting_pairs':sum(len(x['intersections']) for x in results),
    'limits':'Sampled mesh surfaces; not continuous swept solids or manufacturing tolerances.'}
report['status']='passed' if report['fixed_wiring_parts']>0 and report['intersecting_pairs']==0 else 'review_required'
out=Path(bpy.data.filepath).parent/'independent_hybrid_rear_motion.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('REAR_WIRING_AUDIT',len(fixed),report['intersecting_pairs'],flush=True)
