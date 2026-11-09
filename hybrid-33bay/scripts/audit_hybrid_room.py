"""Independent, read-only room installation audit; run using Blender's Python.

First run on the released cabinet with --baseline-out, then on the room blend
with --baseline. Mesh checks preserve source geometry; room clearance checks are
sampled geometric checks, not fabrication or egress certification.
"""
import bpy, json, math, hashlib, sys, argparse
from array import array
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args=argparse.ArgumentParser()
args.add_argument('--baseline-out');args.add_argument('--baseline');args.add_argument('--output')
opt=args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
file=Path(bpy.data.filepath);scene=bpy.context.scene
root=bpy.data.objects.get('CabinetRoot')
if not root: raise RuntimeError('Expected CabinetRoot')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def under(o,p):
 while o:
  if o==p:return True
  o=o.parent
 return False
def fingerprint(o):
 data={'type':o.type,'parent':o.parent.name if o.parent else None}
 if o!=root:data['basis']=[round(v,7) for row in o.matrix_basis for v in row];data['parent_inverse']=[round(v,7) for row in o.matrix_parent_inverse for v in row]
 if o.type=='MESH':
  h=hashlib.sha256();m=o.data
  coords=array('f',[0])*len(m.vertices)*3;m.vertices.foreach_get('co',coords);h.update(coords.tobytes())
  loops=array('i',[0])*len(m.loops);m.loops.foreach_get('vertex_index',loops);h.update(loops.tobytes())
  counts=array('i',[0])*len(m.polygons);m.polygons.foreach_get('loop_total',counts);h.update(counts.tobytes())
  if m.shape_keys:
   for key in m.shape_keys.key_blocks:
    v=array('f',[0])*len(key.data)*3;key.data.foreach_get('co',v);h.update(key.name.encode());h.update(v.tobytes())
  data.update(mesh_sha256=h.hexdigest(),vertices=len(m.vertices),faces=len(m.polygons))
 return data
scene.frame_set(1);bpy.context.view_layer.update()
source={o.name:fingerprint(o) for o in scene.objects if under(o,root)}
if opt.baseline_out:
 Path(opt.baseline_out).write_text(json.dumps({'blend_sha256':sha(file),'objects':source},ensure_ascii=False,indent=2)+'\n');print('BASELINE',len(source));raise SystemExit
if not opt.baseline:raise RuntimeError('--baseline required for room audit')
base=json.loads(Path(opt.baseline).read_text());changes=[]
for name,old in base['objects'].items():
 now=source.get(name)
 if now is None:changes.append({'name':name,'issue':'missing'});continue
 for key,val in old.items():
  if name=='CabinetRoot' and key=='parent':continue
  if now.get(key)!=val:changes.append({'name':name,'field':key})
room=bpy.data.objects.get('RoomEnvironmentRoot')
if not room:raise RuntimeError('Expected RoomEnvironmentRoot')
environment=[o for o in scene.objects if under(o,room) and o.type=='MESH']
extra_source_names=sorted(set(source)-set(base['objects']))

def shape(objects):
 pts=[];faces=[];dg=bpy.context.evaluated_depsgraph_get()
 for o in objects:
  ev=o.evaluated_get(dg);m=ev.to_mesh()
  if not m:continue
  n=len(pts);pts.extend(ev.matrix_world@v.co for v in m.vertices)
  faces.extend(tuple(n+i for i in p.vertices) for p in m.polygons);ev.to_mesh_clear()
 if not pts:return None
 return (Vector([min(p[i] for p in pts) for i in range(3)]),Vector([max(p[i] for p in pts) for i in range(3)]),BVHTree.FromPolygons(pts,faces))
def hit(a,b):return bool(a and b and not any(a[1][i]<b[0][i]-1e-6 or b[1][i]<a[0][i]-1e-6 for i in range(3)) and a[2].overlap(b[2]))
def visible_initial(o):
 while o:
  if o.get('initial_hidden'):return False
  o=o.parent
 return True
# Environment includes hidden/cutaway architecture. Only floor contact surfaces
# are excluded from the moving-object test; walls and furniture remain physical.
fixed=[o for o in environment if o.get('room_role') not in {'floor','display_helper','sign','lighting'}]
fixed_shapes={o.name:shape([o]) for o in fixed}
def boxes_overlap(a0,a1,b0,b1):return all(a1[i]>b0[i]+1e-6 and b1[i]>a0[i]+1e-6 for i in range(3))
operation_intrusions=[];cabinet_envelope_intrusions=[]
for o in fixed:
 if o.get('room_role') not in {'furniture','plant','door'}:continue
 sh=fixed_shapes[o.name]
 if not sh:continue
 if boxes_overlap(sh[0],sh[1],(.9,1.05,0),(4.2,2.25,1.85)):operation_intrusions.append(o.name)
 if boxes_overlap(sh[0],sh[1],(.9,2.25,0),(4.2,2.9,1.85)):cabinet_envelope_intrusions.append(o.name)

ids=[f'A{i}' for i in range(1,10)]+[f'B{i}' for i in range(1,25)]
trays={i:bpy.data.objects['Tray_'+i] for i in ids}
front=[bpy.data.objects['DoorPivot_'+i] for i in ids if i.startswith('A')]+[bpy.data.objects['EquipmentDoorPivot']]
rear=[bpy.data.objects['RearDoorPivot_'+s] for s in ['Left','Center','Right']]
for o in list(trays.values())+front+rear:o.animation_data_clear()
for o in rear:o.rotation_euler.z=0
for t in trays.values():t.location.y=0
parts={d.name:[o for o in scene.objects if o.type=='MESH' and under(o,d) and visible_initial(o)] for d in front}
poses=[];front_min_y=float('inf')
for fraction in [i/20 for i in range(21)]:
 for d in front:
  angle=float(d.get('swing_degrees',d.get('open_degrees',105 if d.name=='EquipmentDoorPivot' else -95)))
  d.rotation_euler.z=math.radians(angle)*fraction
 bpy.context.view_layer.update();hits=[]
 for d in front:
  sh=shape(parts[d.name]);front_min_y=min(front_min_y,sh[0].y)
  for name,fs in fixed_shapes.items():
   if hit(sh,fs):hits.append([d.name,name])
 poses.append({'fraction':fraction,'intersections':hits})
tray_poses=[];tray_min_y=float('inf')
for mm in range(0,321,20):
 for t in trays.values():t.location.y=-mm/1000
 bpy.context.view_layer.update();hits=[]
 for name,t in trays.items():
  objects=[o for o in scene.objects if o.type=='MESH' and under(o,t) and visible_initial(o)]
  sh=shape(objects);tray_min_y=min(tray_min_y,sh[0].y)
  for fname,fs in fixed_shapes.items():
   if hit(sh,fs):hits.append([name,fname])
 tray_poses.append({'travel_cm':mm/10,'intersections':hits})
report={'blend_sha256':sha(file),'source_blend_sha256':base['blend_sha256'],'source_objects_checked':len(base['objects']),'expected_bay_count':33,'actual_tray_count':len(trays),'front_hinged_doors':len(front),'right_drawer_count':sum(i.startswith('B') for i in trays),'source_geometry_or_hierarchy_changes':changes,'cabinet_root_count':sum(o.name=='CabinetRoot' for o in scene.objects),'cabinet_root_position_m':list(root.location),'cabinet_root_scale':list(root.scale),'room_environment_meshes':len(environment),'collision_environment_meshes':len(fixed),'front_door_sweep_samples':poses,'tray_samples':tray_poses,'front_moving_min_room_y_cm':front_min_y*100,'tray_assembly_min_room_y_cm':tray_min_y*100,'operation_zone_front_boundary_cm':105,'remaining_depth_after_front_door_sweep_cm':(front_min_y-1.05)*100,'remaining_depth_after_tray_assembly_cm':(tray_min_y-1.05)*100,'limits':'Surface intersections at 21 door fractions and 17 tray positions. Entire tray assemblies include laptops and connected parts; mechanical tray dimension labels use tray metal only. Excludes floor contact and clearance guide overlays. No egress, thermal, structural or manufacturing certification. Rear maintenance doors are unavailable in room mode because nominal rear clearance is 10 cm.'}
report['unexpected_cabinet_descendants']=extra_source_names
report['furniture_or_door_in_closed_operation_zone']=operation_intrusions
report['furniture_or_door_in_cabinet_envelope']=cabinet_envelope_intrusions
report['placement_matches_reference']=all(abs(root.location[i]-v)<1e-6 for i,v in enumerate((2.55,2.575,0))) and all(abs(v-1)<1e-6 for v in root.scale)
report['intersection_count']=sum(len(p['intersections']) for p in poses+tray_poses)
report['status']='passed' if not changes and not extra_source_names and not operation_intrusions and not cabinet_envelope_intrusions and report['placement_matches_reference'] and not report['intersection_count'] else 'review_required'
out=Path(opt.output) if opt.output else file.parent/'independent_hybrid_room_audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('ROOM_INSTALLATION_AUDIT',report['status'],len(changes),report['intersection_count'],out,flush=True)
