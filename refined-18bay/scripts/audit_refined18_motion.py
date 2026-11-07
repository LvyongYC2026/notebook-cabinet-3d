"""Read-only, independent sampled motion audit of an already loaded cabinet .blend.

Checks moving payload and cables against fixed housing/service parts and all front
doors, plus front-door frames against fixed front structure and neighbouring doors.
This is not continuous swept-volume, tolerance, load or stability certification.
"""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

scene = bpy.context.scene
ids = [s + str(n) for s in 'AB' for n in range(1, 10)]
doors = {i: bpy.data.objects['DoorPivot_' + i] for i in ids}
trays = {i: bpy.data.objects['Tray_' + i] for i in ids}
for ob in [*doors.values(), *trays.values()]:
    ob.animation_data_clear()
scene.frame_set(1)
for ob in bpy.data.objects:
    if ob.name.startswith('RearDoorPivot_') or ob.name == 'EquipmentDoorPivot':
        ob.animation_data_clear()
        ob.rotation_euler.z = 0

def under(ob, parent):
    while ob:
        if ob == parent:
            return True
        ob = ob.parent
    return False

def bay_of(ob):
    while ob:
        if ob.name.startswith('Bay_'):
            return ob.name[4:]
        ob = ob.parent
    return None

def shape(objects):
    points, faces = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objects:
        ev = ob.evaluated_get(dg)
        mesh = ev.to_mesh()
        if mesh is None:
            continue
        start = len(points)
        points.extend(ev.matrix_world @ v.co for v in mesh.vertices)
        faces.extend(tuple(start + i for i in p.vertices) for p in mesh.polygons)
        ev.to_mesh_clear()
    if not points:
        return None
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    return lo, hi, BVHTree.FromPolygons(points, faces, all_triangles=False, epsilon=0)

def hit(a, b):
    if not a or not b or any(a[1][i] < b[0][i] or b[1][i] < a[0][i] for i in range(3)):
        return False
    return bool(a[2].overlap(b[2]))

product = bpy.data.collections['01_Product / 三模块智能柜']
objects = [o for o in product.all_objects if o.type in {'MESH', 'CURVE', 'FONT'}]
payload = {i: [o for o in objects if under(o, trays[i])] for i in ids}
laptops = {i: [o for o in payload[i] if 'laptop_laptop_body' in o.name] for i in ids}
door_parts = {i: [o for o in objects if under(o, doors[i]) and
                       any(s in o.name for s in ('DoorVertical', 'DoorHorizontal', 'Glass_'))] for i in ids}
active_cables = {i: [o for o in objects if o.name.startswith('DynamicCable_' + i + '_') or
                          (o.name.startswith('ParkingCable_' + i + '_') and not o.get('initial_hidden'))] for i in ids}
fixed = [o for o in objects if
         (o.name.startswith('Housing_') or any(s in o.name for s in
          ('_FrontPost', '_CrossRail', '_Partition', '_Shelf', '_Ceiling', '_RearServiceRail', '_RearAirDuct')) or
          ('_Refined_fixed_' in o.name and any(s in o.name for s in
           ('ports_body', 'adapter_bracket_body', 'ac_socket_body', 'network_body', 'light_body', 'supports_'))) or
          o.name.endswith('_PowerAdapter')) and
         not any(under(o, d) for d in doors.values())]
front_fixed = [o for o in fixed if any(s in o.name for s in
              ('_FrontPost', '_CrossRail', '_BaseFascia', '_Header', '_Side', '_Partition'))]
bpy.context.view_layer.update()
fixed_shapes = {o.name: shape([o]) for o in fixed}
poses = [(a, 0) for a in (0, 25, 50, 75, 95)] + [(95, t) for t in (80, 160, 240, 320)]
results = []
for angle, travel_mm in poses:
    for i in ids:
        doors[i].rotation_euler.z = -math.radians(min(angle, abs(doors[i].get('swing_degrees', 95))))
        trays[i].location.y = -travel_mm / 1000
    bpy.context.view_layer.update()
    ds = {i: shape(door_parts[i]) for i in ids}
    ps = {i: shape(payload[i]) for i in ids}
    cs = {i: shape(active_cables[i]) for i in ids}
    ls = {i: shape(laptops[i]) for i in ids}
    hits = []
    for i in ids:
        for ob in fixed:
            if hit(ps[i], fixed_shapes[ob.name]):
                hits.append(['payload:' + i, ob.name])
            if hit(cs[i], fixed_shapes[ob.name]):
                hits.append(['cables:' + i, ob.name])
        for ob in front_fixed:
            if hit(ds[i], fixed_shapes[ob.name]):
                hits.append(['door:' + i, ob.name])
        for j in ids:
            if hit(ps[i], ds[j]):
                hits.append(['payload:' + i, 'door:' + j])
            if hit(cs[i], ds[j]):
                hits.append(['cables:' + i, 'door:' + j])
            if hit(cs[i], ls[j]):
                hits.append(['cables:' + i, 'laptop:' + j])
            if j > i and hit(ds[i], ds[j]):
                hits.append(['door:' + i, 'door:' + j])
    results.append({'front_door_degrees': angle, 'all_trays_mm': travel_mm, 'intersections': hits})
    print('MOTION_POSE', angle, travel_mm, len(hits), flush=True)

report = {'method': 'Evaluated mesh triangle BVH, all 18 bays in nine simultaneous poses',
          'fixed_objects': len(fixed), 'bay_count': len(ids),
          'poses': results, 'intersecting_pairs': sum(len(r['intersections']) for r in results),
          'exclusions': 'Nested slide assemblies, fasteners, hinge hardware, intended connector/clip engagement; static-static pairs.',
          'limits': 'Sampling only, not continuous swept solids, containment, tolerance, strength or stability certification.'}
out = Path(bpy.data.filepath).parent / 'independent_motion_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('MOTION_AUDIT', str(out), report['intersecting_pairs'], flush=True)
