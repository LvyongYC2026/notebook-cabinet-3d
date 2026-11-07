"""Read-only, sampled interference audit for the refined 18-bay cabinet.

Run against an already loaded candidate .blend; this script never saves the .blend.
The JSON report is written beside bpy.data.filepath. Distances are metres in Blender.
"""
import bpy
import json
import hashlib
import math
import re
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SCENE = bpy.context.scene
BAY_IDS = [f'{side}{number}' for side in 'AB' for number in range(1, 10)]
EMPTY_IDS = ['A3', 'B2', 'B6']
OUT = Path(bpy.data.filepath).resolve().parent / 'refined_clearance_audit.json'
OBJECTS = list(SCENE.objects)
SHAPE_TYPES = {'MESH', 'CURVE', 'FONT'}


def descendants(root):
    return {root} | {item for child in root.children for item in descendants(child)}


def geometry(ob):
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    if not mesh:
        return None
    points = [ev.matrix_world @ v.co for v in mesh.vertices]
    faces = [tuple(poly.vertices) for poly in mesh.polygons]
    ev.to_mesh_clear()
    if not points or not faces:
        return None
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError('Non-finite geometry: ' + ob.name)
    lo = Vector([min(point[i] for point in points) for i in range(3)])
    hi = Vector([max(point[i] for point in points) for i in range(3)])
    tree = BVHTree.FromPolygons(points, faces, all_triangles=False, epsilon=0)
    return lo, hi, tree


def intersects(a, b):
    if not a or not b:
        return False
    if any(a[1][i] < b[0][i] or b[1][i] < a[0][i] for i in range(3)):
        return False
    return bool(a[2].overlap(b[2]))


def token(ob):
    # Refined template names may carry a bay prefix, which is irrelevant to a role.
    return re.sub(r'^[AB][1-9]_Refined_', '', ob.name)


def is_shell(ob):
    name = ob.name
    return (name.startswith('Housing_')
            or bool(re.match(r'^(Left|Right)_(Partition|FrontPost|CrossRail)', name))
            or bool(re.match(r'^[AB][1-9]_(Shelf|Ceiling|RearServiceRail|RearAirDuct)', name)))


def is_fixed_internal(ob):
    name = token(ob)
    return name.startswith(('fixed_ports_', 'fixed_interface_panel_', 'fixed_adapter_bracket_', 'fixed_cables_', 'fixed_light_', 'fixed_network_', 'fixed_ac_socket_', 'fixed_power_', 'fixed_supports_', 'ParkingDock_', 'ServicePanel_', 'PowerAdapter_', 'Adapter_Independent',
                            'Adapter_Shelf', 'Adapter_WallMount', 'Adapter_Basket',
                            'Adapter_RearMount', 'AdapterBracket_', 'CableParking_',
                            'Cable_Parking', 'StowedCableDock')) or bool(re.match(r'^[AB][1-9]_PowerAdapter', ob.name))


def is_main_door(ob):
    name = token(ob)
    return (name.startswith(('Door_VerticalFrame', 'Door_HorizontalFrame', 'Door_ClearGlass'))
            or bool(re.match(r'^[AB][1-9]_Door(Vertical|Horizontal)', ob.name))
            or bool(re.match(r'^Glass_[AB][1-9]', ob.name)))


def is_tray_structure(ob):
    return token(ob).startswith(('tray_', 'Tray_Deck', 'Tray_FrontFold', 'Tray_RearLip', 'Tray_SideFold')) or bool(re.match(r'^[AB][1-9]_Tray(Deck|Fold)', ob.name))


def is_connector(ob):
    return token(ob).startswith(('tray_network_', 'tray_power_', 'laptop_network_', 'laptop_power_')) or any(word in token(ob) for word in ('Connector', 'Port', 'CableBoot', 'CableNeck'))


SCENE.frame_set(1)
missing = [name for b in BAY_IDS for name in ('Bay_' + b, 'DoorPivot_' + b, 'Tray_' + b) if name not in bpy.data.objects]
if missing:
    raise AssertionError('Missing required nodes: ' + ', '.join(missing))
trays = {b: bpy.data.objects['Tray_' + b] for b in BAY_IDS}
doors = {b: bpy.data.objects['DoorPivot_' + b] for b in BAY_IDS}
bays = {b: bpy.data.objects['Bay_' + b] for b in BAY_IDS}
laptops = {b: bpy.data.objects.get('Laptop_' + b) for b in BAY_IDS}
# Clearing animation only changes the in-memory audit scene; no .blend save follows.
for ob in list(trays.values()) + list(doors.values()):
    ob.animation_data_clear()
    if ob in doors.values():
        ob.rotation_euler.z = 0
for ob in OBJECTS:
    if ob.name.startswith('RearDoorPivot_') or ob.name == 'EquipmentDoorPivot':
        ob.animation_data_clear()
        ob.rotation_euler.z = 0
base_tray_locations = {b: ob.location.copy() for b, ob in trays.items()}
max_door_degrees = {b: abs(float(ob.get('swing_degrees', ob.get('open_degrees', 95)))) for b, ob in doors.items()}
all_moving = set().union(*(descendants(o) for o in list(trays.values()) + list(doors.values())))
fixed = [ob for ob in OBJECTS if ob.type in SHAPE_TYPES and ob not in all_moving and (is_shell(ob) or is_fixed_internal(ob))]
all_door_parts = {b: [ob for ob in descendants(doors[b]) if ob.type in SHAPE_TYPES and is_main_door(ob)] for b in BAY_IDS}
BUNDLES = {}
for b in BAY_IDS:
    lap_parts = descendants(laptops[b]) if laptops[b] else set()
    payload = [ob for ob in descendants(trays[b]) if ob.type in SHAPE_TYPES and (ob in lap_parts or is_tray_structure(ob))]
    cables = [ob for ob in descendants(bays[b]) if ob.type in SHAPE_TYPES and (ob.name.startswith('DynamicCable_' + b + '_') or ob.get('dynamicCable'))]
    # Stowed empty-bay cables are static but must also avoid the tray sweep.
    parked = [ob for ob in descendants(bays[b]) if ob.type in SHAPE_TYPES and not ob.get('initial_hidden') and not ob.hide_render and (ob.get('stowed') or ob.get('motion') == 'stowed' or ob.name.startswith('StowedCable_' + b + '_'))]
    BUNDLES[b] = dict(payload=payload, cables=cables, parked=parked)

bpy.context.view_layer.update()
fixed_shapes = {ob.name: geometry(ob) for ob in fixed}
closed_door_shapes = {ob.name: geometry(ob) for group in all_door_parts.values() for ob in group}
report = {
    'model': Path(bpy.data.filepath).name,
    'model_sha256': hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
    'method': 'Evaluated polygon mesh triangle BVH surface intersections, epsilon 0; AABB broad phase; no .blend mutation is saved.',
    'checked': [
        '18 bays individually: moving tray sheet/folds and laptop vs fixed cabinet sheet/frame, service panel, adapter basket/adapter, own door and adjacent closed doors',
        'Dynamic cables vs the same fixed structures, doors, and laptop/tray payload, except intentional connector engagement',
        'Stowed empty-bay cables vs moving tray and the same fixed structures/doors',
        'Moving door frame/glass vs selected fixed structures and adjacent closed doors',
    ],
    'excluded': [
        'Fastener threads/heads, nested slide rails, hinge knuckles, rubber/seal compression and intentional plug/socket contacts',
        'Cable-to-fixed-feed contact: fixed_cables groups excluded only from cable-vs-fixed checks. Stowed plugs/cables contacting ParkingDock/Parking supports are intentional; active cables remain checked against these parking mounts. All mounts remain checked against tray/laptop and door; small electrical contact internals excluded',
        'Service/rear-door sweep, unsampled combinations, continuous swept solids, minimum clearance tolerances, full containment and manufacturing/load/thermal/electrical certification',
        'BVH reports intersecting surfaces; it is not a robust solid-overlap or tolerance solver',
    ],
    'expected_counts': {'bays': 18, 'trays': 18, 'front_bay_doors': 18, 'laptops': 15, 'empty_bays': EMPTY_IDS},
    'counts': {'bays': len(bays), 'trays': len(trays), 'front_bay_doors': len(doors), 'laptops': sum(o is not None for o in laptops.values()), 'empty_bays': [b for b, o in laptops.items() if o is None]},
    'selected_geometry': {'fixed_count': len(fixed), 'fixed_object_names': sorted(ob.name for ob in fixed), 'bays': {}},
    'native_morph_validation': {'expected_active_cables': 30, 'actual_active_cables': sum(len(v['cables']) for v in BUNDLES.values()), 'mismatches': []},
    'door_limits_degrees': max_door_degrees,
    'poses': [],
    'combined_poses': [],
    'fixed_body_shell_audit': {'method': 'Fixed major interface/light/adapter bodies vs actual shelf, ceiling, partition and exterior side sheets; attachment pillars, clips, rail supports and shims excluded as intended mounting contacts.', 'intersections': []},
}
report['counts_match'] = report['counts'] == report['expected_counts']
fixed_main = [o for o in fixed if token(o).startswith(('fixed_ports_', 'fixed_interface_panel_', 'fixed_adapter_bracket_', 'fixed_light_', 'fixed_network_', 'fixed_ac_socket_', 'fixed_power_')) or re.match(r'^[AB][1-9]_PowerAdapter', o.name)]
fixed_sheets = [o for o in fixed if re.match(r'^[AB][1-9]_(Shelf|Ceiling)', o.name) or re.match(r'^(Left|Right)_Partition', o.name) or (o.name.startswith('Housing_') and '_Side' in o.name)]
report['fixed_body_shell_audit']['body_names'] = sorted(o.name for o in fixed_main)
report['fixed_body_shell_audit']['sheet_names'] = sorted(o.name for o in fixed_sheets)
for a in fixed_main:
    for b in fixed_sheets:
        if intersects(fixed_shapes.get(a.name), fixed_shapes.get(b.name)):
            report['fixed_body_shell_audit']['intersections'].append({'a': a.name, 'b': b.name})
for b in BAY_IDS:
    bundle = BUNDLES[b]
    payload, cables, parked = (bundle[k] for k in ('payload', 'cables', 'parked'))
    own_door = all_door_parts[b]
    other_door = [ob for other, group in all_door_parts.items() if other != b for ob in group]
    report['selected_geometry']['bays'][b] = {k: sorted(ob.name for ob in bundle[k]) for k in bundle}
    report['selected_geometry']['bays'][b]['door_parts'] = sorted(ob.name for ob in own_door)
    assert payload and own_door, 'Audit selector missed tray or door for ' + b
    angles = sorted(set([0, 25, 50, 75, max_door_degrees[b]]))
    poses = [(angle, 0) for angle in angles if angle <= max_door_degrees[b]] + [(max_door_degrees[b], t) for t in (80, 160, 240, 320)]
    for angle, mm in poses:
        doors[b].rotation_euler.z = -math.radians(angle)
        trays[b].location = base_tray_locations[b] + Vector((0, -mm / 1000, 0))
        bpy.context.view_layer.update()
        for cable in cables:
            keys = cable.data.shape_keys if cable.type == 'MESH' else None
            key = keys.key_blocks.get('TrayExtended320mm') if keys else None
            value = float(key.value) if key else None
            if value is None or abs(value - mm / 320) > 0.00001:
                report['native_morph_validation']['mismatches'].append({'bay_id': b, 'object': cable.name, 'travel_mm': mm, 'expected': mm / 320, 'actual': value})
        changing = set(payload + cables + parked + own_door)
        shapes = {ob.name: geometry(ob) for ob in changing}
        shapes.update(fixed_shapes)
        shapes.update({ob.name: closed_door_shapes[ob.name] for ob in other_door})
        hits = set()
        def test(a, target_list, category):
            for target in target_list:
                if a == target:
                    continue
                if intersects(shapes.get(a.name), shapes.get(target.name)):
                    hits.add((category, a.name, target.name))
        for ob in payload:
            test(ob, fixed + own_door + other_door, 'payload_vs_structure')
        for ob in cables + parked:
            test(ob, [f for f in fixed if not token(f).startswith('fixed_cables_') and not (ob in parked and token(f).startswith(('ParkingDock_', 'fixed_supports_Parking')))] + own_door + other_door, 'cable_vs_structure')
            test(ob, [p for p in payload if not is_connector(p)], 'cable_vs_payload')
        for ob in own_door:
            test(ob, fixed + other_door, 'door_vs_structure')
        pose = {'bay_id': b, 'door_degrees': angle, 'tray_mm': mm,
                'intersections': [{'category': category, 'a': a, 'b': other} for category, a, other in sorted(hits)]}
        report['poses'].append(pose)
    doors[b].rotation_euler.z = 0
    trays[b].location = base_tray_locations[b]
    bpy.context.view_layer.update()
    print('BAY_AUDIT', b, sum(len(p['intersections']) for p in report['poses'] if p['bay_id'] == b), flush=True)

# Global states expose adjacent open-door/tray collisions that isolated sweeps miss.
scenarios = [
    ('all_doors_open_trays_home', {b: 0 for b in BAY_IDS}, set(BAY_IDS)),
    ('all_doors_open_all_trays_160', {b: 160 for b in BAY_IDS}, set(BAY_IDS)),
    ('all_doors_open_all_trays_320', {b: 320 for b in BAY_IDS}, set(BAY_IDS)),
    ('alternating_open_and_extended', {b: (320 if int(b[1:]) % 2 else 0) for b in BAY_IDS}, {b for b in BAY_IDS if int(b[1:]) % 2}),
    ('mixed_neighboring_travel', {b: (0, 160, 320)[(int(b[1:]) - 1) % 3] for b in BAY_IDS}, set(BAY_IDS)),
]
for label, travel, opened in scenarios:
    for b in BAY_IDS:
        doors[b].rotation_euler.z = -math.radians(max_door_degrees[b]) if b in opened else 0
        trays[b].location = base_tray_locations[b] + Vector((0, -travel[b] / 1000, 0))
    bpy.context.view_layer.update()
    moving = set(ob for b in BAY_IDS for k in ('payload', 'cables', 'parked') for ob in BUNDLES[b][k])
    moving.update(ob for group in all_door_parts.values() for ob in group)
    shapes = dict(fixed_shapes)
    shapes.update({ob.name: geometry(ob) for ob in moving})
    hits = set()
    def compare(a, targets, category):
        for other in targets:
            if a != other and intersects(shapes.get(a.name), shapes.get(other.name)):
                hits.add((category, *sorted((a.name, other.name))))
    for b in BAY_IDS:
        bundle = BUNDLES[b]
        all_frames = [ob for group in all_door_parts.values() for ob in group]
        for ob in bundle['payload']:
            compare(ob, fixed + all_frames, 'payload_vs_structure')
            compare(ob, [p for other in BAY_IDS if other != b for p in BUNDLES[other]['payload']], 'adjacent_payloads')
        for ob in bundle['cables'] + bundle['parked']:
            compare(ob, [f for f in fixed if not token(f).startswith('fixed_cables_') and not (ob in bundle['parked'] and token(f).startswith(('ParkingDock_', 'fixed_supports_Parking')))] + all_frames, 'cable_vs_structure')
            compare(ob, [p for other in BAY_IDS for p in BUNDLES[other]['payload'] if not is_connector(p)], 'cable_vs_payload')
        for ob in all_door_parts[b]:
            compare(ob, fixed + [p for other in BAY_IDS if other != b for p in all_door_parts[other]], 'door_vs_structure')
        for cable in bundle['cables']:
            keys = cable.data.shape_keys if cable.type == 'MESH' else None
            key = keys.key_blocks.get('TrayExtended320mm') if keys else None
            value = float(key.value) if key else None
            if value is None or abs(value - travel[b] / 320) > 0.00001:
                report['native_morph_validation']['mismatches'].append({'scenario': label, 'bay_id': b, 'object': cable.name, 'travel_mm': travel[b], 'expected': travel[b] / 320, 'actual': value})
    report['combined_poses'].append({'scenario': label, 'door_limits_used': True, 'open_bays': sorted(opened), 'tray_mm': travel,
                                    'intersections': [{'category': category, 'a': a, 'b': other} for category, a, other in sorted(hits)]})
    print('COMBINED_AUDIT', label, len(hits), flush=True)
report['sample_count'] = len(report['poses']) + len(report['combined_poses'])
report['intersection_occurrences'] = sum(len(p['intersections']) for p in report['poses'] + report['combined_poses'])
unique = sorted({(hit['category'], hit['a'], hit['b']) for p in report['poses'] + report['combined_poses'] for hit in p['intersections']})
report['unique_intersecting_pairs'] = [{'category': c, 'a': a, 'b': b} for c, a, b in unique]
morph = report['native_morph_validation']
report['passed_within_scope'] = report['counts_match'] and report['intersection_occurrences'] == 0 and morph['actual_active_cables'] == morph['expected_active_cables'] and not morph['mismatches'] and not report['fixed_body_shell_audit']['intersections']
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('REFINED_CLEARANCE_AUDIT', str(OUT), 'poses=', report['sample_count'], 'intersections=', report['intersection_occurrences'], 'counts_match=', report['counts_match'], 'fixed_body_intersections=', len(report['fixed_body_shell_audit']['intersections']), flush=True)
