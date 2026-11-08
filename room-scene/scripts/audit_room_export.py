"""Independent GLB environment boundary and coordinate audit (Blender Python)."""
import json,struct,hashlib,sys,argparse
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
p=argparse.ArgumentParser();p.add_argument('--glb',required=True);p.add_argument('--metadata',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);file=Path(a.glb);raw=file.read_bytes();magic,version,size=struct.unpack_from('<4sII',raw,0)
assert magic==b'glTF' and version==2 and size==len(raw)
n,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
g=json.loads(raw[20:20+n]);meta=json.loads(Path(a.metadata).read_text());nodes=g.get('nodes',[])
parents={child:i for i,node in enumerate(nodes) for child in node.get('children',[])}
world={}
def matrix(i):
 if i in world:return world[i]
 node=nodes[i]
 if 'matrix' in node:m=Matrix([node['matrix'][j::4] for j in range(4)])
 else:
  r=node.get('rotation',[0,0,0,1]);q=Quaternion((r[3],r[0],r[1],r[2]));m=Matrix.LocRotScale(Vector(node.get('translation',[0,0,0])),q,Vector(node.get('scale',[1,1,1])))
 if i in parents:m=matrix(parents[i])@m
 world[i]=m;return m
lo=Vector((1e9,)*3);hi=Vector((-1e9,)*3);mesh_nodes=0
for i,node in enumerate(nodes):
 if 'mesh' not in node:continue
 mesh_nodes+=1;m=matrix(i)
 for prim in g['meshes'][node['mesh']]['primitives']:
  ac=g['accessors'][prim['attributes']['POSITION']]
  for x in [ac['min'][0],ac['max'][0]]:
   for y in [ac['min'][1],ac['max'][1]]:
    for z in [ac['min'][2],ac['max'][2]]:
     v=m@Vector((x,y,z));lo=Vector([min(lo[k],v[k])for k in range(3)]);hi=Vector([max(hi[k],v[k])for k in range(3)])
names=[n.get('name','')for n in nodes];forbidden=[n for n in names if n in {'CabinetRoot','SingleCabinetRoot'} or n.startswith(('Tray_','DoorPivot_','DynamicCable_','Studio_','Camera_'))]
root=[node for node in nodes if node.get('name')=='RoomEnvironmentRoot']
required=meta['cutaway_node_names']+['RoomWall_Back','RoomWall_Left','RoomWorkstation','RoomSecurityDoor']
missing=[n for n in required if n not in names]
# 12cm external wall thickness and 8cm floor thickness surround the exact
# 510x300x280cm net room in the cabinet-local Y-up export coordinates.
expected_min=(-2.67,-.08,-.545);expected_max=(2.67,2.86,2.695)
bounds_ok=all(abs(lo[i]-expected_min[i])<.003 and abs(hi[i]-expected_max[i])<.003 for i in range(3))
root_space=root[0].get('extras',{}).get('coordinate_space') if len(root)==1 else None
report={'glb_sha256':hashlib.sha256(raw).hexdigest(),'metadata_sha256':hashlib.sha256(Path(a.metadata).read_bytes()).hexdigest(),'node_count':len(nodes),'mesh_node_count':mesh_nodes,'bounds_gltf_m':{'min':list(lo),'max':list(hi)},'expected_exterior_bounds_match':bounds_ok,'environment_root_count':len(root),'coordinate_space':root_space,'forbidden_product_or_studio_nodes':forbidden,'missing_required_environment_groups':missing,'cameras_exported':len(g.get('cameras',[])),'lights_exported':len(g.get('extensions',{}).get('KHR_lights_punctual',{}).get('lights',[])),'limits':'Checks exported accessor bounding envelopes and scene graph, not rendered appearance or manufacturing tolerances.'}
report['status']='passed' if bounds_ok and len(root)==1 and root_space=='cabinet_local_gltf' and not forbidden and not missing and not report['cameras_exported'] and not report['lights_exported'] else 'review_required'
Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('ROOM_EXPORT',report['status'],report['bounds_gltf_m'])
