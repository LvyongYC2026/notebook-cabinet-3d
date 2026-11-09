#!/usr/bin/env python3
"""Read-only GLB cosmetic delta check against the frozen glass-front candidate.

Only each right laptop's base/lid/two hinges may replace geometry. Every original
parent, transform, connector, cable, variant and other object stays unchanged.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import sys
from audit_hybrid_assets import GLB, Checks
from audit_hybrid_glass_assets import fingerprints, sha


def audit(role, baseline, candidate):
    glb_name = 'smart_cabinet.glb' if role == 'cabinet' else 'smart_cabinet_drawer.glb'
    meta_name = 'components.json' if role == 'cabinet' else 'drawer_compartment.json'
    before_path, after_path = baseline/glb_name, candidate/glb_name
    old_meta_path, meta_path = baseline/meta_name, candidate/meta_name
    initial_hashes = {str(p): sha(p) for p in (before_path, after_path, old_meta_path, meta_path)}
    c=Checks(); old=GLB(before_path,Checks());g=GLB(after_path,c);stats=g.geometry()
    before,after=fingerprints(old),fingerprints(g)
    original=json.loads(old_meta_path.read_text());meta=json.loads(meta_path.read_text())
    ids=[f'B{i}' for i in range(1,25)] if role=='cabinet' else ['S1']
    roots={bay:('Laptop_'+bay if role=='cabinet' else 'Laptop') for bay in ids}
    allowed={bay+suffix for bay in ids for suffix in ('_LaptopBase','_LaptopClosedLid','_LaptopHinge','_LaptopHinge.001')}
    c.check(allowed<=before.keys(),'all_exact_replaceable_nodes_exist')
    changed=[];unexpected=[]
    for name,fp in before.items():
        if name not in after:unexpected.append({'node':name,'differences':['missing']});continue
        fields=[k for k in fp if fp[k]!=after[name][k]]
        if not fields:continue
        if name not in allowed or fields!=['mesh']:unexpected.append({'node':name,'differences':fields})
        else:changed.append(name)
    c.check(not unexpected,'only_exact_laptop_meshes_changed',unexpected)
    extras_deltas=[name for name in before if name in after and old.nodes[old.names[name][0]].get('extras',{}) != g.nodes[g.names[name][0]].get('extras',{})]
    c.check(not extras_deltas,'all_original_node_extras_preserved',extras_deltas)
    c.check(set(changed)==allowed,'every_expected_cosmetic_mesh_replaced',sorted(allowed-set(changed)))
    added=sorted(set(after)-set(before));c.check(bool(added),'style_details_present')
    c.check(all(re.fullmatch(r'(?:B(?:[1-9]|1[0-9]|2[0-4])|S1)_Style_[A-Za-z0-9_.-]+',name) for name in added),'new_node_name_scope',added)
    details_by_bay=collections.defaultdict(list);bounds=[];ports=[]
    for name in added:
        bay=name.split('_',1)[0];root_name=roots.get(bay);i=g.resolve(name);ri=g.resolve(root_name) if root_name else None
        if i is None or ri is None:continue
        node=g.nodes[i];old_root=old.nodes[old.resolve(root_name)];extras=node.get('extras',{})
        c.check(g.parents.get(i)==ri,'new_style_direct_laptop_child',name)
        c.check(extras.get('bay_id')==bay and extras.get('component_key')==('laptop:'+bay if role=='cabinet' else 'single:laptop'),'own_laptop_component_binding',name)
        c.check('initial_hidden' in extras and bool(extras['initial_hidden'])==bool(old_root.get('extras',{}).get('initial_hidden',False)),'empty_bay_detail_visibility_contract',name)
        c.check(not extras.get('drawer_front_variant'),'style_outside_front_variant_contract',name)
        details_by_bay[bay].append(i)
    c.check(set(details_by_bay)==set(ids),'all_laptops_have_style_details')
    for bay,root_name in roots.items():
        ri=g.resolve(root_name)
        if ri is None:continue
        nodes=details_by_bay[bay]+[g.resolve(name) for name in allowed if name.startswith(bay+'_')]
        points=[v for i in nodes if i is not None for v in g.cloud(i,ri)]
        lo=[min(v[k] for v in points) for k in range(3)] if points else []
        hi=[max(v[k] for v in points) for k in range(3)] if points else []
        c.check(bool(points) and all(lo[k]>=[-.120,0,.045][k]-1e-6 and hi[k]<=[.180,.030,.255][k]+1e-6 for k in range(3)),'all_cosmetic_geometry_inside_30x21x3cm_envelope',{'bay':bay,'gltf_yup_min':lo,'gltf_yup_max':hi})
        bounds.append({'bay_id':bay,'gltf_yup_min_m':lo,'gltf_yup_max_m':hi,'new_detail_nodes':len(details_by_bay[bay])})
        lid = g.nodes[g.resolve(bay+'_LaptopClosedLid')]
        for primitive in g.g['meshes'][lid['mesh']]['primitives']:
            material = g.g.get('materials',[])[primitive['material']];pbr=material.get('pbrMetallicRoughness',{})
            c.check(material.get('name','').startswith('LaptopStyle | Brushed Silver'),'brushed_silver_lid_material',bay)
            c.check('TEXCOORD_0' in primitive['attributes'],'brushed_lid_uv_present',bay)
            for key in ('baseColorTexture','metallicRoughnessTexture'):
                index=pbr.get(key,{}).get('index')
                c.check(isinstance(index,int) and 0<=index<len(g.g.get('textures',[])),'brushed_lid_texture_binding',{'bay':bay,'texture':key})
        for suffix in ('_LaptopDCIn','_LaptopUSBIn'):
            name=bay+suffix;c.check(name in before and after.get(name)==before.get(name),'original_connected_port_exactly_preserved',name);ports.append(name)
    # Restore only explicitly allowed laptop component prose for a full metadata diff.
    normalized=json.loads(json.dumps(meta));normalized.pop('laptop_appearance',None)
    for bay in ids:
        key='laptop:'+bay if role=='cabinet' else 'single:laptop'
        c.check(key in meta.get('components',{}),'laptop_metadata_exists',key)
        c.check(meta.get('components',{}).get(key,{}).get('dimensions_mm')==[300,210,30],'nominal_laptop_envelope_metadata',key)
        normalized.setdefault('components',{})[key]=original['components'][key]
    c.check(normalized==original,'all_noncosmetic_metadata_exactly_preserved')
    appearance=meta.get('laptop_appearance',{})
    c.check(appearance.get('styled_bays')==ids and appearance.get('appearance_only') is True,'appearance_scope_contract')
    c.check(appearance.get('source_metadata_sha256')==sha(old_meta_path),'appearance_source_metadata_binding')
    image_details=[]
    for i,image in enumerate(g.g.get('images',[])):
        c.check('uri' not in image and 'bufferView' in image,'embedded_texture_image',i)
        if 'bufferView' in image:
            v=g.g['bufferViews'][image['bufferView']];start=v.get('byteOffset',0);data=g.binary[start:start+v['byteLength']]
            c.check(bool(data) and (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')),'valid_nonempty_image_payload',i)
            image_details.append({'index':i,'bytes':len(data),'mime_type':image.get('mimeType')})
    for i,tex in enumerate(g.g.get('textures',[])):
        c.check(isinstance(tex.get('source'),int) and 0<=tex['source']<len(g.g.get('images',[])),'texture_source_resolves',i)
    c.check(len(image_details)>=2,'brushed_color_and_roughness_textures_embedded')
    c.check(all(sha(p)==value for p,value in initial_hashes.items()),'inputs_stable_during_audit')
    return {'role':role,'baseline_glb_sha256':initial_hashes[str(before_path)],'glb_sha256':initial_hashes[str(after_path)],
            'baseline_metadata_sha256':initial_hashes[str(old_meta_path)],'metadata_sha256':initial_hashes[str(meta_path)],
            'statistics':stats,'original_nodes_compared':len(before),'exact_mesh_replacements':sorted(changed),'unexpected_deltas':unexpected,
            'added_nodes':len(added),'original_connected_ports_preserved':ports,'cosmetic_bounds':bounds,'embedded_images':image_details,
            'check_counts':dict(c.counts),'errors':c.errors,'passed':not c.errors}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,default=Path('output/hybrid_glass_styled'));p.add_argument('--output',type=Path,default=Path('tmp/hybrid-glass-audit/laptop_style_assets.json'));args=p.parse_args()
    rows=[audit('cabinet',args.baseline,args.candidate),audit('drawer',args.baseline/'single_drawer',args.candidate/'single_drawer')]
    report={'status':'passed_within_scope' if all(x['passed'] for x in rows) else 'failed','assets':rows,
            'limits':'Decoded exported geometry/metadata/texture and exact cosmetic delta. Empty-bay visibility is an extras contract, not a live browser check. No continuous collision, physical laptop fit, cooling or electrical certification.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'roles':[{k:r[k] for k in ('role','passed','original_nodes_compared','added_nodes')} for r in rows],
                      'errors':[{'role':r['role'],'counts':dict(collections.Counter(e['check'] for e in r['errors'])),'first':r['errors'][:3]} for r in rows if r['errors']]},ensure_ascii=False,indent=2))
    return int(report['status']=='failed')

if __name__=='__main__':sys.exit(main())
