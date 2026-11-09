"""Read-only targeted A-side motion audit for the hybrid cabinet revision.

Blender -b MODEL.blend -P scripts/audit_hybrid_left.py -- \
  --metadata components.json --output independent_hybrid_left.json \
  [--expected-blend-sha256 HASH] [--expected-metadata-sha256 HASH]

Only revised original fixed objects and new hybrid fixed objects are obstacles.
All active Tray_A1..A9 descendants (including rail/fastener parts) plus the 17
active A native cables are sampled every 20 mm. All nine A doors are sampled at 21 angles.
No .blend is saved; temporary pose edits apply to this background process only.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

GEOMETRY = {'MESH', 'CURVE', 'FONT', 'SURFACE'}
LEFT = [f'A{i}' for i in range(1, 10)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def under(obj, parent):
    while obj:
        if obj == parent:
            return True
        obj = obj.parent
    return False


def inherited(obj, key):
    while obj:
        if key in obj:
            return obj[key]
        obj = obj.parent
    return None


def active(obj):
    while obj:
        if obj.get('initial_hidden'):
            return False
        obj = obj.parent
    return True


def canonical(name):
    return str(name).removesuffix('_Mesh')


def shape(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    if mesh is None:
        return None
    try:
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()
    if not vertices or not triangles:
        return None
    return {'min': Vector([min(v[i] for v in vertices) for i in range(3)]),
            'max': Vector([max(v[i] for v in vertices) for i in range(3)]),
            'vertices': vertices, 'triangles': triangles,
            'tree': BVHTree.FromPolygons(vertices, triangles, all_triangles=True)}


def broad_overlap(a, b):
    return bool(a and b and all(a['max'][i] >= b['min'][i]-1e-8 and
                              b['max'][i] >= a['min'][i]-1e-8 for i in range(3)))


def gltf_point(point):
    # Blender X/Y/Z -> GLTF X/Z/-Y; metadata is Bay-local GLTF metres.
    return Vector((point[0], -point[2], point[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-blend-sha256')
    parser.add_argument('--expected-metadata-sha256')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    blend = Path(bpy.data.filepath).resolve()
    metadata_path = Path(args.metadata).resolve()
    blend_sha, metadata_sha = digest(blend), digest(metadata_path)
    if args.expected_blend_sha256 and args.expected_blend_sha256 != blend_sha:
        raise RuntimeError('Input blend does not match requested frozen SHA256')
    if args.expected_metadata_sha256 and args.expected_metadata_sha256 != metadata_sha:
        raise RuntimeError('Input metadata does not match requested frozen SHA256')
    meta = json.loads(metadata_path.read_text())
    changed = set(meta.get('source_provenance', {}).get('intentional_original_object_changes', []))
    if not changed:
        raise RuntimeError('intentional_original_object_changes must explicitly define this audit scope')
    root = bpy.data.objects.get('CabinetRoot')
    if root is None:
        raise RuntimeError('CabinetRoot missing')
    scene = bpy.context.scene
    scene.frame_set(1)
    all_objects = [o for o in scene.objects if under(o, root)]
    geometry = [o for o in all_objects if o.type in GEOMETRY]
    all_trays = [o for o in all_objects if re.fullmatch(r'Tray_[AB]\d+', o.name)]
    all_doors = [o for o in all_objects if not o.type in GEOMETRY and
                 (o.get('interaction') == 'door' or re.match(r'^(?:DoorPivot_|RearDoorPivot_|EquipmentDoorPivot$)', o.name))]
    trays = {bay: bpy.data.objects.get('Tray_'+bay) for bay in LEFT}
    left_doors = {bay: bpy.data.objects.get('DoorPivot_'+bay) for bay in LEFT}
    if any(t is None for t in trays.values()) or any(d is None for d in left_doors.values()):
        raise RuntimeError('Expected A1..A9 trays and doors missing')
    for obj in [*all_trays, *all_doors]:
        obj.animation_data_clear()
    for tray in all_trays:
        tray.location.y = 0
    for door in all_doors:
        door.rotation_euler.z = math.radians(float(door.get('swing_degrees', -95))) if re.fullmatch(r'DoorPivot_A\d+', door.name) else 0
    bpy.context.view_layer.update()

    index = {}
    for obj in all_objects:
        index.setdefault(canonical(obj.name), []).append(obj)
    def named_geometry(names):
        found = set()
        for name in names:
            for obj in index.get(canonical(name), []):
                if obj.type in GEOMETRY:
                    found.add(obj)
                found.update(child for child in obj.children_recursive if child.type in GEOMETRY)
        return found

    native_specs = [p for p in meta.get('cable_paths', []) if p.get('bay_id') in LEFT
                    and p.get('morph_target') and not p.get('stowed') and p.get('motion') != 'stowed']
    all_native = set()
    for spec in meta.get('cable_paths', []):
        if spec.get('morph_target') and not spec.get('stowed') and spec.get('motion') != 'stowed':
            all_native.update(named_geometry(spec.get('source_node_names', [])))
    all_native.update(o for o in geometry if inherited(o, 'hybrid_role') == 'cable_dynamic')
    cables, spec_for_object = [], {}
    missing_cables = []
    for spec in native_specs:
        parts = sorted((o for o in named_geometry(spec.get('source_node_names', [])) if active(o)), key=lambda o: o.name)
        if not parts:
            missing_cables.append(spec['id'])
        for obj in parts:
            cables.append(obj)
            spec_for_object[obj.name] = spec
    cables = sorted(set(cables), key=lambda o: o.name)
    moving = {bay: sorted((o for o in geometry if under(o, tray) and active(o)), key=lambda o: o.name)
              for bay, tray in trays.items()}
    door_parts = {bay: sorted((o for o in geometry if under(o, door) and active(o)), key=lambda o: o.name) for bay, door in left_doors.items()}

    candidates = [o for o in geometry if o.name in changed or inherited(o, 'hybrid_role') is not None]
    excluded, fixed = {}, []
    for obj in candidates:
        reason = ('inactive_initial_variant' if not active(obj) else
                  'tray_descendant' if any(under(obj, tray) for tray in all_trays) else
                  'door_descendant' if any(under(obj, door) for door in all_doors) else
                  'native_dynamic_cable' if obj in all_native else None)
        if reason:
            excluded[obj.name] = reason
        else:
            fixed.append(obj)
    fixed.sort(key=lambda o: o.name)
    fixed_shapes = {o.name: shape(o) for o in fixed}
    empty_fixed = [name for name, sh in fixed_shapes.items() if sh is None]
    missing_changed = sorted(name for name in changed if bpy.data.objects.get(name) is None)

    # No broad class or bay exemption: only this exact native-to-fixed connector
    # object pair may qualify. All overlapping cable triangles must lie within a
    # bounded endpoint zone, otherwise the pair is reported as an intersection.
    endpoint_pairs = {}
    for cable in cables:
        spec = spec_for_object[cable.name]
        bay = spec['bay_id']
        network = spec.get('keep_connected_when_empty') is True
        target = spec.get('fixed_endpoint_node') or f'{bay}_Refined_fixed_{"network" if network else "power"}_body'
        if target not in fixed_shapes:
            continue
        endpoint_pairs[(cable.name, target)] = {
            'spec': spec, 'target': target,
            'zone_mm': max(6.0, float(spec.get('radius_mm', 0))*3),
            'reason': 'Exact native fixed-end connector engagement; endpoint-local triangles only'}

    report = {
        'status': 'running', 'blend_path': str(blend), 'blend_sha256': blend_sha,
        'metadata_path': str(metadata_path), 'metadata_sha256': metadata_sha,
        'script_sha256': digest(__file__),
        'scope': 'A1..A9 tray descendants and 17 active native cables against revised/new fixed objects; A1..A9 doors against the same fixed set',
        'fixed_selection_rule': 'active geometric object in intentional_original_object_changes OR inherited hybrid_role; then exclude all tray/door descendants and native dynamic cables',
        'changed_original_names': len(changed), 'removed_changed_names': missing_changed,
        'fixed_objects': [{'name': o.name, 'hybrid_role': inherited(o, 'hybrid_role'),
                           'revised_original': o.name in changed,
                           'vertices': len(fixed_shapes[o.name]['vertices']) if fixed_shapes[o.name] else 0,
                           'triangles': len(fixed_shapes[o.name]['triangles']) if fixed_shapes[o.name] else 0} for o in fixed],
        'excluded_candidates': excluded, 'empty_evaluated_fixed_objects': empty_fixed,
        'tray_objects': {bay: [o.name for o in objects] for bay, objects in moving.items()},
        'hidden_tray_variants_excluded': [o.name for o in geometry if any(under(o,t) for t in trays.values()) and not active(o)],
        'native_specs': [p['id'] for p in native_specs], 'native_objects': [o.name for o in cables],
        'missing_native_specs': missing_cables, 'door_objects': {bay: [o.name for o in parts] for bay, parts in door_parts.items()},
        'permitted_endpoint_pairs': [{'moving': a, 'fixed': b, 'zone_mm': rule['zone_mm'], 'reason': rule['reason']}
                                     for (a,b), rule in sorted(endpoint_pairs.items())],
        'tray_poses': [], 'door_poses': [], 'empty_evaluated_moving_objects': [],
        'limits': 'Discrete evaluated triangle-surface BVH intersections only. No claim of continuous swept volume, containment-only overlap, minimum clearance, load, electrical compliance or rail/fastener manufacturing fit. No whole rail/fastener group is excluded. Only current initial occupancy is tested; source .blend is never saved.'
    }
    tested_pairs = 0
    def check_pose(parts):
        nonlocal tested_pairs
        hits, contacts = [], []
        for obj in parts:
            sh = shape(obj)
            if sh is None:
                report['empty_evaluated_moving_objects'].append(obj.name)
                continue
            for fixed_obj in fixed:
                other = fixed_shapes[fixed_obj.name]
                if not broad_overlap(sh, other):
                    continue
                tested_pairs += 1
                overlaps = sh['tree'].overlap(other['tree'])
                if not overlaps:
                    continue
                row = {'moving': obj.name, 'fixed': fixed_obj.name, 'triangle_pair_count': len(overlaps)}
                rule = endpoint_pairs.get((obj.name, fixed_obj.name))
                if rule:
                    spec = rule['spec']
                    parent = bpy.data.objects[spec.get('parent_node') or 'Bay_'+spec['bay_id']]
                    end = parent.matrix_world @ gltf_point(spec['fixed'])
                    vertices = {index for face, _ in overlaps for index in sh['triangles'][face]}
                    maximum = max((sh['vertices'][i]-end).length for i in vertices)*1000
                    row.update({'fixed_endpoint_world_blender_m': list(end), 'furthest_overlapping_cable_triangle_vertex_mm': maximum,
                                'permitted_endpoint_zone_mm': rule['zone_mm']})
                    if maximum <= rule['zone_mm']+1e-6:
                        row['reason'] = rule['reason']
                        contacts.append(row)
                        continue
                hits.append(row)
        return hits, contacts

    for travel in range(0, 321, 20):
        for tray in trays.values():
            tray.location.y = -travel/1000
        bpy.context.view_layer.update()
        hits, contacts = check_pose([o for parts in moving.values() for o in parts] + cables)
        influences = {}
        for cable in cables:
            spec = spec_for_object[cable.name]
            keys = getattr(cable.evaluated_get(bpy.context.evaluated_depsgraph_get()).data, 'shape_keys', None)
            key = keys.key_blocks.get(spec['morph_target']) if keys else None
            influences[cable.name] = float(key.value) if key else None
        report['tray_poses'].append({'travel_mm': travel, 'native_morph_values': influences, 'intersections': hits, 'intentional_endpoint_contacts': contacts})
        print('HYBRID_LEFT_TRAYS', travel, 'hits', len(hits), 'endpoint_contacts', len(contacts), flush=True)
    for tray in trays.values():
        tray.location.y = 0
    for index_pose in range(21):
        degrees = 95*index_pose/20
        for door in left_doors.values():
            door.rotation_euler.z = math.copysign(math.radians(degrees), float(door.get('swing_degrees', -95)))
        bpy.context.view_layer.update()
        hits, contacts = check_pose([o for parts in door_parts.values() for o in parts])
        report['door_poses'].append({'doors': LEFT, 'degrees': degrees, 'intersections': hits, 'intentional_endpoint_contacts': contacts})
        print('HYBRID_LEFT_DOORS', degrees, 'hits', len(hits), flush=True)

    report['empty_evaluated_moving_objects'] = sorted(set(report['empty_evaluated_moving_objects']))
    report['fixed_object_count'] = len(fixed)
    report['bvh_pair_tests_after_broadphase'] = tested_pairs
    report['intersection_count'] = sum(len(p['intersections']) for p in report['tray_poses']+report['door_poses'])
    report['intentional_endpoint_contact_count'] = sum(len(p['intentional_endpoint_contacts']) for p in report['tray_poses']+report['door_poses'])
    report['source_files_unchanged'] = digest(blend) == blend_sha and digest(metadata_path) == metadata_sha
    report['native_morph_pose_failures'] = [{'travel_mm': pose['travel_mm'], 'object': name, 'value': value}
        for pose in report['tray_poses'] for name, value in pose['native_morph_values'].items()
        if value is None or abs(value-pose['travel_mm']/320) > 1e-5]
    report['coverage_pass'] = (not report['native_morph_pose_failures'] and len(native_specs) == 17 and len(cables) >= 17 and not missing_cables and all(moving.values())
                               and all(door_parts.values()) and bool(fixed) and not empty_fixed
                               and not report['empty_evaluated_moving_objects'] and report['source_files_unchanged'])
    report['status'] = 'passed_within_scope' if report['coverage_pass'] and report['intersection_count'] == 0 else 'review_required'
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('HYBRID_LEFT_AUDIT', report['status'], 'intersections', report['intersection_count'],
          'fixed', len(fixed), 'source_unchanged', report['source_files_unchanged'], flush=True)
    return 0 if report['status'] == 'passed_within_scope' else 1


if __name__ == '__main__':
    code = main()
    if code:
        raise SystemExit(code)
