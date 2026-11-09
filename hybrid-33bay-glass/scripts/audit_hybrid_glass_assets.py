#!/usr/bin/env python3
"""Read-only decoded-GLB delta audit against the published 33-bay release.

This checks exported geometry and variant contracts, not live Three.js visibility,
continuous collisions, hardware selection, glass strength or safety certification.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sys

from audit_hybrid_assets import GLB, Checks, mul, inverse, transform


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fingerprints(g):
    """Resolve indices before hashing; new accessor/mesh ordering is immaterial."""
    accessors, meshes = {}, {}
    def acc(i):
        if i not in accessors:
            a = g.g['accessors'][i]
            accessors[i] = digest({'componentType': a['componentType'], 'type': a['type'],
                                   'normalized': a.get('normalized', False), 'values': g.accessor(i)})
        return accessors[i]
    def mesh(i):
        if i not in meshes:
            m = g.g['meshes'][i]
            prims = []
            for p in m['primitives']:
                prims.append({'mode': p.get('mode', 4),
                              'attributes': {k: acc(v) for k, v in p['attributes'].items()},
                              'indices': acc(p['indices']) if 'indices' in p else None,
                              'targets': [{k: acc(v) for k, v in t.items()} for t in p.get('targets', [])],
                              'material': g.g['materials'][p['material']] if 'material' in p else None})
            meshes[i] = digest({'primitives': prims, 'weights': m.get('weights', []),
                                'targetNames': m.get('extras', {}).get('targetNames', [])})
        return meshes[i]
    return {n.get('name', ''): {'parent': g.nodes[g.parents[i]].get('name') if i in g.parents else None,
                               'local_transform': g.local(i), 'mesh': mesh(n['mesh']) if 'mesh' in n else None,
                               'weights': n.get('weights', [])}
            for i, n in enumerate(g.nodes)}


def audit_pair(role, glb, meta_path, old_glb, old_meta, glass_material):
    c = Checks(); g = GLB(glb, c); old = GLB(old_glb, Checks())
    meta = json.loads(Path(meta_path).read_text()); previous = json.loads(Path(old_meta).read_text())
    stats = g.geometry()
    c.check(all(len(v) == 1 for v in g.names.values()), 'unique_node_names')
    before, after = fingerprints(old), fingerprints(g)
    deltas = []
    for name, fp in before.items():
        if name not in after: deltas.append({'node': name, 'differences': ['missing']})
        elif fp != after[name]: deltas.append({'node': name, 'differences': [k for k in fp if fp[k] != after[name][k]]})
    c.check(not deltas, 'all_published_nodes_geometry_material_transform_morph_preserved', deltas)
    additions = sorted(set(after) - set(before))
    shared_declared = set()
    for assembly in meta.get('drawer_front_variants', {}).get('assemblies', []):
        for name in assembly.get('shared_attachment_node_names', []):
            i = g.resolve(name)
            if i is not None: shared_declared.update(g.nodes[j]['name'] for j in g.descendants(i))
    c.check(bool(additions), 'new_glass_geometry_present')
    c.check(all(re.match(r'^(DrawerGlassFront_|GlassFront_)', n) or (n in shared_declared and re.match(r'^DrawerFrontAttachment_(?:B(?:[1-9]|1[0-9]|2[0-4])|S1)(?:_|$)', n)) for n in additions), 'only_declared_glass_and_shared_attachment_nodes_added', additions)
    preserved_meta = []
    for key in ('bay_ids', 'empty_bays', 'cabinet_dimensions_mm', 'dimensions_mm', 'cable_paths',
                'cable_system', 'usb_connections', 'switch_port_plan', 'power_branch_plan',
                'control_channel_budget', 'control_power_topology', 'rear_doors'):
        if key in previous:
            c.check(meta.get(key) == previous[key], 'published_metadata_preserved', key);preserved_meta.append(key)
    contract = meta.get('drawer_front_variants', {})
    c.check(contract.get('default') == 'glass', 'default_glass')
    c.check({x.get('id') for x in contract.get('options', [])} == {'glass', 'metal'}, 'exact_two_front_options')
    ids = [f'B{i}' for i in range(1, 25)] if role == 'cabinet' else ['S1']
    assemblies = contract.get('assemblies', [])
    c.check(collections.Counter(x.get('bay_id') for x in assemblies) == collections.Counter(ids), 'exact_variant_assembly_coverage')
    c.check(len(meta.get('bay_ids', [])) == (33 if role == 'cabinet' else 1), 'capacity_unchanged')
    panes = []; claimed = set()
    for a in assemblies:
        bay = a.get('bay_id'); tray_name = 'Tray_' + bay if role == 'cabinet' else 'SingleTray'
        c.check(a.get('tray_node') == tray_name, 'own_tray_binding', a)
        ti = g.resolve(tray_name)
        groups = {}
        for variant in ('metal', 'glass'):
            names = a.get(variant + '_node_names', [])
            root_name = ('DrawerFront_' if variant == 'metal' else 'DrawerGlassFront_') + bay
            ri = g.resolve(root_name); ni = [g.resolve(n) for n in names]
            c.check(bool(names) and len(names) == len(set(names)), 'nonempty_unique_variant_binding', {'bay': bay, 'variant': variant})
            c.check(root_name in names, 'variant_root_bound', {'bay': bay, 'variant': variant})
            if ri is None or ti is None or any(i is None for i in ni): continue
            c.check(g.parents.get(ri) == ti, 'front_root_direct_tray_child', root_name)
            descendants = g.descendants(ri); actual_names = {g.nodes[i]['name'] for i in descendants}
            # A bound root controls its complete subtree; leaf names need not be repeated.
            resolved_closure = set().union(*(g.descendants(i) for i in ni))
            c.check(resolved_closure == descendants, 'complete_variant_subtree_binding', {'root': root_name, 'extra_bound_nodes': sorted(set(names)-actual_names)})
            c.check(not (claimed & actual_names), 'no_cross_bay_or_variant_shared_nodes', root_name)
            claimed.update(actual_names); groups[variant] = actual_names
            for i in descendants:
                n = g.nodes[i]; e = n.get('extras', {})
                c.check(e.get('drawer_front_variant') == variant, 'variant_extras_match', n['name'])
                c.check(all(k in e for k in ('variant_default_visible', 'initial_hidden')) and
                        bool(e.get('variant_default_visible')) == (variant == 'glass') and
                        bool(e.get('initial_hidden')) == (variant == 'metal'), 'default_visibility_contract', n['name'])
                c.check(g.under(i, ti), 'all_front_parts_follow_own_tray', n['name'])
        c.check(not (groups.get('glass', set()) & groups.get('metal', set())), 'mutually_exclusive_node_sets', bay)
        shared = set()
        for name in a.get('shared_attachment_node_names', []):
            i = g.resolve(name)
            if i is not None: shared.update(g.descendants(i))
        for i in shared:
            node = g.nodes[i]; extras = node.get('extras', {})
            c.check((node['name'] == f'DrawerFrontAttachment_{bay}' or node['name'].startswith(f'DrawerFrontAttachment_{bay}_')), 'shared_attachment_own_bay_name', node['name'])
            c.check(ti is not None and g.under(i, ti), 'shared_attachment_follows_own_tray', node['name'])
            c.check(not extras.get('drawer_front_variant') and not extras.get('initial_hidden'), 'shared_attachment_visible_in_both_variants', node['name'])
            c.check(node['name'] not in claimed, 'shared_attachment_outside_variant_subtrees', node['name'])
        pane_name = f'GlassFront_{bay}_GlassPane'; pi = g.resolve(pane_name)
        if pi is not None and ti is not None:
            node = g.nodes[pi]
            c.check('mesh' in node, 'physical_glass_mesh', pane_name)
            if 'mesh' in node:
                materials = [g.g['materials'][p['material']] for p in g.g['meshes'][node['mesh']]['primitives']]
                c.check(bool(materials) and all(m == glass_material for m in materials), 'same_glass_material_as_left_A1', pane_name)
                xyz = g.cloud(pi, ti); dims = [max(p[k] for p in xyz)-min(p[k] for p in xyz) for k in range(3)] if xyz else []
                c.check(len(dims) == 3 and all(abs(a-b) < 0.00002 for a,b in zip(dims, [.418,.106,.006])), 'glass_physical_size_metres_y_up', {'node':pane_name,'dimensions':dims})
                panes.append({'node':pane_name,'dimensions_m':dims})
        handles = [n for n in groups.get('glass', []) if n.startswith(f'GlassFront_{bay}_HandleCup') or n == f'GlassFront_{bay}_HandleGrip']
        c.check(any('HandleCup' in n for n in handles) and any('HandleGrip' in n for n in handles), 'recessed_handle_parts_present', bay)
    return {'role':role,'glb':Path(glb).name,'metadata':Path(meta_path).name,'glb_sha256':sha(glb),
            'metadata_sha256':sha(meta_path),'baseline_glb_sha256':sha(old_glb),'baseline_metadata_sha256':sha(old_meta),
            'statistics':stats,'published_nodes_compared':len(before),'published_node_deltas':deltas,
            'added_nodes':len(additions),'shared_attachment_nodes':len(shared_declared),'preserved_metadata_sections':preserved_meta,'glass_panes':panes,
            'check_counts':dict(c.counts),'errors':c.errors,'passed':not c.errors}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate',type=Path,default=Path('output/hybrid_glass_candidate'))
    ap.add_argument('--baseline',type=Path,default=Path('tmp/hybrid-glass-audit/baseline'))
    ap.add_argument('--output',type=Path,default=Path('tmp/hybrid-glass-audit/assets.json'))
    args=ap.parse_args();bg=GLB(args.baseline/'smart_cabinet.glb',Checks());ai=bg.resolve('Glass_A1')
    glass=bg.g['materials'][bg.g['meshes'][bg.nodes[ai]['mesh']]['primitives'][0]['material']]
    results=[]
    for role,sub,glb,meta in [('cabinet','', 'smart_cabinet.glb','components.json'),('drawer','single_drawer','smart_cabinet_drawer.glb','drawer_compartment.json')]:
        results.append(audit_pair(role,args.candidate/sub/glb,args.candidate/sub/meta,args.baseline/glb,args.baseline/meta,glass))
    report={'status':'passed_within_scope' if all(r['passed'] for r in results) else 'failed',
            'source_commit':'41035f03eb458b92dbde771714ab69f25013c9c5','assets':results,
            'limits':'Decoded GLB and metadata checks. Default visibility is an extras contract: live Three.js mutual visibility must be verified separately. No continuous collision, grip ergonomics, glass strength or electrical/thermal certification.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'roles':[{k:r[k] for k in ('role','passed','published_nodes_compared','added_nodes')} for r in results], 'errors':[{'role':r['role'],'counts':dict(collections.Counter(e['check'] for e in r['errors'])),'first':r['errors'][:3]} for r in results if r['errors']]},ensure_ascii=False,indent=2))
    return 0 if report['status']=='passed_within_scope' else 1

if __name__=='__main__':sys.exit(main())
