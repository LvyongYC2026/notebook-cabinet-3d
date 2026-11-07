"""Independent sampled collision checks; run against a loaded .blend, never save it."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

scene=bpy.context.scene
door=bpy.data.objects['SingleDoorPivot']; tray=bpy.data.objects['SingleTray']
door.animation_data_clear(); tray.animation_data_clear()
def under(obj,parent):
    while obj:
        if obj==parent:return True
        obj=obj.parent
    return False
def geometry(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=ev.to_mesh()
    if not mesh:return None
    points=[ev.matrix_world@v.co for v in mesh.vertices]
    faces=[tuple(p.vertices) for p in mesh.polygons]
    ev.to_mesh_clear()
    if not points or not faces:return None
    lo=Vector([min(p[i] for p in points) for i in range(3)])
    hi=Vector([max(p[i] for p in points) for i in range(3)])
    return (lo,hi,BVHTree.FromPolygons(points,faces,all_triangles=False,epsilon=0))
def intersects(a,b):
    if any(a[1][i]<b[0][i] or b[1][i]<a[0][i] for i in range(3)):return False
    return bool(a[2].overlap(b[2]))
solid_prefixes=('Housing_', 'Rear_Ventilation_', 'ServicePanel_', 'PowerAdapter_Block',
                'Adapter_Independent', 'Adapter_Shelf', 'Adapter_RearMount')
fixed=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(solid_prefixes)]
payload=[o for o in bpy.data.objects if o.type=='MESH' and (under(o,bpy.data.objects['Laptop']) or
         o.name.startswith(('Tray_Deck','Tray_FrontFold','Tray_RearLip','Tray_SideFold')))]
moving_cables=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('SingleDynamicCable')]
door_parts=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(('Door_VerticalFrame','Door_HorizontalFrame','Door_ClearGlass'))]
results=[]
for angle,travel in [(0,0),(25,0),(50,0),(75,0),(100,0),(100,.08),(100,.16),(100,.24),(100,.32)]:
    scene.frame_set(1);door.rotation_euler.z=-math.radians(angle);tray.location.y=-travel;bpy.context.view_layer.update()
    targets=set(fixed+payload+moving_cables+door_parts)
    shapes={o.name:geometry(o) for o in targets}
    hits=[]
    for a in payload+moving_cables:
        for b in fixed+door_parts:
            if shapes[a.name] and shapes[b.name] and intersects(shapes[a.name],shapes[b.name]):hits.append([a.name,b.name])
    for a in moving_cables:
        for b in payload:
            if 'Connector' in b.name or 'Port' in b.name:continue
            if shapes[a.name] and shapes[b.name] and intersects(shapes[a.name],shapes[b.name]):hits.append([a.name,b.name])
    for a in door_parts:
        for b in fixed:
            if shapes[a.name] and shapes[b.name] and intersects(shapes[a.name],shapes[b.name]):hits.append([a.name,b.name])
    results.append({'door_degrees':angle,'tray_mm':round(travel*1000),'intersections':hits})
report={'method':'evaluated mesh triangle BVH intersection, nine mechanism poses',
        'checks':'payload and moving cables vs fixed shell/service panel/adapter/door; moving cables vs laptop; frame/glass vs fixed shell',
        'excluded':'fasteners, rail nested surfaces, hinge knuckle assemblies, plug/socket engagement; not a continuous swept-solid or tolerance test',
        'poses':results,'intersecting_pairs':sum(len(x['intersections']) for x in results)}
out=Path(bpy.data.filepath).parent/'clearance_audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('CLEARANCE_AUDIT',json.dumps(report,ensure_ascii=False))
