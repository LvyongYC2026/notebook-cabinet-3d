"""Read-only surface audit of fixed wiring against cabinet and service parts.

Invoke Blender with the candidate .blend followed by --python this file.
Endpoint engagements are reported separately; all other hits need review.
"""
import bpy, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

single = 'SingleCabinetRoot' in bpy.data.objects
root = bpy.data.objects['SingleCabinetRoot' if single else 'CabinetRoot']
def under(ob, parent):
    while ob:
        if ob == parent: return True
        ob = ob.parent
    return False
def mesh_shape(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    if not me or not me.vertices: return None
    ps = [ev.matrix_world @ v.co for v in me.vertices]
    fs = [tuple(f.vertices) for f in me.polygons]; ev.to_mesh_clear()
    return {'lo': Vector([min(p[i] for p in ps) for i in range(3)]), 'hi': Vector([max(p[i] for p in ps) for i in range(3)]),
        'tree': BVHTree.FromPolygons(ps, fs), 'centers': [sum((ps[i] for i in f), Vector()) / len(f) for f in fs]}
def overlap(a,b):
    if not a or not b or any(a['hi'][i] < b['lo'][i] or b['hi'][i] < a['lo'][i] for i in range(3)): return []
    return a['tree'].overlap(b['tree'])

bpy.context.scene.frame_set(1)
for ob in bpy.data.objects:
    if ob.name.startswith(('RearDoorPivot_', 'DoorPivot_', 'Tray_')) or ob.name in ('SingleDoorPivot','SingleTray','EquipmentDoorPivot'):
        ob.animation_data_clear()
        if 'Tray' in ob.name: ob.location.y=0
        else: ob.rotation_euler.z=0
bpy.context.view_layer.update()
blend_path=Path(bpy.data.filepath); base=blend_path.parent
meta_path=base/('model_metadata.json' if single else 'components.json')
input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [blend_path,meta_path]}
meta=json.loads(meta_path.read_text())
routes=meta.get('wiring_design',{}).get('fixed_routes',[])
route_names={r['name'] for r in routes}
objects=[o for o in bpy.context.scene.objects if under(o,root) and o.type in {'MESH','CURVE','FONT'}]
targets=[o for o in objects if o.type=='MESH' and o.name not in route_names and (
    o.name.startswith(('Housing_','Equipment_','Rear_Ventilation_','ServicePanel_','Wiring_')) or
    any(t in o.name for t in ('_RearAirDuct','_Shelf','_Partition','_Ceiling','_RearServiceRail','_CrossRail','_FrontPost')) or
    ('_Refined_fixed_' in o.name and any(t in o.name for t in ('ports_body','adapter_bracket_body','ac_socket_body','network_body','light_body','supports_')))
)]
shapes={o.name:mesh_shape(o) for o in targets}
hits=[];engagement=[]
for r in routes:
    ob=bpy.data.objects.get(r['name'])
    if not ob: hits.append({'route':r['name'],'error':'missing route mesh'}); continue
    sh=mesh_shape(ob)
    parent=bpy.data.objects.get(r.get('parent_node'))
    pts=[(parent.matrix_world @ Vector(p) if parent else Vector(p)) for p in r['points_blender_m']]
    for target in targets:
        pairs=overlap(sh,shapes[target.name])
        if not pairs: continue
        # A long straight tube quad can span an entire panel approach. Its
        # centroid is NOT the contact point. Raycast the route centerline to
        # locate actual crossings; tangential/radius-only hits stay for review.
        contacts=[]
        for a,b in zip(pts,pts[1:]):
            length=(b-a).length
            if length<1e-8: continue
            for origin,direction in [(a,(b-a)/length),(b,(a-b)/length)]:
                point,normal,index,distance=shapes[target.name]['tree'].ray_cast(origin,direction,length+1e-6)
                if point is not None: contacts.append(point)
        distances=[min((p-pts[0]).length,(p-pts[-1]).length)*1000 for p in contacts]
        farthest=max(distances) if distances else None
        record={'route':ob.name,'part':target.name,'surface_pairs':len(pairs),'centerline_contacts':len(contacts),'contact_positions_blender_m':[[round(v,6) for v in p] for p in contacts],'farthest_from_route_endpoint_mm':round(farthest,3) if farthest is not None else None}
        (engagement if farthest is not None and farthest<=15 else hits).append(record)
    print('FIXED_ROUTE_CHECK',ob.name,flush=True)
report={'method':'Evaluated mesh BVH against fixed structural and service parts; within 15mm of route endpoint classified separately for connector review',
    'mode':'single' if single else 'cabinet','input_sha256':input_hashes,'route_count':len(routes),'target_count':len(targets),
    'review_hits':hits,'endpoint_engagements':engagement,
    'limits':'Sampled polygon surface overlaps, not containment or full cable-cable analysis. Endpoint classification is a review aid, not automatic proof of a valid connector.'}
(base/'independent_fixed_route_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FIXED_ROUTE_AUDIT',len(routes),len(hits),'review hits',len(engagement),'endpoint engagements',flush=True)
