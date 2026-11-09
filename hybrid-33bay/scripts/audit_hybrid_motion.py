"""Read-only independent geometry audit of the hybrid 9-door/24-drawer cabinet.

Run with Blender --background MODEL.blend --python THIS.py -- --output report.json.
Uses evaluated triangle meshes, endpoint/mixed motion samples and occupied-envelope
ray clearance. This is not a continuous-motion, manufacturing or electrical test.
"""
import argparse, hashlib, json, math, re, sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser();p.add_argument('--output',required=True)
p.add_argument('--quick',action='store_true')
opt=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
scene=bpy.context.scene;scene.frame_set(1)
root=bpy.data.objects.get('CabinetRoot') or bpy.data.objects.get('SingleDrawerRoot')
if root is None:raise RuntimeError('Missing product root')
single=root.name!='CabinetRoot'
ids=['S1'] if single else [f'A{i}' for i in range(1,10)]+[f'B{i}' for i in range(1,25)]
right=['S1'] if single else [f'B{i}' for i in range(1,25)]
trays={i:bpy.data.objects.get('SingleTray' if single else 'Tray_'+i) for i in ids}
if any(t is None for t in trays.values()):raise RuntimeError('Missing expected tray')
def under(o,parent):
 while o:
  if o==parent:return True
  o=o.parent
 return False
def active(o):
 while o:
  if o.get('initial_hidden'):return False
  o=o.parent
 return True
def bay(o):
 while o:
  if o.get('bay_id'):return str(o['bay_id'])
  if o.name.startswith('Bay_'):return o.name[4:]
  o=o.parent
 return 'S1' if single else None
objects=[o for o in scene.objects if under(o,root) and o.type in {'MESH','CURVE','FONT'}]
doors=[o for o in scene.objects if under(o,root) and ('DoorPivot' in o.name)]
for o in [*trays.values(),*doors]:o.animation_data_clear()
for t in trays.values():t.location.y=0
for d in doors:
 d.rotation_euler.z=math.radians(float(d.get('swing_degrees',-95))) if re.match(r'DoorPivot_A\d+$',d.name) else 0
bpy.context.view_layer.update()

def shape(parts):
 points=[];faces=[];dg=bpy.context.evaluated_depsgraph_get()
 for ob in parts:
  ev=ob.evaluated_get(dg);mesh=ev.to_mesh()
  if mesh is None:continue
  offset=len(points);points.extend(ev.matrix_world@v.co for v in mesh.vertices)
  faces.extend(tuple(offset+i for i in f.vertices) for f in mesh.polygons);ev.to_mesh_clear()
 if not points:return None
 lo=Vector([min(v[i] for v in points) for i in range(3)])
 hi=Vector([max(v[i] for v in points) for i in range(3)])
 return lo,hi,BVHTree.FromPolygons(points,faces)
def overlap(a,b):
 if not a or not b or any(a[1][i]<b[0][i]-1e-7 or b[1][i]<a[0][i]-1e-7 for i in range(3)):return False
 return bool(a[2].overlap(b[2]))

moving={i:[o for o in objects if under(o,trays[i]) and active(o)] for i in ids}
dynamic=[o for o in objects if o.get('hybrid_role')=='cable_dynamic' and active(o)]
door_parts=[o for o in objects if any(under(o,d) for d in doors) and active(o)]
fixed=[o for o in objects if active(o) and not any(under(o,t) for t in trays.values()) and o not in dynamic and o not in door_parts]
# Fixed rails remain collision obstacles; only moving rail engagement and fasteners
# are excluded. Other tray/device geometry is checked against the fixed rails.
excluded={o.name:str(o.get('hybrid_role')) for o in fixed if o.get('hybrid_role') in {'fastener'}}
physical=[o for o in fixed if o.name not in excluded]
fixed_shapes={o.name:shape([o]) for o in physical}
payload={i:[o for o in moving[i] if o.get('hybrid_role') not in {'slide_moving','fastener','cable_dynamic'} and True] for i in right}
cables={i:[o for o in objects if active(o) and bay(o)==i and o.get('hybrid_role')=='cable_dynamic'] for i in right}
source_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
report={'blend_sha256':source_hash,'single':single,'expected_trays':len(ids),'actual_trays':len(trays),
 'drawer_ids':right,'fixed_mesh_count':len(physical),'fixed_role_counts':{},'excluded_attached_hardware':excluded,'excluded_moving_rail_engagement':[o.name for rows in moving.values() for o in rows if o.get('hybrid_role')=='slide_moving'],
 'moving_object_counts':{i:len(v) for i,v in moving.items()},'dynamic_cable_counts':{i:len(v) for i,v in cables.items()},
 'clearance':[],'poses':[],'intentional_cable_engagement':['Dynamic network to own FixedNetworkFeed and NICNetworkPlug','Dynamic DC to own FixedAdapterDC and DCMovingPlug'],
 'limits':'Sampled evaluated surface intersections and clearance rays; excludes intentional nested rails/fastener engagement. Does not establish continuous clearance, tolerances, load, stability, heat or electrical compliance.'}
for o in physical:
 role=o.get('hybrid_role','existing');report['fixed_role_counts'][role]=report['fixed_role_counts'].get(role,0)+1

# Measure upward from the actual load-bearing datum at the closed laptop footprint.
# All fixed hardware is eligible, including lights and locks; room lighting is not
# under the product root. References are declared device-footprint design assumptions.
for i in right:
 node=bpy.data.objects.get('Bay_'+i) if not single else bpy.data.objects['SingleDrawerRoot']
 origin=trays[i].matrix_world.translation.copy()
 ray_rows=[]
 for x in [-.119,-.045,.03,.105,.179]:
  for y in [-.254,-.20,-.15,-.10,-.046]:
   start=origin+Vector((x,y,.001));best=None;owner=None
   for name,sh in fixed_shapes.items():
    if sh is None or not(sh[0].x-1e-6<=start.x<=sh[1].x+1e-6 and sh[0].y-1e-6<=start.y<=sh[1].y+1e-6):continue
    hit,normal,face,dist=sh[2].ray_cast(start,Vector((0,0,1)),.5)
    if hit is not None and (best is None or dist<best):best=dist;owner=name
   ray_rows.append({'xy_cm':[x*100,y*100],'clear_cm':round((best+.001)*100,5) if best is not None else None,'obstacle':owner})
 valid=[r['clear_cm'] for r in ray_rows if r['clear_cm'] is not None]
 report['clearance'].append({'bay':i,'support_z_cm':round(origin.z*100,5),'rays':ray_rows,'minimum_clear_cm':min(valid) if valid else None,'all_rays_bounded':len(valid)==len(ray_rows)})

def pose(label,values):
 for i,t in trays.items():t.location.y=-values.get(i,0)/1000
 bpy.context.view_layer.update();hits=[];current={i:shape(payload[i]) for i in right}
 for i in right:
  sh=current[i]
  for ob in physical:
   if overlap(sh,fixed_shapes[ob.name]):hits.append(['drawer:'+i,ob.name])
  for j in right:
   if j>i and overlap(sh,current[j]):hits.append(['drawer:'+i,'drawer:'+j])
  for cb in cables[i]:
   cs=shape([cb])
   for ob in physical:
    # Exact connector engagement is evaluated by asset/end-ring tests instead.
    if bay(ob)==i and ob.name in ({'FixedNetworkFeed_'+i} if cb.name.endswith('_network') else {'FixedAdapterDC_'+i}):continue
    if overlap(cs,fixed_shapes[ob.name]):hits.append([cb.name,ob.name])
   for j in right:
    if overlap(cs,current[j]):
     for ob in payload[j]:
      if j==i and ob.name in ({i+'_NICNetworkPlug'} if cb.name.endswith('_network') else {i+'_DCMovingPlug'}):continue
      if overlap(cs,shape([ob])):hits.append([cb.name,ob.name])
 report['poses'].append({'name':label,'travel_mm':values,'intersections':hits})
 print('HYBRID_POSE',label,len(hits),flush=True)

steps=[0,80,160,240,320] if opt.quick else list(range(0,321,20))
for v in steps:pose('simultaneous_'+str(v),{i:v for i in ids})
# One moving drawer with every neighbour closed catches inter-level and column
# collisions hidden by the simultaneous all-equal samples.
for i in right:
 for v in ([160,320] if opt.quick else [80,160,240,320]):pose('individual_'+i+'_'+str(v),{i:v})
if len(right)>1:
 pose('checker_0_160_320',{i:[0,160,320][n%3] for n,i in enumerate(right)})
 pose('checker_320_0_160',{i:[320,0,160][n%3] for n,i in enumerate(right)})
pose('closed',{})
report['intersection_count']=sum(len(x['intersections']) for x in report['poses'])
report['clearance_pass']=all(x['all_rays_bounded'] and x['minimum_clear_cm']>=12.999 for x in report['clearance'])
report['coverage_pass']=all(payload[i] and len(cables[i])>=1 for i in right) and bool(physical)
report['status']='passed' if report['coverage_pass'] and report['clearance_pass'] and report['intersection_count']==0 else 'review_required'
Path(opt.output).parent.mkdir(parents=True,exist_ok=True);Path(opt.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('HYBRID_AUDIT',report['status'],report['intersection_count'],opt.output,flush=True)
