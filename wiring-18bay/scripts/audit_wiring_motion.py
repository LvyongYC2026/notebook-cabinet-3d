"""Independent sampled interference audit for newly added tray wiring.

Run against a candidate .blend; does not save or alter the source asset.
Surface intersection sampling is not a continuous mechanical certification.
"""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

single = 'SingleCabinetRoot' in bpy.data.objects
input_hash = hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
root = bpy.data.objects['SingleCabinetRoot' if single else 'CabinetRoot']
ids = ['S1'] if single else [s + str(i) for s in 'AB' for i in range(1, 10)]
trays = {i: bpy.data.objects['SingleTray' if single else 'Tray_' + i] for i in ids}
doors = {i: bpy.data.objects['SingleDoorPivot' if single else 'DoorPivot_' + i] for i in ids}
def under(ob, parent):
    while ob:
        if ob == parent: return True
        ob = ob.parent
    return False
def hidden(ob):
    while ob:
        if ob.get('initial_hidden'): return True
        ob = ob.parent
    return False
def shape(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg); mesh = ev.to_mesh()
    if mesh is None or not mesh.vertices: return None
    pts = [ev.matrix_world @ v.co for v in mesh.vertices]
    faces = [tuple(f.vertices) for f in mesh.polygons]
    ev.to_mesh_clear()
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi, BVHTree.FromPolygons(pts, faces, all_triangles=False)
def intersects(a, b):
    return bool(a and b and not any(a[1][i] < b[0][i] or b[1][i] < a[0][i] for i in range(3)) and a[2].overlap(b[2]))

scene = bpy.context.scene; scene.frame_set(1)
for ob in list(trays.values()) + list(doors.values()): ob.animation_data_clear()
for ob in bpy.data.objects:
    if ob.name.startswith('RearDoorPivot_') or ob.name == 'EquipmentDoorPivot':
        ob.animation_data_clear(); ob.rotation_euler.z = 0
objects = [o for o in scene.objects if under(o, root) and o.type in {'MESH', 'CURVE', 'FONT'}]
moving = {i: [o for o in objects if under(o, trays[i]) and o.get('wiring_design') and not hidden(o)] for i in ids}
network = {i: bpy.data.objects.get('SingleDynamicCable_network' if single else 'DynamicCable_' + i + '_network') for i in ids}
fixed = [o for o in objects if not any(under(o, t) for t in trays.values()) and not any(under(o, d) for d in doors.values()) and (
    o.name.startswith('Housing_') or any(s in o.name for s in ('_FrontPost', '_CrossRail', '_Partition', '_Shelf', '_Ceiling', '_RearServiceRail', '_RearAirDuct')) or
    ('_Refined_fixed_' in o.name and any(s in o.name for s in ('ports_body', 'adapter_bracket_body', 'ac_socket_body', 'network_body', 'light_body', 'supports_'))) or
    o.name.startswith(('PowerAdapter_', 'ServicePanel_')) or o.name.endswith('_PowerAdapter')
)]
doorparts = [o for o in objects if any(under(o, d) for d in doors.values()) and any(s in o.name.lower() for s in ('frame', 'glass', 'doorvertical', 'doorhorizontal'))]
laptops = [o for o in objects if ('laptop_laptop_body' in o.name or o.name in ('Laptop_LowerChassis', 'Laptop_UpperDeck', 'Laptop_DisplayBack', 'Laptop_DisplayBezel', 'Laptop_LCD'))]
power = [o for o in objects if o.name.startswith(('SingleDynamicCable_power', 'DynamicCable_')) and o.name.endswith('_power') and not hidden(o)]
parking_supports = [o for o in objects if o.name.startswith('PowerParking_S1')] if single else []
bpy.context.view_layer.update()
fixed_shapes = {o.name: shape(o) for o in fixed}
parking_shapes = {o.name: shape(o) for o in parking_supports}
results = []
for travel in range(0, 321, 20):
    for i in ids:
        doors[i].rotation_euler.z = math.radians(-100 if single else -95)
        trays[i].location.y = -travel / 1000
    bpy.context.view_layer.update()
    ds = {o.name: shape(o) for o in doorparts}
    ls = {o.name: shape(o) for o in laptops}
    pcs = {o.name: shape(o) for o in power}
    hits = []
    for lname,lsh in ls.items():
        for pname,psh in parking_shapes.items():
            if intersects(lsh,psh): hits.append([lname,pname])
    for i in ids:
        for ob in moving[i] + ([network[i]] if network[i] else []):
            sh = shape(ob)
            for name, fs in fixed_shapes.items():
                if intersects(sh, fs): hits.append([ob.name, name])
            for name, dsh in ds.items():
                if intersects(sh, dsh): hits.append([ob.name, name])
            if '_Cable' in ob.name:
                for name, lsh in ls.items():
                    if intersects(sh, lsh): hits.append([ob.name, name])
            if ob.get('wiring_design'):
                for name, psh in pcs.items():
                    if intersects(sh, psh): hits.append([ob.name, name])
    results.append({'travel_mm': travel, 'intersections': hits})
    print('NEW_WIRING_POSE', travel, len(hits), flush=True)
report = {'method': 'Evaluated mesh triangle BVH, candidate new active NIC/USB and blue cable, 17 tray positions at 20mm intervals, front doors fully open',
    'blend_sha256': input_hash,
    'mode': 'single' if single else 'cabinet', 'new_moving_objects': sum(len(v) for v in moving.values()),
    'fixed_objects': len(fixed), 'door_objects': len(doorparts), 'laptop_bodies': len(laptops), 'parking_supports_checked':len(parking_supports), 'poses': results,
    'intersecting_pairs': sum(len(r['intersections']) for r in results),
    'limits': 'Sampled surface intersections only. Excludes intentional connector/clip engagement, nested slides, new fixed-trunk audit. Not tolerances or certification.'}
out = Path(bpy.data.filepath).parent / 'independent_new_wiring_motion.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('NEW_WIRING_AUDIT', out, report['intersecting_pairs'], flush=True)
