"""Read-only evaluated-mesh fixed cable to solid review. Run in Blender.
All fixed root descendants including new support/fastener solids are considered.
Moving Tray descendants and native morph cables are covered by motion audits.
"""
import bpy,sys,json,hashlib,math,time
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
args=sys.argv[sys.argv.index('--')+1:];base=Path(args[0]).resolve();bpy.ops.wm.open_mainfile(filepath=str(base));bpy.context.scene.frame_set(1)
meta=json.loads(base.with_name('components.json').read_text());root=bpy.data.objects['CabinetRoot'];dg=bpy.context.evaluated_depsgraph_get();route_names={r['name'] for r in meta['wiring_design']['fixed_routes']}
def under(o):
 while o:
  if o==root:return True
  o=o.parent
 return False
def moving(o):
 while o:
  if o.name.startswith('Tray_') or o.name=='SingleTray':return True
  o=o.parent
 return False
def mesh_info(o):
 ev=o.evaluated_get(dg);me=ev.to_mesh();vs=[o.matrix_world@v.co for v in me.vertices];fs=[tuple(p.vertices) for p in me.polygons];ev.to_mesh_clear()
 if not vs or not fs:return None
 lo=Vector([min(v[k] for v in vs) for k in range(3)]);hi=Vector([max(v[k] for v in vs) for k in range(3)]);return vs,fs,BVHTree.FromPolygons(vs,fs,all_triangles=False),lo,hi
def overlap(a,b):return all(a[3][i]<=b[4][i]+1e-7 and b[3][i]<=a[4][i]+1e-7 for i in range(3))
fixed=[];empty_fixed=[]
for o in bpy.context.scene.objects:
 if o.type!='MESH' or not under(o) or moving(o) or o.name in route_names or o.data.shape_keys:continue
 if o.get('initial_hidden',False):continue
 info=mesh_info(o)
 if info:fixed.append((o,info))
 else:empty_fixed.append(o.name)
records=[];allowed=[];tested=0
for ri,r in enumerate(meta['wiring_design']['fixed_routes']):
 ob=bpy.data.objects.get(r['name'])
 if not ob:raise ValueError('Missing route '+r['name'])
 source=mesh_info(ob);parent=bpy.data.objects.get(r.get('parent_node','CabinetRoot'));pts=[parent.matrix_world@Vector(p) for p in r['points_blender_m']];endpoints=[pts[0],pts[-1]];bound_ends=set(r.get('endpoint_node_names',[]))
 for target,info in fixed:
  if not overlap(source,info):continue
  tested+=1;hits=source[2].overlap(info[2])
  if not hits:continue
  contacts=[]
  for a,z in zip(pts,pts[1:]):
   d=z-a;n=d.length
   if n<1e-9:continue
   unit=d/n;start=a.copy();remaining=n
   for _ in range(6):
    pos,normal,face,dist=info[2].ray_cast(start,unit,remaining+1e-7)
    if pos is None:break
    contacts.append(pos);advance=(pos-start).length+1e-6;remaining-=advance
    if remaining<=0:break
    start=pos+unit*1e-6
  nearest_ends=[info[2].find_nearest(q)[3] for q in endpoints]
  nearest=min((d for d in nearest_ends if d is not None),default=1e9)*1000
  max_end=max((min((q-e).length for e in endpoints)*1000 for q in contacts),default=None)
  connector=(target.get('hybrid_role')=='connector' or any(s in target.name.lower() for s in ['plug','socket','connector','entry','terminal','inlet','input','output']))
  endpoint_named=target.name in bound_ends
  end_inside=any(all(info[3][k]-.00035<=q[k]<=info[4][k]+.00035 for k in range(3)) for q in endpoints)
  compact_connector=max(info[4][k]-info[3][k] for k in range(3))<.100
  narrow_end=(connector and compact_connector and (nearest<.35 or end_inside) and (max_end is None or max_end<25))
  rec={'route':r['name'],'part':target.name,'hybrid_role':target.get('hybrid_role','existing'),'surface_pair_count':len(hits),'centerline_contact_count':len(contacts),'contact_positions_blender_m':[[round(v,7) for v in q] for q in contacts],'max_distance_from_route_end_mm':None if max_end is None else round(max_end,4),'nearest_end_to_surface_mm':round(nearest,4),'explicit_endpoint_node':endpoint_named,'endpoint_inside_compact_connector':end_inside and compact_connector}
  if narrow_end:
   rec['classification']='expected endpoint connection; compact connector contains route end or touches within0.35mm, all measured crossings within25mm';allowed.append(rec)
  else:
   rec['classification']='review required; not broadly exempted by role';records.append(rec)
 print('FIXED_SOLID',ri+1,'of',len(route_names),'review',len(records),flush=True)
report={'blend_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'metadata_sha256':hashlib.sha256(base.with_name('components.json').read_bytes()).hexdigest(),'route_count':len(route_names),'fixed_mesh_count':len(fixed),'broadphase_pairs':tested,'review_pairs':records,'expected_endpoint_pairs':allowed,'method':'Evaluated actual tube/solid mesh BVH surface overlap plus centerline ray contacts. Includes new fasteners/service supports; does not blanket-ignore clips. Moves no geometry.','limits':'Surface intersections and declared endpoint classification; not electrical insulation/EMC, material tolerance, manufacturing, mechanical load or thermal certification.'}
report['empty_fixed_mesh_names']=empty_fixed
report['status']='passed' if not records and not empty_fixed else 'review_required'
out=Path(args[1]).resolve() if len(args)>1 else base.with_name('fixed_solid_audit.json');out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('FIXED_SOLID_COMPLETE',len(records),'review',len(allowed),'expected',len(empty_fixed),'empty fixed',flush=True)
