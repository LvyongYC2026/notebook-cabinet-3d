"""Independent GLB/metadata audit of the 33-bay release. Python 3.9+, stdlib only.

Example:
  python3 scripts/audit_hybrid_assets.py \
    --pair cabinet full.glb components.json --pair drawer drawer.glb drawer.json \
    --pair door single.glb single.json --pair room room.glb room.json \
    --cabinet-blend full.blend --output independent_assets_audit.json

Reads exported bytes, not builder helpers. Does not alter any input. Partial
candidate runs may provide fewer pairs; the report explicitly lists their scope.
This is a graph/export/endpoint audit, not a collision, load or thermal audit.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import re
import struct

IDENTITY = [[float(i == j) for j in range(4)] for i in range(4)]
EXPECTED_BAYS = {f'A{i}' for i in range(1, 10)} | {f'B{i}' for i in range(1, 25)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def inverse(a):
    rows = [a[i][:] + IDENTITY[i][:] for i in range(4)]
    for c in range(4):
        p = max(range(c, 4), key=lambda i: abs(rows[i][c]))
        if abs(rows[p][c]) < 1e-12:
            raise ValueError('Singular node transform')
        rows[c], rows[p] = rows[p], rows[c]
        scale = rows[c][c]
        rows[c] = [v / scale for v in rows[c]]
        for r in range(4):
            if r != c:
                s = rows[r][c]
                rows[r] = [x - s * y for x, y in zip(rows[r], rows[c])]
    return [r[4:] for r in rows]


def transform(m, v, direction=False):
    p = list(v) + [0.0 if direction else 1.0]
    return tuple(sum(m[i][j] * p[j] for j in range(4)) for i in range(3))


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def point(p):
    return isinstance(p, (list, tuple)) and len(p) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)


def canonical(name):
    return re.sub(r'_Mesh$', '', re.sub(r'[.\[\]/:]', '', name))


class Checks:
    def __init__(self):
        self.counts = collections.Counter()
        self.errors = []

    def check(self, valid, code, detail=None):
        self.counts[code] += 1
        if not valid:
            self.errors.append({'check': code, 'detail': detail})
        return bool(valid)


class GLB:
    def __init__(self, path, checks):
        self.path, self.c = Path(path), checks
        raw = self.path.read_bytes()
        if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
            raise ValueError('Invalid GLB header/length/version')
        checks.check(len(raw) < 25 * 1024 * 1024, 'browser_upload_size', len(raw))
        chunks, offset = [], 12
        while offset < len(raw):
            n, kind = struct.unpack_from('<II', raw, offset)
            offset += 8
            if offset + n > len(raw) or n % 4:
                raise ValueError('Invalid GLB chunk bounds/alignment')
            chunks.append((kind, raw[offset:offset + n])); offset += n
        if not chunks or chunks[0][0] != 0x4e4f534a:
            raise ValueError('Missing initial JSON chunk')
        self.g = json.loads(chunks[0][1])
        bins = [b for k, b in chunks if k == 0x004e4942]
        self.binary = bins[0] if len(bins) == 1 else b''
        self.nodes = self.g.get('nodes', [])
        self.names = collections.defaultdict(list)
        self.normalized = collections.defaultdict(list)
        self.parents, self.world_cache, self.accessor_cache = {}, {}, {}
        for i, node in enumerate(self.nodes):
            self.names[node.get('name', '')].append(i)
            self.normalized[canonical(node.get('name', ''))].append(i)
            for child in node.get('children', []):
                if child in self.parents or not 0 <= child < len(self.nodes):
                    raise ValueError('Invalid child index or multiple node parents')
                self.parents[child] = i
        checks.check(bool(self.nodes), 'nonzero_nodes')
        checks.check(self.g.get('asset', {}).get('version') == '2.0', 'gltf_version')
        checks.check(len(self.g.get('buffers', [])) == 1 and len(bins) == 1, 'embedded_single_buffer')
        for b in self.g.get('buffers', []):
            checks.check('uri' not in b and b['byteLength'] <= len(self.binary), 'buffer_bounds')
        for v in self.g.get('bufferViews', []):
            checks.check(v.get('buffer', 0) == 0 and v.get('byteOffset', 0) + v['byteLength'] <= len(self.binary), 'buffer_view_bounds')
        checks.check(not self.g.get('cameras'), 'no_exported_cameras')
        checks.check(not self.g.get('extensions', {}).get('KHR_lights_punctual', {}).get('lights'), 'no_exported_lights')
        checks.check(all('uri' not in image for image in self.g.get('images', [])), 'embedded_images')
        scene = self.g.get('scenes', [])[self.g.get('scene', 0)]
        reached = set()
        for i in scene.get('nodes', []):
            reached.update(self.descendants(i))
        outside = sorted(set(range(len(self.nodes))) - reached)
        checks.check(not outside, 'all_nodes_reachable', {'outside_active_scene_count': len(outside), 'sample_node_names': [self.nodes[i].get('name', str(i)) for i in outside[:20]]})

    def resolve(self, name):
        ids = self.names.get(name, []) or self.normalized.get(canonical(name), [])
        self.c.check(len(ids) == 1, 'metadata_node_resolves_uniquely', name)
        return ids[0] if len(ids) == 1 else None

    def descendants(self, start):
        pending, result = [start], set()
        while pending:
            i = pending.pop()
            if i in result:
                raise ValueError('Cycle or repeated descendant in scene tree')
            result.add(i); pending.extend(self.nodes[i].get('children', []))
        return result

    def under(self, child, ancestor):
        while child is not None:
            if child == ancestor:
                return True
            child = self.parents.get(child)
        return False

    def local(self, i):
        n = self.nodes[i]
        if 'matrix' in n:
            return [n['matrix'][j::4] for j in range(4)]
        x, y, z, w = n.get('rotation', [0, 0, 0, 1])
        r = [[1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w, 0],
             [2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w, 0],
             [2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y, 0], [0, 0, 0, 1]]
        s = n.get('scale', [1, 1, 1]); t = n.get('translation', [0, 0, 0])
        for a in range(3):
            for b in range(3): r[a][b] *= s[b]
            r[a][3] = t[a]
        return r

    def world(self, i, visiting=None):
        if i in self.world_cache: return self.world_cache[i]
        visiting = set() if visiting is None else visiting
        if i in visiting: raise ValueError('Transform hierarchy cycle')
        visiting.add(i); m = self.local(i)
        if i in self.parents: m = mul(self.world(self.parents[i], visiting), m)
        if not all(math.isfinite(v) for row in m for v in row): raise ValueError('Non-finite transform')
        self.world_cache[i] = m
        return m

    def accessor(self, i):
        if i in self.accessor_cache: return self.accessor_cache[i]
        a = self.g['accessors'][i]
        formats = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
        dims = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
        if a['type'] not in dims: raise ValueError('Unsupported non-vector inspected accessor')
        f = '<' + formats[a['componentType']] * dims[a['type']]; size = struct.calcsize(f)
        def read(view_index, offset, count, fmt, stride=None):
            view = self.g['bufferViews'][view_index]; element_size = struct.calcsize(fmt)
            stride = stride or view.get('byteStride', element_size)
            if stride < element_size or offset < 0 or (count and offset + (count-1)*stride + element_size > view['byteLength']):
                raise ValueError('Accessor extends outside bufferView')
            start = view.get('byteOffset', 0) + offset
            return [struct.unpack_from(fmt, self.binary, start+j*stride) for j in range(count)]
        values = read(a['bufferView'], a.get('byteOffset', 0), a['count'], f) if 'bufferView' in a else [(0,) * dims[a['type']]] * a['count']
        if 'sparse' in a:
            sp = a['sparse']; ix = sp['indices']; val = sp['values']
            indices = read(ix['bufferView'], ix.get('byteOffset', 0), sp['count'], '<' + formats[ix['componentType']])
            replacements = read(val['bufferView'], val.get('byteOffset', 0), sp['count'], f, size)
            for (j,), replacement in zip(indices, replacements):
                if not 0 <= j < len(values): raise ValueError('Sparse accessor index out of range')
                values[j] = replacement
        self.accessor_cache[i] = values
        return values

    def mesh_nodes(self, root):
        return [i for i in self.descendants(root) if 'mesh' in self.nodes[i]]

    def cloud(self, node, parent, target=None, extended=False, tray=None, travel=.32):
        points = []; relative = inverse(self.world(parent))
        for i in self.mesh_nodes(node):
            mesh = self.g['meshes'][self.nodes[i]['mesh']]
            names = mesh.get('extras', {}).get('targetNames', [])
            target_index = names.index(target) if target in names else None
            m = mul(relative, self.world(i)); shift = (0, 0, 0)
            if extended and tray is not None and self.under(i, tray):
                shift = transform(mul(relative, self.world(self.parents[tray])), (0, 0, travel), True)
            for prim in mesh['primitives']:
                base = self.accessor(prim['attributes']['POSITION']); delta = None
                if extended and target_index is not None:
                    delta = self.accessor(prim['targets'][target_index]['POSITION'])
                for j, v in enumerate(base):
                    vv = tuple(v[k] + (delta[j][k] if delta else 0) for k in range(3))
                    p = transform(m, vv); points.append(tuple(p[k] + shift[k] for k in range(3)))
        return points

    def geometry(self):
        primitives = vertices = 0
        for mi, mesh in enumerate(self.g.get('meshes', [])):
            self.c.check(bool(mesh.get('primitives')), 'nonzero_mesh_primitives', mi)
            targets = mesh.get('extras', {}).get('targetNames', [])
            self.c.check(len(targets) == len(set(targets)), 'unique_morph_names', mi)
            for p in mesh.get('primitives', []):
                primitives += 1; positions = self.accessor(p['attributes']['POSITION']); vertices += len(positions)
                self.c.check(bool(positions) and all(point(v) for v in positions), 'finite_nonzero_position_accessor', mi)
                if 'indices' in p:
                    indices = self.accessor(p['indices'])
                    self.c.check(bool(indices) and all(0 <= v[0] < len(positions) for v in indices), 'valid_mesh_indices', mi)
                if p.get('targets'):
                    self.c.check(len(targets) == len(p['targets']), 'morph_names_match_primitive', mi)
                for target in p.get('targets', []):
                    ds = self.accessor(target['POSITION'])
                    self.c.check(len(ds) == len(positions) and all(point(v) for v in ds), 'morph_topology_and_finite', mi)
            self.c.check(all(abs(v) < 1e-7 for v in mesh.get('weights', [])), 'closed_mesh_morph_weights', mi)
        for i, n in enumerate(self.nodes):
            self.c.check(all(abs(v) < 1e-7 for v in n.get('weights', [])), 'closed_node_morph_weights', n.get('name', i))
        self.c.check(primitives > 0 and vertices > 0, 'nonzero_geometry')
        return {'unique_meshes': len(self.g.get('meshes', [])), 'primitives': primitives, 'vertices_in_unique_primitives': vertices}


def check_references(g, obj, path='metadata'):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = path + '.' + k
            if isinstance(v, str) and (k.endswith('_node') or k in {'root_node', 'node_name'}):
                g.resolve(v)
            elif isinstance(v, list) and (k.endswith('_node_names') or k == 'cutaway_node_names'):
                for name in v: g.resolve(name)
            elif k == 'real_apertures' and isinstance(v, list):
                for entry in v:
                    if entry.get('object'):
                        node = g.resolve(entry['object'])
                        if node is not None: g.c.check(bool(g.mesh_nodes(node)), 'aperture_has_nonempty_exported_structure', entry['object'])
            else: check_references(g, v, p)
    elif isinstance(obj, list):
        for v in obj: check_references(g, v, path)


def audit_cables(g, meta, ids):
    c = g.c; paths = meta.get('cable_paths', [])
    c.check(len(paths) >= len(ids), 'nonzero_cable_coverage', {'paths': len(paths), 'bays': len(ids)})
    seen, networks, active, endpoint_checks = set(), set(), 0, 0
    network_counts = collections.Counter()
    for p in paths:
        name = p.get('id'); bay = p.get('bay_id', 'S1')
        c.check(name and name not in seen, 'unique_cable_id', name); seen.add(name)
        c.check(bay in ids, 'cable_bay_exists', {'cable': name, 'bay': bay})
        network = 'network' in str(name).lower() or p.get('connection_mode') == 'tray_usb_nic'
        if network:
            network_counts[bay] += 1
            networks.add(bay); c.check(p.get('keep_connected_when_empty') is True, 'empty_network_stays_connected', name)
        expected_tray = 'SingleTray' if ids == {'S1'} else 'Tray_' + str(bay)
        expected_parents = {'SingleCabinetRoot','SingleDrawerRoot'} if ids == {'S1'} else {'Bay_' + str(bay)}
        c.check(p.get('tray_node') == expected_tray and p.get('parent_node') in expected_parents, 'cable_assigned_to_own_bay_frame', name)
        parent = g.resolve(p.get('parent_node', '')); tray = g.resolve(p.get('tray_node', ''))
        source = [g.resolve(n) for n in p.get('source_node_names', [])]
        c.check(bool(source) and all(i is not None for i in source), 'cable_has_source_geometry', name)
        if parent is None or tray is None or not source or None in source: continue
        c.check(g.under(tray, parent), 'tray_under_cable_frame', name)
        c.check(all(g.under(s, parent) for s in source), 'cable_geometry_under_own_bay', name)
        closed, opened = p.get('guide_points', []), p.get('guide_points_extended', [])
        c.check(len(closed) >= 2 and all(point(v) for v in closed), 'valid_closed_cable_path', name)
        if len(closed) < 2 or not all(point(v) for v in closed): continue
        c.check(point(p.get('fixed')), 'valid_fixed_endpoint', name)
        if point(p.get('fixed')): c.check(distance(closed[0], p['fixed']) < .001, 'fixed_path_endpoint', name)
        stowed = p.get('stowed') is True or p.get('motion') == 'stowed'
        if stowed:
            c.check(not network, 'network_not_stowed', name); continue
        active += 1; target = p.get('morph_target')
        travel = p.get('travel_mm', 320) / 1000
        c.check(abs(travel - .32) < 1e-6, 'tray_travel_320mm', name)
        valid = len(opened) == len(closed) and all(point(v) for v in opened)
        c.check(valid, 'controlled_extended_path_topology', name)
        if not valid: continue
        c.check(distance(closed[0], opened[0]) < .001, 'fixed_endpoint_stationary', name)
        delta = [opened[-1][k] - closed[-1][k] for k in range(3)]
        c.check(distance(delta, [0, 0, travel]) < .001, 'moving_endpoint_yup_axis', {'cable': name, 'delta': delta})
        c.check(point(p.get('moving')) and distance(closed[-1], p['moving']) < .002, 'moving_metadata_matches_path', name)
        targets_found = 0
        for source_id in source:
            for i in g.mesh_nodes(source_id):
                mesh = g.g['meshes'][g.nodes[i]['mesh']]; names = mesh.get('extras', {}).get('targetNames', [])
                if c.check(target in names, 'native_morph_target_exists', {'cable': name, 'node': g.nodes[i].get('name'), 'target': target}):
                    targets_found += 1
        c.check(targets_found > 0, 'nonzero_morph_targets', name)
        if not targets_found: continue
        tolerance = p.get('radius_mm', 2.5) / 1000 + .002
        for extended, guides in [(False, closed), (True, opened)]:
            cloud = [v for sid in source for v in g.cloud(sid, parent, target, extended, tray, travel)]
            c.check(bool(cloud), 'nonzero_cable_vertices', name)
            if not cloud: continue
            for endpoint in [guides[0], guides[-1]]:
                nearest = min(distance(v, endpoint) for v in cloud)
                c.check(nearest <= tolerance, 'exported_morph_endpoint_matches_metadata', {'cable': name, 'extended': extended, 'distance_mm': round(nearest*1000, 4), 'tolerance_mm': round(tolerance*1000, 4)})
                endpoint_checks += 1
    c.check(networks == ids, 'one_network_path_per_bay_coverage', {'missing': sorted(ids-networks), 'unexpected': sorted(networks-ids)})
    c.check(all(network_counts[bay] == 1 for bay in ids), 'exactly_one_network_path_each', dict(network_counts))
    c.check(active > 0 and endpoint_checks > 0, 'nonzero_motion_endpoint_checks')
    usb = meta.get('usb_connections', [])
    c.check({p.get('bay_id', 'S1') for p in usb} == ids and len(usb) == len(ids), 'usb_connection_coverage')
    for p in usb:
        bay = p.get('bay_id', 'S1')
        c.check(p.get('tray_node') == ('SingleTray' if ids == {'S1'} else 'Tray_' + str(bay)), 'usb_connection_on_own_bay_tray', bay)
        nic = g.resolve(p.get('nic_node', '')); tray = g.resolve(p.get('tray_node', ''))
        if nic is not None and tray is not None: c.check(g.under(nic, tray), 'nic_moves_with_own_tray', p.get('bay_id'))
        c.check(bool(p.get('parked_node_names')), 'usb_parking_geometry_declared', p.get('bay_id'))
    return {'cable_paths': len(paths), 'active_morph_paths': active, 'endpoint_geometry_checks': endpoint_checks, 'usb_connections': len(usb)}


def audit_pair(role, glb, metadata, cabinet_blend=None):
    checks = Checks(); g = GLB(glb, checks); meta = json.loads(Path(metadata).read_text()); stats = g.geometry()
    expected_root = {'cabinet':'CabinetRoot','room':'RoomEnvironmentRoot','door':'SingleCabinetRoot','drawer':'SingleDrawerRoot'}[role]
    root = g.resolve(expected_root)
    checks.check(root is not None and len(g.names.get(expected_root, [])) == 1, 'one_expected_asset_root', expected_root)
    checks.check(not any(re.match(r'^(Studio_|Camera_)', n) for n in g.names), 'no_studio_nodes')
    if root is not None:
        m = g.world(root); scales = [math.sqrt(sum(m[i][j]**2 for i in range(3))) for j in range(3)]
        checks.check(all(abs(v-1) < 1e-5 for v in scales), 'root_unit_scale', scales)
        checks.check(all(abs(m[i][3]) < 1e-5 for i in range(3)), 'asset_local_root_origin')
        lo, hi = [math.inf]*3, [-math.inf]*3
        for i in g.mesh_nodes(root):
            m = g.world(i)
            for p in g.g['meshes'][g.nodes[i]['mesh']]['primitives']:
                a = g.g['accessors'][p['attributes']['POSITION']]
                values = g.accessor(p['attributes']['POSITION'])
                low = [min(v[k] for v in values) for k in range(3)]; high = [max(v[k] for v in values) for k in range(3)]
                checks.check(all(abs(low[k]-a.get('min', low)[k]) < 1e-5 and abs(high[k]-a.get('max', high)[k]) < 1e-5 for k in range(3)), 'accessor_bounds_match_bytes', i)
                for x in [low[0], high[0]]:
                    for y in [low[1], high[1]]:
                        for z in [low[2], high[2]]:
                            v = transform(m, (x, y, z))
                            lo = [min(lo[k], v[k]) for k in range(3)]; hi = [max(hi[k], v[k]) for k in range(3)]
        dimensions = [hi[k]-lo[k] for k in range(3)]; stats['gltf_yup_geometry_bounds_m'] = {'min': lo, 'max': hi, 'dimensions': dimensions}
        ranges = {'cabinet': [(3.2,3.5),(1.8,1.95),(.6,.9)], 'door': [(.4,.5),(.4,.55),(.6,.85)], 'drawer': [(.35,.5),(.12,.23),(.6,.85)], 'room': [(5.2,5.5),(2.8,3.0),(3.1,3.4)]}[role]
        checks.check(all(a <= v <= b for (a,b),v in zip(ranges,dimensions)), 'metres_yup_role_dimensions', {'role': role, 'dimensions': dimensions})
    check_references(g, meta)
    if role == 'cabinet':
        bays = {n[4:] for n in g.names if re.fullmatch(r'Bay_[AB]\d+', n)}
        trays = {n[5:] for n in g.names if re.fullmatch(r'Tray_[AB]\d+', n)}
        doors = {n[10:] for n in g.names if re.fullmatch(r'DoorPivot_[AB]\d+', n)}
        checks.check(bays == EXPECTED_BAYS, 'exact_33_bay_inventory', sorted(bays))
        checks.check(trays == EXPECTED_BAYS, 'exact_33_tray_inventory', sorted(trays))
        checks.check(doors == {f'A{i}' for i in range(1,10)}, 'only_9_A_hinged_doors', sorted(doors))
        checks.check(len(meta.get('bay_ids', [])) == 33 and set(meta.get('bay_ids', [])) == EXPECTED_BAYS, 'metadata_exact_33_bay_ids')
        components = meta.get('components', {})
        drawer_grid = set()
        for bay in EXPECTED_BAYS:
            bi, ti = g.resolve('Bay_'+bay), g.resolve('Tray_'+bay)
            if bi is not None and ti is not None: checks.check(g.under(ti,bi), 'tray_under_correct_bay', bay)
            info = components.get('bay:'+bay, {})
            checks.check(bool(info), 'metadata_has_bay', bay)
            if bay.startswith('B'):
                checks.check(info.get('access_type') == 'drawer', 'B_access_is_drawer', bay)
                drawer_grid.add((info.get('row'), info.get('column')))
                support = info.get('support_height_mm')
                checks.check(isinstance(support, (int, float)) and 375 <= support <= 1505, 'B_support_height_declared', bay)
        # Accept zero- or one-based indexing, but never duplicated/missing cells.
        grids = [{(r,c) for r in range(start_r,start_r+8) for c in range(start_c,start_c+3)} for start_r in (0,1) for start_c in (0,1)]
        checks.check(drawer_grid in grids, 'B_unique_3_column_8_row_grid', sorted(drawer_grid, key=str))
        ports = meta.get('switch_port_plan', [])
        checks.check(len(ports) == 48 and {p.get('port') for p in ports} == set(range(1,49)), 'complete_unique_48_port_map')
        mapped = [p.get('endpoint') for p in ports if p.get('role') == 'bay_data']
        checks.check(len(mapped) == 33 and set(mapped) == EXPECTED_BAYS, '33_unique_bay_network_ports')
        checks.check({p.get('endpoint') for p in ports if p.get('role') == 'device_or_management'} == {'server','lock_controller','pdu','ups','external_management'}, 'five_management_ports_retained')
        checks.check(sum(p.get('role') == 'spare' for p in ports) == 10, 'ten_spare_ports')
        physical_ports={n for n in g.names if re.fullmatch(r'HybridSwitch_Port_\d{2}',n)}
        checks.check(physical_ports=={f'HybridSwitch_Port_{i:02d}'for i in range(1,49)}, '48_physical_switch_port_nodes')
        checks.check({p.get('port_node')for p in ports}==physical_ports, 'switch_map_binds_physical_ports')
        if len(physical_ports)==48:
            locations=[tuple(round(g.world(g.names[n][0])[i][3],5)for i in range(3))for n in physical_ports]
            xs={p[0]for p in locations};ys={p[1]for p in locations};zs={p[2]for p in locations}
            checks.check(len(xs)==24 and len(ys)==2 and len(zs)==1 and len(set(locations))==48, 'physical_switch_2_rows_24_columns', {'columns':len(xs),'rows':len(ys),'planes':len(zs)})
        outlets={n for n in g.names if re.fullmatch(r'HybridPDU_Outlet_\d{2}',n)}
        power=meta.get('power_branch_plan',[])
        checks.check(outlets=={f'HybridPDU_Outlet_{i:02d}'for i in range(1,34)}, '33_physical_power_outlets')
        checks.check(len(power)==33 and {p.get('bay_id')for p in power}==EXPECTED_BAYS and {p.get('port_node')for p in power}==outlets, '33_unique_bay_power_bindings')
        for prefix in ['LockOutput','DoorStateInput','LockStateInput']:
            actual={n for n in g.names if re.fullmatch('HybridControl_'+prefix+r'_\d{2}',n)}
            checks.check(actual=={f'HybridControl_{prefix}_{i:02d}'for i in range(1,34)}, '33_control_nodes_'+prefix)
        stats.update({'bays': len(bays), 'trays': len(trays), 'A_doors': len(doors), 'switch_ports': len(ports)})
        stats.update({'physical_switch_ports':len(physical_ports),'physical_power_outlets':len(outlets),'control_terminal_groups':3})
        stats.update(audit_cables(g,meta,EXPECTED_BAYS))
    elif role in {'drawer','door'}:
        tray = g.resolve('SingleTray'); checks.check(tray is not None, 'one_single_tray')
        checks.check(not any(re.fullmatch(r'(Bay|Tray)_[AB]\d+', n) for n in g.names), 'single_asset_not_full_cabinet')
        checks.check(('SingleDoorPivot' in g.names) == (role == 'door'), 'single_access_type_matches_role', role)
        checks.check(not any(n.startswith('DoorPivot_B') for n in g.names), 'single_drawer_has_no_B_pivot')
        stats.update(audit_cables(g,meta,{'S1'}))
    else:
        checks.check(meta.get('coordinate_space') == 'cabinet_local_gltf', 'room_coordinate_contract')
        checks.check(meta.get('units') == 'metres', 'room_metadata_units')
        checks.check(not any(n in {'CabinetRoot','SingleCabinetRoot','SingleDrawerRoot'} or re.match(r'^(Bay_|Tray_|DoorPivot_|DynamicCable_)',n) for n in g.names), 'environment_has_no_duplicate_product')
        checks.check(meta.get('rear_maintenance_available') is False, 'room_rear_maintenance_locked')
        if cabinet_blend: checks.check(meta.get('cabinet_source_sha256') == digest(cabinet_blend), 'room_bound_to_current_cabinet_blend')
    if role != 'room': checks.check(meta.get('unit') == 'mm', 'metadata_millimetres')
    glass = []
    for i,n in enumerate(g.nodes):
        # Match the actual viewing panes, not steel glass-retainer screws or
        # opaque decorative camera lenses that happen to include 'Glass'.
        name = n.get('name', '')
        is_pane = (role == 'cabinet' and re.fullmatch(r'Glass_[AB]\d+', name)) or (role == 'door' and name == 'Door_ClearGlass')
        if 'mesh' not in n or not is_pane: continue
        for p in g.g['meshes'][n['mesh']]['primitives']:
            mat = g.g.get('materials',[])[p['material']]
            alpha = mat.get('pbrMetallicRoughness',{}).get('baseColorFactor',[1,1,1,1])[3]
            transmission = mat.get('extensions',{}).get('KHR_materials_transmission',{}).get('transmissionFactor',0)
            valid = transmission > .1 or (mat.get('alphaMode') == 'BLEND' and alpha < .9)
            checks.check(valid, 'glass_material_transmits', {'node': n.get('name'), 'material': mat.get('name'), 'alpha': alpha, 'transmission': transmission})
            glass.append(n.get('name'))
    if role in {'cabinet','door'}: checks.check(len(glass) == (9 if role == 'cabinet' else 1), 'expected_glass_material_coverage', len(glass))
    stats['glass_mesh_primitives_checked'] = len(glass)
    return {'role':role,'glb':Path(glb).name,'metadata':Path(metadata).name,'glb_sha256':digest(glb),'metadata_sha256':digest(metadata),'glb_bytes':Path(glb).stat().st_size,'statistics':stats,'check_counts':dict(checks.counts),'errors':checks.errors,'passed':not checks.errors}


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--pair',nargs=3,action='append',metavar=('ROLE','GLB','METADATA'),required=True)
    p.add_argument('--cabinet-blend');p.add_argument('--output',required=True)
    args=p.parse_args();results=[];seen=set()
    for role,glb,meta in args.pair:
        if role not in {'cabinet','door','drawer','room'} or role in seen: p.error('Unique roles: cabinet, door, drawer, room')
        seen.add(role)
        try:results.append(audit_pair(role,glb,meta,args.cabinet_blend))
        except Exception as error:results.append({'role':role,'passed':False,'errors':[{'check':'read_or_structure_failure','detail':str(error)}]})
    hashes=[r['glb_sha256'] for r in results if 'glb_sha256' in r]
    duplicates=len(hashes)!=len(set(hashes))
    report={'status':'passed_within_scope' if all(r['passed'] for r in results) and not duplicates else 'review_required','roles_checked':sorted(seen),'complete_four_asset_release':seen=={'cabinet','door','drawer','room'},'different_roles_reuse_identical_glb':duplicates,'assets':results,'limits':'Decoded GLB hierarchy, binary attributes, role/metadata binding, material and native cable endpoint checks. No scene rendering, full-solid collision, continuous motion, minimum bend radius, stability, load, electrical or thermal certification.'}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'roles':sorted(seen),'errors':sum(len(r['errors']) for r in results),'complete_four_asset_release':report['complete_four_asset_release']},ensure_ascii=False))
    return 0 if report['status']=='passed_within_scope' else 1


if __name__=='__main__':raise SystemExit(main())
