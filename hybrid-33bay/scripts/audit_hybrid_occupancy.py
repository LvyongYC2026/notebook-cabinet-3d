"""Read-only reverse-occupancy spot check, independent of builder/motion code.

blender -b candidate.blend -P scripts/audit_hybrid_occupancy.py -- \
  --metadata components.json --output reverse_occupancy_audit.json

B1 is made empty/parked and B2 occupied/connected in memory, then sampled at
0/80/160/240/320 mm. Checks individual evaluated meshes and declared endpoints.
No blend is saved. Full 24-drawer/mixed/continuous-motion coverage is not claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def under(o, parent):
    while o:
        if o == parent: return True
        o = o.parent
    return False


def active(o):
    while o:
        if o.get('initial_hidden'): return False
        o = o.parent
    return True


def set_hidden(root, hidden):
    for o in [root, *root.children_recursive]:
        o['initial_hidden'] = hidden
        o.hide_set(False)  # Visibility decision is explicit above, not viewport state.
        o.hide_render = hidden


def shape(o):
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = e.to_mesh()
    if mesh is None: return None
    vertices = [e.matrix_world @ v.co for v in mesh.vertices]
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    e.to_mesh_clear()
    if not vertices or not polygons: return None
    return {'min': Vector([min(v[i] for v in vertices) for i in range(3)]),
            'max': Vector([max(v[i] for v in vertices) for i in range(3)]),
            'tree': BVHTree.FromPolygons(vertices, polygons),
            'vertices': vertices}


def overlap(a, b):
    if not a or not b or any(a['max'][i] < b['min'][i]-1e-7 or b['max'][i] < a['min'][i]-1e-7 for i in range(3)): return False
    return bool(a['tree'].overlap(b['tree']))


def gltf_point(p):
    return Vector((p[0], -p[2], p[1]))


def endpoint_distance(p, sh):
    nearest = sh['tree'].find_nearest(p)
    # The end point may intentionally lie inside a solid connector.
    inside_bounds = all(sh['min'][i]-1e-6 <= p[i] <= sh['max'][i]+1e-6 for i in range(3))
    return float(nearest[3]) if nearest[0] is not None else float('inf'), inside_bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--metadata', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    metadata_path = Path(args.metadata); meta = json.loads(metadata_path.read_text())
    root = bpy.data.objects.get('CabinetRoot')
    if root is None: raise RuntimeError('CabinetRoot required')
    scene = bpy.context.scene; scene.frame_set(1)
    source_sha = hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
    selected = {'B1': False, 'B2': True}
    trays = {bay: bpy.data.objects['Tray_'+bay] for bay in selected}
    old_states = {}
    for bay, occupied in selected.items():
        old_states[bay] = bool(bpy.data.objects['Bay_'+bay].get('occupied'))
        objects = {
            'Laptop_'+bay: not occupied,
            'DynamicCable_'+bay+'_power': not occupied,
            bay+'_DCMovingPlug': not occupied,
            'DCParked_'+bay: occupied,
            'USBConnected_'+bay: not occupied,
            'USBParked_'+bay: occupied,
        }
        for name, hidden in objects.items():
            if name not in bpy.data.objects: raise RuntimeError('Required state object missing: '+name)
            set_hidden(bpy.data.objects[name], hidden)
        trays[bay].animation_data_clear(); trays[bay].location.y = 0
    bpy.context.view_layer.update()
    objects = [o for o in scene.objects if under(o, root) and active(o) and o.type in {'MESH','CURVE','FONT'}]
    movable = {bay: [o for o in objects if under(o, tray) and o.get('hybrid_role') not in {'slide_moving','fastener'}] for bay,tray in trays.items()}
    dynamic = {bay: [o for o in objects if o.get('hybrid_role') == 'cable_dynamic' and o.get('bay_id') == bay] for bay in selected}
    moving_set = {o for parts in movable.values() for o in parts}
    dynamic_set = {o for parts in dynamic.values() for o in parts}
    fixed = [o for o in objects if o not in moving_set and o not in dynamic_set and not any(under(o,t) for t in trays.values()) and o.get('hybrid_role') not in {'fastener','slide_fixed'}]
    fixed_shapes = {o.name: shape(o) for o in fixed}
    allowed = set()
    for bay in selected:
        for pair in [('DynamicCable_'+bay+'_network','FixedNetworkFeed_'+bay),
                     ('DynamicCable_'+bay+'_network',bay+'_NICNetworkPlug'),
                     ('DynamicCable_'+bay+'_power','FixedAdapterDC_'+bay),
                     ('DynamicCable_'+bay+'_power',bay+'_DCMovingPlug')]: allowed.add(frozenset(pair))
    report = {'source_blend_sha256': source_sha, 'metadata_sha256': hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
              'original_occupancy': old_states, 'tested_occupancy': selected,
              'fixed_mesh_count':len(fixed), 'moving_mesh_counts':{b:len(v)for b,v in movable.items()},
              'dynamic_cable_counts':{b:len(v)for b,v in dynamic.items()},
              'exact_endpoint_pair_exemptions':[sorted(p)for p in sorted(allowed,key=lambda p:sorted(p))],
              'poses':[], 'limits':'Reverse occupancy of B1/B2 only, five discrete poses; evaluated surface intersections, explicit endpoint checks. Does not certify continuous motion, tolerances or all occupied/empty combinations. Ordinary attached fasteners and sliding rail engagements are outside this spot check. No scene file saved.'}
    for travel in [0,80,160,240,320]:
        for tray in trays.values(): tray.location.y = -travel/1000
        bpy.context.view_layer.update()
        cache = dict(fixed_shapes)
        for o in moving_set | dynamic_set: cache[o.name] = shape(o)
        hits = set(); endpoint_contacts = set()
        def test(a,b):
            if a.name == b.name or not overlap(cache.get(a.name),cache.get(b.name)): return
            pair = frozenset((a.name,b.name))
            (endpoint_contacts if pair in allowed else hits).add(tuple(sorted(pair)))
        for parts in movable.values():
            for o in parts:
                for f in fixed: test(o,f)
        for bay,parts in dynamic.items():
            for cable in parts:
                for f in fixed: test(cable,f)
                for o in moving_set: test(cable,o)
        # Two neighbouring trays have different occupancy but share the sample
        # travel. Their individual mesh sets still remain separate in the test.
        for a in movable['B1']:
            for b in movable['B2']: test(a,b)
        checks = []
        for bay,occupied in selected.items():
            bay_node = bpy.data.objects['Bay_'+bay];tray=trays[bay]
            usb = next(p for p in meta['usb_connections'] if p['bay_id']==bay)
            usb_points = usb['connected_guide_points' if occupied else 'parked_guide_points']
            endpoints = [(tray.matrix_world@gltf_point(usb_points[0]),bay+'_NICUSBEntry','USB NIC endpoint'),
                         (tray.matrix_world@gltf_point(usb_points[-1]),bay+('_USBConnectedPlug' if occupied else '_USBParkedPlug'),'USB plug endpoint')]
            for cable in [p for p in meta['cable_paths'] if p['bay_id']==bay]:
                power=cable['id'].endswith('_power')
                if power and not occupied:
                    end=cable['parking_guide_points'][-1];target=bay+'_ParkingDCPlug'
                else:
                    end=cable['guide_points'][-1][:];end[2]+=travel/1000
                    target=bay+('_DCMovingPlug' if power else '_NICNetworkPlug')
                endpoints.append((bay_node.matrix_world@gltf_point(end),target,'DC/network endpoint'))
            for p,name,kind in endpoints:
                sh=cache.get(name) or shape(bpy.data.objects[name]);dist,inside=endpoint_distance(p,sh)
                checks.append({'kind':kind,'target':name,'distance_to_surface_mm':round(dist*1000,6),'within_target_bounds':inside,'passed':inside or dist<=.00025})
        pose={'travel_mm':travel,'intersections':[list(p)for p in sorted(hits)],'intentional_endpoint_contacts':[list(p)for p in sorted(endpoint_contacts)],'endpoint_checks':checks}
        report['poses'].append(pose)
        print('REVERSE_OCCUPANCY',travel,'intersections',len(hits),'endpoint_failures',sum(not x['passed']for x in checks),flush=True)
    report['coverage_pass']=old_states=={'B1':True,'B2':False} and all(movable.values()) and all(dynamic.values()) and bool(fixed)
    report['intersection_count']=sum(len(p['intersections'])for p in report['poses'])
    report['endpoint_check_count']=sum(len(p['endpoint_checks'])for p in report['poses'])
    report['endpoint_failure_count']=sum(not c['passed']for p in report['poses']for c in p['endpoint_checks'])
    report['status']='passed_within_scope' if report['coverage_pass'] and not report['intersection_count'] and not report['endpoint_failure_count'] else 'review_required'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('REVERSE_OCCUPANCY_AUDIT',report['status'],flush=True)
    return 0 if report['status']=='passed_within_scope' else 1


if __name__=='__main__':
    result=main()
    if result: raise SystemExit(result)
