"""Read-only fingerprints for left/central modules and original A fixed feeds.

Capture from the immutable released 18-bay blend:
  blender -b source.blend -P scripts/audit_hybrid_preservation.py -- \
    --capture-out baseline.json
Compare the hybrid candidate; explicitly allow only reviewed changes:
  blender -b candidate.blend -P scripts/audit_hybrid_preservation.py -- \
    --baseline baseline.json --allow-change '^Equipment_Switch_48Port$' --output audit.json

An allow rule is visible in the report, never silently dropped from the audit.
Names, local and cabinet-relative transforms, topology, UVs, shape keys, drivers,
material shaders, modifiers and key interaction attributes are fingerprinted.
The loaded blend is never saved. Blender's in-memory frame is set to frame 1.
"""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy


def digest_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def simple(value):
    if value is None or isinstance(value, (bool, str, int)): return value
    if isinstance(value, float): return round(value, 8)
    if hasattr(value, 'name_full'): return {'data_name': value.name_full}
    try: return [simple(v) for v in value]
    except TypeError: return str(type(value).__name__)


def RNA_props(value, skip=()):
    result = {}
    for prop in value.bl_rna.properties:
        name = prop.identifier
        if name in {'rna_type'} | set(skip) or prop.type == 'COLLECTION': continue
        try: result[name] = simple(getattr(value, name))
        except (AttributeError, RuntimeError, TypeError): continue
    return result


def animation(value):
    ad = getattr(value, 'animation_data', None)
    if not ad: return None
    result = {'action': ad.action.name if ad.action else None, 'drivers': []}
    for fc in ad.drivers:
        d = fc.driver
        variables = []
        for v in d.variables:
            variables.append({'name': v.name, 'type': v.type, 'targets': [RNA_props(t, {'id'}) | {'id': t.id.name if t.id else None} for t in v.targets]})
        result['drivers'].append({'data_path':fc.data_path,'array_index':fc.array_index,'type':d.type,'expression':d.expression,'variables':variables})
    return result


def field_bytes(collection, name, width, code):
    values = array(code, [0]) * (len(collection) * width)
    collection.foreach_get(name, values)
    return values.tobytes()


def mesh_fingerprint(mesh):
    h = hashlib.sha256()
    h.update(field_bytes(mesh.vertices, 'co', 3, 'f'))
    h.update(field_bytes(mesh.edges, 'vertices', 2, 'i'))
    h.update(field_bytes(mesh.loops, 'vertex_index', 1, 'i'))
    h.update(field_bytes(mesh.polygons, 'loop_total', 1, 'i'))
    h.update(field_bytes(mesh.polygons, 'material_index', 1, 'i'))
    h.update(field_bytes(mesh.polygons, 'use_smooth', 1, 'b'))
    for layer in mesh.uv_layers:
        h.update(layer.name.encode()); h.update(field_bytes(layer.data, 'uv', 2, 'f'))
    shape_keys = []
    if mesh.shape_keys:
        for key in mesh.shape_keys.key_blocks:
            kh = hashlib.sha256(field_bytes(key.data, 'co', 3, 'f')).hexdigest()
            shape_keys.append({'name':key.name,'relative_key':key.relative_key.name,'sha256':kh,'slider_min':key.slider_min,'slider_max':key.slider_max})
    return {'sha256':h.hexdigest(),'vertices':len(mesh.vertices),'edges':len(mesh.edges),'faces':len(mesh.polygons),'uv_layers':len(mesh.uv_layers),'shape_keys':shape_keys,'shape_key_drivers':animation(mesh.shape_keys) if mesh.shape_keys else None}


def material_fingerprint(material):
    if material is None: return None
    data = {'use_nodes':material.use_nodes,'diffuse_color':simple(material.diffuse_color),'roughness':simple(material.roughness),'metallic':simple(material.metallic)}
    for key in ['surface_render_method','blend_method','use_backface_culling','use_transparency_overlap']:
        if hasattr(material,key): data[key] = simple(getattr(material,key))
    if material.use_nodes and material.node_tree:
        nodes = []
        for node in material.node_tree.nodes:
            item = {'name':node.name,'type':node.bl_idname,'mute':node.mute,'inputs':[]}
            for i,socket in enumerate(node.inputs):
                if hasattr(socket,'default_value'): item['inputs'].append([i,socket.identifier,simple(socket.default_value)])
            if hasattr(node,'image') and node.image:
                image = node.image
                item['image'] = {'name':image.name,'size':list(image.size),'source':image.source,'packed_sha256':hashlib.sha256(image.packed_file.data).hexdigest() if image.packed_file else None}
            for key in ['operation','blend_type','interpolation','extension','projection','distribution']:
                if hasattr(node,key): item[key] = simple(getattr(node,key))
            nodes.append(item)
        data['nodes'] = sorted(nodes,key=lambda n:n['name'])
        data['links'] = sorted([[l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier] for l in material.node_tree.links])
    return digest_json(data)


def descendants(obj):
    result = {obj}
    for child in obj.children: result |= descendants(child)
    return result


def object_fingerprint(obj, cabinet):
    relative = cabinet.matrix_world.inverted() @ obj.matrix_world
    data = {'type':obj.type,'parent':obj.parent.name if obj.parent else None,
            'basis':simple([v for row in obj.matrix_basis for v in row]),
            'parent_inverse':simple([v for row in obj.matrix_parent_inverse for v in row]),
            'cabinet_relative_transform':simple([v for row in relative for v in row]),
            'materials':[material_fingerprint(slot.material) for slot in obj.material_slots],
            'modifiers':[RNA_props(mod) for mod in obj.modifiers],
            'constraints':[RNA_props(con) for con in obj.constraints],
            'object_animation':animation(obj),
            'interaction_properties':{k:simple(obj[k]) for k in ['component_key','bay_id','interaction','initial_hidden','dynamicCable','stowed','motion','travel_mm','swing_degrees','support_height_mm'] if k in obj}}
    if obj.type == 'MESH': data['geometry'] = mesh_fingerprint(obj.data)
    elif obj.type == 'FONT':
        data['text_geometry'] = {k:simple(getattr(obj.data,k)) for k in ['body','size','extrude','bevel_depth','align_x','align_y','space_character','space_word','space_line']}
    elif obj.type == 'CURVE':
        splines=[]
        for spline in obj.data.splines:
            splines.append({'type':spline.type,'cyclic':spline.use_cyclic_u,'points':[simple(p.co) for p in spline.points],'bezier_points':[[simple(p.co),simple(p.handle_left),simple(p.handle_right)] for p in spline.bezier_points]})
        data['curve_geometry']={'splines':splines,'bevel_depth':obj.data.bevel_depth,'bevel_resolution':obj.data.bevel_resolution,'resolution_u':obj.data.resolution_u}
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--capture-out');parser.add_argument('--baseline');parser.add_argument('--output')
    parser.add_argument('--allow-change',action='append',default=[],help='Fullmatch regex for explicitly reviewed object changes/additions/removals')
    parser.add_argument('--allow-list',help='JSON list of reviewed exact object names; never treats entries as patterns')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if bool(args.capture_out)==bool(args.baseline): parser.error('Choose --capture-out or --baseline')
    if args.baseline and not args.output: parser.error('--output required for comparison')
    scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
    cabinet=bpy.data.objects.get('CabinetRoot')
    roots=[bpy.data.objects.get('Module_Left'),bpy.data.objects.get('Module_Center')]
    if cabinet is None or any(o is None for o in roots): raise RuntimeError('CabinetRoot, Module_Left and Module_Center are mandatory')
    selected=set().union(*(descendants(o) for o in roots))
    # Original A fixed feeds can be parented directly under CabinetRoot rather
    # than Module_Left. Include them explicitly so a hierarchy convenience
    # cannot hide an unintended left-side cable change.
    external_a_roots=[o for o in scene.objects if o.name.startswith(('FixedNetwork_A','FixedAC_A'))]
    for o in external_a_roots: selected.update(descendants(o))
    names={o.name for o in selected}
    if not {f'Bay_A{i}' for i in range(1,10)} <= names: raise RuntimeError('Preservation scope missed one or more A bays')
    if len(descendants(roots[1]))<10: raise RuntimeError('Central preservation scope unexpectedly empty')
    source=Path(bpy.data.filepath)
    fingerprints={o.name:object_fingerprint(o,cabinet) for o in sorted(selected,key=lambda o:o.name)}
    record={'schema':'hybrid-preservation-v1','source_blend_name':source.name,'source_blend_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope_roots':[o.name for o in roots]+sorted(o.name for o in external_a_roots),'objects':fingerprints,'object_count':len(fingerprints),'limits':'Raw editable geometry, transforms, shader settings and driver fingerprints at frame 1. Does not certify collision, tolerances, thermal or electrical performance. External unpacked texture pixels are not read.'}
    if args.capture_out:
        Path(args.capture_out).parent.mkdir(parents=True,exist_ok=True);Path(args.capture_out).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        print('PRESERVATION_CAPTURE',len(fingerprints),record['source_blend_sha256']);return 0
    baseline=json.loads(Path(args.baseline).read_text())
    if baseline.get('schema')!='hybrid-preservation-v1' or not baseline.get('objects'): raise RuntimeError('Invalid/empty preservation baseline')
    exact=json.loads(Path(args.allow_list).read_text())if args.allow_list else[]
    if not isinstance(exact,list)or not all(isinstance(n,str)and n for n in exact):raise ValueError('Allow list must contain exact object names')
    differences=[]
    for name in sorted(set(baseline['objects'])|set(fingerprints)):
        old=baseline['objects'].get(name);new=fingerprints.get(name)
        if old==new:continue
        fields=['added'] if old is None else ['missing'] if new is None else sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k))
        matched=[rule for rule in args.allow_change if re.fullmatch(rule,name)]
        if name in exact:matched.append('exact:'+name)
        differences.append({'object':name,'fields':fields,'allowed_rules':matched})
    unexpected=[d for d in differences if not d['allowed_rules']]
    report={'status':'passed_preserved_scope' if not unexpected else 'review_required','baseline_blend_sha256':baseline['source_blend_sha256'],'candidate_blend_sha256':record['source_blend_sha256'],'baseline_objects':len(baseline['objects']),'candidate_scope_objects':len(fingerprints),'unchanged_objects':sum(fingerprints.get(n)==v for n,v in baseline['objects'].items()),'scope_roots':record['scope_roots'],'explicit_allow_rules':args.allow_change,'explicit_allowed_object_names':exact,'allowed_changes':[d for d in differences if d['allowed_rules']],'unexpected_changes':unexpected,'limits':record['limits']}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PRESERVATION_AUDIT',report['status'],'unexpected',len(unexpected),'allowed',len(report['allowed_changes']),'unchanged',report['unchanged_objects'])
    return 0 if not unexpected else 1


if __name__=='__main__':
    result=main()
    if result:raise SystemExit(result)
