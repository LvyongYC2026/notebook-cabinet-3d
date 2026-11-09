"""Independent cosmetic delta for occupied right-hand closed laptops.

Input is the frozen glass-front package; output is a different directory.
Never modifies input, port transforms, Tray/Laptop roots, wire paths or drivers.
Usage: blender -b --python-exit-code 1 -P build_style.py -- --input output/hybrid_glass_candidate
       --output output/hybrid_glass_styled --expected-input manifest.json
"""
import argparse, hashlib, json, math, shutil, sys
from array import array
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

parser=argparse.ArgumentParser()
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--expected-input',type=Path,required=True)
parser.add_argument('--only',choices=['whole','single'])
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
INPUT,OUT=args.input.resolve(),args.output.resolve()
if INPUT==OUT or INPUT in OUT.parents:raise ValueError('Use a separate output directory')
EXPECTED=json.loads(args.expected_input.read_text())
ASSETS=Path(__file__).resolve().parent/'assets'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def descendants(root):return [root,*root.children_recursive]
def under(obj,root):
    while obj:
        if obj==root:return True
        obj=obj.parent
    return False
def authored_world(obj):
    # Hidden variant assemblies may load with unevaluated identity matrix_world
    # caches. Fingerprint authored TRS/parent inverse, not those stale caches.
    return authored_world(obj.parent)@obj.matrix_parent_inverse@obj.matrix_basis if obj.parent else obj.matrix_basis.copy()
def digest(objects):
    h=hashlib.sha256()
    for obj in sorted(objects,key=lambda o:o.name):
        h.update(obj.name.encode());h.update((obj.parent.name if obj.parent else '').encode())
        for matrix in [obj.matrix_basis,obj.matrix_parent_inverse,authored_world(obj)]:h.update(array('f',[v for row in matrix for v in row]).tobytes())
        h.update(json.dumps(dict(obj.items()),sort_keys=True,default=str).encode())
        if obj.type=='MESH':
            h.update(array('f',[v for p in obj.data.vertices for v in p.co]).tobytes())
            h.update(json.dumps([list(p.vertices) for p in obj.data.polygons]).encode())
            h.update('|'.join(m.name if m else '' for m in obj.data.materials).encode())
            if obj.data.shape_keys:
                for key in obj.data.shape_keys.key_blocks:h.update(array('f',[v for p in key.data for v in p.co]).tobytes())
        if obj.animation_data:
            h.update(json.dumps([(d.data_path,d.array_index,d.driver.expression) for d in obj.animation_data.drivers]).encode())
    return h.hexdigest()

def material(name,color,metal=0,rough=.4):
    mat=bpy.data.materials.new('LaptopStyle | '+name);mat.use_nodes=True
    n=mat.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
    mat.diffuse_color=(*color,1);mat.metallic=metal;mat.roughness=rough
    return mat

def texture_material():
    mat=material('Brushed Silver',(0.62,.64,.66),.78,.39)
    nodes=mat.node_tree.nodes;bsdf=nodes.get('Principled BSDF')
    colour=nodes.new('ShaderNodeTexImage');colour.image=bpy.data.images.load(str(ASSETS/'brushed_silver.png'),check_existing=True)
    colour.image.colorspace_settings.name='sRGB';mat.node_tree.links.new(colour.outputs['Color'],bsdf.inputs['Base Color'])
    orm=nodes.new('ShaderNodeTexImage');orm.image=bpy.data.images.load(str(ASSETS/'brushed_orm.png'),check_existing=True)
    orm.image.colorspace_settings.name='Non-Color';channels=nodes.new('ShaderNodeSeparateColor');channels.mode='RGB'
    mat.node_tree.links.new(orm.outputs['Color'],channels.inputs['Color'])
    mat.node_tree.links.new(channels.outputs['Green'],bsdf.inputs['Roughness'])
    mat.node_tree.links.new(channels.outputs['Blue'],bsdf.inputs['Metallic'])
    return mat

def recalc(mesh):
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()

def rounded_mesh(name,width,depth,height,radius,segments=10):
    points=[]
    for cx,cy,start in [(width/2-radius,depth/2-radius,0),(-width/2+radius,depth/2-radius,90),(-width/2+radius,-depth/2+radius,180),(width/2-radius,-depth/2+radius,270)]:
        for i in range(segments+1):
            angle=math.radians(start+i*90/segments);points.append((cx+radius*math.cos(angle),cy+radius*math.sin(angle)))
    n=len(points);verts=[(x,y,z) for z in [-height/2,height/2] for x,y in points]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);recalc(mesh)
    return mesh

def rounded_lower_shell():
    # Establish the large lower perimeter radius BEFORE drilling small ports.
    # Weight only horizontal perimeter edges: lower 2.5 mm, upper 0.4 mm.
    mesh=rounded_mesh('LaptopStyle_DarkLowerShell',.300,.210,.025,.007)
    weights=mesh.attributes.new('bevel_weight_edge','FLOAT','EDGE')
    for edge in mesh.edges:
        zs=[mesh.vertices[i].co.z for i in edge.vertices]
        weights.data[edge.index].value=1.0 if max(zs)<-.0124 else .16 if min(zs)>.0124 else 0
    obj=temp_object(mesh);modifier=obj.modifiers.new('Lower shell rolled perimeter','BEVEL')
    modifier.limit_method='WEIGHT';modifier.width=.0025;modifier.segments=6;modifier.use_clamp_overlap=False
    apply(obj,modifier);mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);recalc(mesh)
    for poly in mesh.polygons:poly.use_smooth=len(poly.vertices)==4
    return mesh

def box_mesh(name,dims):
    x,y,z=[d/2 for d in dims];mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(a*x,b*y,c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]],[],[(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6),(0,1,3,2),(4,6,7,5)])
    recalc(mesh);return mesh

def cylinder_mesh(name,radius,depth,segments=32,axis='X'):
    verts=[]
    for u in [-depth/2,depth/2]:
        for i in range(segments):
            a=i*math.tau/segments;v=(u,radius*math.cos(a),radius*math.sin(a))
            verts.append(v if axis=='X' else (v[1],v[2],v[0]))
    faces=[tuple(reversed(range(segments))),tuple(range(segments,2*segments))]+[(i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);recalc(mesh);return mesh

def temp_object(mesh):
    obj=bpy.data.objects.new('__StyleTemplate',mesh);bpy.context.scene.collection.objects.link(obj);return obj

def apply(obj,modifier):
    bpy.context.view_layer.objects.active=obj;obj.hide_set(False);bpy.ops.object.modifier_apply(modifier=modifier.name)

def bevel_mesh(mesh,width=.0004,segments=3):
    obj=temp_object(mesh);m=obj.modifiers.new('Manufactured edge fillet','BEVEL');m.width=width;m.segments=segments
    apply(obj,m);mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True);recalc(mesh);return mesh

def cut(obj,mesh,location):
    cutter=temp_object(mesh);cutter.location=location
    mod=obj.modifiers.new('Functional aperture','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    apply(obj,mod);bpy.data.objects.remove(cutter,do_unlink=True)

def create_templates(mats):
    base=temp_object(rounded_lower_shell())
    # Base coordinates are relative to its unchanged (.03,-.15,.0125) origin.
    for y,z,w,h in [(-.075,.026,.012,.008),(-.220,.018,.013,.007)]:
        cut(base,box_mesh('__SocketCutter',(.009,w,h)),(-.150,y+.150,z-.0125))
    cut(base,box_mesh('__SpareUSBCutter',(.009,.013,.007)),(.150,-.035,.0015))
    cut(base,cylinder_mesh('__AudioCutter',.0019,.009),(.150,-.005,.0015))
    for y in [-.130,-.120,-.110,-.100,-.090,-.080,-.070]:
        cut(base,box_mesh('__VentCutter',(.007,.0055,.0032)),(.150,y+.150,.0005))
    # Front opening recess under the lid, within the original outer envelope.
    notch=bevel_mesh(box_mesh('__NotchCutter',(.032,.008,.007)),.0014,4)
    cut(base,notch,(0,-.105,.012))
    mod=base.modifiers.new('Shell edge softening','BEVEL');mod.width=.0006;mod.segments=3
    apply(base,mod);base_mesh=base.data;bpy.data.objects.remove(base,do_unlink=True);recalc(base_mesh)
    base_mesh.materials.clear();base_mesh.materials.append(mats['dark'])
    for poly in base_mesh.polygons:poly.material_index=0
    lid_obj=temp_object(rounded_mesh('LaptopStyle_SilverLid',.300,.210,.004,.007))
    cut(lid_obj,box_mesh('__DCSocketLidCutter',(.009,.012,.008)),(-.150,.075,-.002))
    for x in [-.115,.115]:cut(lid_obj,box_mesh('__HingeWindow',(.027,.016,.010)),(x,.105,0))
    lid=lid_obj.data;bpy.data.objects.remove(lid_obj,do_unlink=True);lid=bevel_mesh(lid,.00035,3)
    uv=lid.uv_layers.new(name='BrushedSurfaceUV')
    for poly in lid.polygons:
        for index in poly.loop_indices:
            co=lid.vertices[lid.loops[index].vertex_index].co;uv.data[index].uv=((co.x+.15)/.30,(co.y+.105)/.21)
    lid.materials.clear();lid.materials.append(mats['silver'])
    for poly in lid.polygons:poly.material_index=0
    hinge=bevel_mesh(box_mesh('LaptopStyle_HingeBarrel',(.025,.0074,.0074)),.0008,4)
    for v in hinge.vertices:v.co.y-=.0017;v.co.z+=.0013
    hinge.materials.append(mats['hinge'])
    for poly in hinge.polygons:poly.use_smooth=len(poly.vertices)==4
    return {'base':base_mesh,'lid':lid,'hinge':hinge}

def style_laptop(root,bay,mats,templates,collection,single=False):
    key='single:laptop' if single else 'laptop:'+bay;changed=[];created=[]
    for obj in list(root.children_recursive):
        kind='base' if obj.name.startswith(bay+'_LaptopBase') else 'lid' if obj.name.startswith(bay+'_LaptopClosedLid') else 'hinge' if obj.name.startswith(bay+'_LaptopHinge') else None
        if kind:
            obj.data=templates[kind];obj.modifiers.clear();changed.append(obj.name)
    def detail(name,loc,dims,mat,mesh=None):
        token=(name,tuple(dims),mat.name)
        if token not in DETAIL_POOL:
            geometry=mesh or bevel_mesh(box_mesh('LaptopStyle_'+name,dims),min(.00025,min(dims)*.15),2)
            geometry.materials.clear();geometry.materials.append(mat)
            for poly in geometry.polygons:poly.material_index=0
            DETAIL_POOL[token]=geometry
        obj=bpy.data.objects.new(bay+'_Style_'+name,DETAIL_POOL[token]);collection.objects.link(obj);obj.parent=root;obj.location=loc
        obj['component_key']=key;obj['bay_id']=bay;obj['basis']='model';obj['laptop_style_detail']=name;obj['initial_hidden']=bool(root.get('initial_hidden',False));obj.hide_render=obj['initial_hidden'];obj.hide_set(obj['initial_hidden'])
        created.append(obj);return obj
    # Recessed backings and socket tongues stay inside the dark shell.
    detail('VentInterior',(.1765,-.100,.013),(.0006,.067,.0044),mats['black'])
    detail('SpareUSBBack',(.1763,-.185,.014),(.0006,.012,.006),mats['black'])
    detail('SpareUSBTongue',(.1780,-.185,.0138),(.0038,.008,.0013),mats['black'])
    for y in [-.191,-.179]:detail('SpareUSBSide'+str(y),(.1795,y,.014),(.0007,.0005,.0055),mats['edge'])
    for z in [.0112,.0168]:detail('SpareUSBEdge'+str(z),(.1795,-.185,z),(.0007,.012,.0005),mats['edge'])
    detail('AudioWell',(.1763,-.155,.014),(.0006,.004,.004),mats['black'],cylinder_mesh('LaptopStyle_AudioWell',.0018,.0006))
    # A subtle centre seam at the rear reinforces the two discrete hinges.
    detail('RearHingeRecess',(.030,-.046,.025),(.187,.001,.0025),mats['black'])
    # Engraved underside service screws. No protrusion below the support plane.
    for i,(x,y) in enumerate([(-.100,-.230),(.160,-.230),(-.100,-.066),(.160,-.066)]):
        detail('UndersideScrew'+str(i),(x,y,.0002),(.0035,.0035,.0004),mats['edge'],cylinder_mesh('LaptopStyle_Screw',.00175,.0004,20,'Z'))
    return changed,created

def export_glb(path,root,scene,collection):
    objects=[o for o in scene.objects if under(o,root) and o.type in {'EMPTY','MESH','FONT','CURVE'}]
    states={o:(o.hide_get(),o.hide_viewport,o.hide_render) for o in objects};drivers=[];duplicates=[]
    for obj in objects:
        if obj.get('drawer_front_variant') and obj.animation_data:
            for fc in obj.animation_data.drivers:
                if fc.data_path in {'hide_viewport','hide_render'}:fc.mute=True;drivers.append(fc)
        obj.hide_viewport=False;obj.hide_render=False;obj.hide_set(False)
    bpy.context.view_layer.update()
    for obj in scene.objects:obj.select_set(False)
    graph=bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        if obj.type in {'FONT','CURVE'}:
            mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
            for i,mat in enumerate(mesh.materials):
                if mat:mesh.materials[i]=mat.original
            copy=bpy.data.objects.new(obj.name+'_Mesh',mesh);collection.objects.link(copy);copy.parent=obj.parent;copy.matrix_local=obj.matrix_local.copy()
            for key in obj.keys():copy[key]=obj[key]
            copy.select_set(True);duplicates.append(copy)
        else:obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,use_active_scene=True,export_apply=False,export_animations=False,export_extras=True,export_yup=True,export_cameras=False,export_lights=False,export_morph=True)
    for obj in duplicates:bpy.data.objects.remove(obj,do_unlink=True)
    for obj,(hidden,disabled,render_hidden) in states.items():obj.hide_set(hidden);obj.hide_viewport=disabled;obj.hide_render=render_hidden
    for fc in drivers:fc.mute=False
    scene.frame_set(1);bpy.context.view_layer.update()

report={'status':'built_pending_visual_and_independent_audit','source_manifest_sha256':sha(args.expected_input),'export_note':'Blender glTF exporter may issue a sampler warning because roughness and metallic are two sockets; both read the same prepacked ORM image with identical UV and sampler. Actual GLB embeds one ORM texture.','appearance_parameters_mm':{'nominal_body':[300,210,30],'lower_edge_radius':2.5,'upper_edge_radius':0.4,'lid_plan_corner_radius':7,'hinge_cover':[25,7.4,7.4]},'scenes':[]}
for role,sub,blend_name,glb_name,meta_name in [('whole','', 'smart_cabinet_33bay.blend','smart_cabinet.glb','components.json'),('single','single_drawer','smart_cabinet_drawer.blend','smart_cabinet_drawer.glb','drawer_compartment.json')]:
    if args.only and args.only!=role:continue
    src=INPUT/sub;dst=OUT/sub;dst.mkdir(parents=True,exist_ok=True)
    for name in [blend_name,glb_name,meta_name]:
        rel=str(Path(sub)/name);expected=EXPECTED[rel]['sha256']
        if sha(src/name)!=expected:raise ValueError('Input changed: '+rel)
    bpy.ops.wm.open_mainfile(filepath=str(src/blend_name));scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
    model=bpy.data.objects['CabinetRoot' if role=='whole' else 'SingleDrawerRoot'];metadata=json.loads((src/meta_name).read_text())
    ids=[f'B{i}' for i in range(1,25)] if role=='whole' else ['S1']
    laptops=[bpy.data.objects['Laptop_'+bay if role=='whole' else 'Laptop'] for bay in ids]
    changed=[obj for root in laptops for obj in root.children_recursive if any(obj.name.startswith(root.get('bay_id','S1')+'_'+suffix) for suffix in ['LaptopBase','LaptopClosedLid','LaptopHinge'])]
    # Root bay_id is present in the frozen source; assert the exact narrow scope.
    assert len(changed)==len(laptops)*4,(len(changed),len(laptops))
    originals=[obj for obj in scene.objects if under(obj,model)];unchanged=[obj for obj in originals if obj not in changed]
    preserved_before=digest(unchanged);before_objects={o.name:{'digest':digest([o]),'world':[list(r) for r in o.matrix_world],'local':[list(r) for r in o.matrix_local]} for o in unchanged};source_ports=[obj for root in laptops for obj in root.children_recursive if obj.get('hybrid_role')=='connector'];assert len(source_ports)==len(laptops)*2,(len(source_ports),len(laptops));ports_before=digest(source_ports)
    collection=bpy.data.collections.new('Laptop_Cosmetic_Details');scene.collection.children.link(collection)
    mats={'dark':material('Dark Graphite Lower Shell',(.022,.028,.036),.15,.42),'black':material('Port Interior',(.009,.013,.019),.05,.62),'edge':material('Machined Edge',(.30,.34,.38),.72,.3),'silver':texture_material(),'hinge':material('Hinge Barrel',(.012,.016,.021),.35,.46)}
    DETAIL_POOL={};templates=create_templates(mats);changed_names=[];created=[]
    for bay,root in zip(ids,laptops):
        updated,new=style_laptop(root,bay,mats,templates,collection,role=='single');changed_names+=updated;created+=new
        key='single:laptop' if role=='single' else 'laptop:'+bay
        entry=metadata['components'][key];entry['title']=bay+' 银色拉丝闭盖笔记本';entry['dimensions_mm']=[300,210,30]
        previous=entry.get('notes','');entry['notes']=str(previous)+' 银色拉丝顶盖、深灰圆角下壳、双后铰链与前开盖凹口；侧面备用USB、音频口和散热槽为外观示意。原USB/DC接线位置和取放动作不变；接口与散热能力仍需实机选型验证。'
    bpy.context.view_layer.update()
    assert preserved_before==digest(unchanged),'Unrelated source object changed'
    assert ports_before==digest(source_ports),'Existing laptop USB/DC ports changed'
    bounds=[]
    for bay,root in zip(ids,laptops):
        inverse=authored_world(root).inverted();points=[inverse@authored_world(obj)@v.co for obj in root.children_recursive if obj.type=='MESH' and (obj in created or obj.name in changed_names) for v in obj.data.vertices]
        lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
        assert all(lo[i]>=(-.120,-.255,0)[i]-1e-6 and hi[i]<=(.180,-.045,.030)[i]+1e-6 for i in range(3)),(bay,lo,hi)
        bounds.append({'bay_id':bay,'styled_geometry_bounds_m':[lo,hi]})
    metadata['laptop_appearance']={'status':'model_styling','styled_bays':ids,'empty_bays_remain_hidden':[bay for bay in ids if bool(bpy.data.objects['Laptop_'+bay if role=='whole' else 'Laptop'].get('initial_hidden',False))],'nominal_dimensions_mm':[300,210,30],'changes':'Silver brushed lid, dark rounded lower shell, twin hinges, finger recess and side details. Existing Laptop/Tray roots and USB/DC ports are unchanged.','source_blend_sha256':sha(src/blend_name),'source_metadata_sha256':sha(src/meta_name),'appearance_only':True}
    export_glb(dst/glb_name,model,scene,collection)
    if preserved_before!=digest(unchanged):
        delta=[{'name':o.name,'before':before_objects[o.name],'after':{'digest':digest([o]),'world':[list(r) for r in o.matrix_world],'local':[list(r) for r in o.matrix_local]}} for o in unchanged if before_objects[o.name]['digest']!=digest([o])]
        (dst/'export_delta_debug.json').write_text(json.dumps(delta,indent=2)+'\n')
        raise AssertionError('Export altered unrelated original objects: '+str([d['name'] for d in delta]))
    (dst/meta_name).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    # New textures are embedded and also available at portable relative paths.
    texture_dir=dst/'textures';texture_dir.mkdir(exist_ok=True)
    for filename in ['brushed_silver.png','brushed_orm.png']:
        shutil.copy2(ASSETS/filename,texture_dir/filename)
        image=bpy.data.images.get(filename)
        if image:image.pack();image.filepath='//textures/'+filename
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(dst/blend_name),compress=True)
    report['scenes'].append({'role':role,'styled_laptops':ids,'replaced_original_meshes':changed_names,'new_objects':len(created),'new_object_prefix':'<bay>_Style_','new_object_names':[o.name for o in created],'existing_port_nodes':[o.name for o in source_ports],'preserved_original_objects':len(unchanged),'preserved_original_sha256':preserved_before,'existing_port_fingerprint_sha256':ports_before,'existing_ports_preserved':True,'bounds':bounds,'files':{name:{'bytes':(dst/name).stat().st_size,'sha256':sha(dst/name)} for name in [blend_name,glb_name,meta_name]}})
    (dst/'export_delta_debug.json').unlink(missing_ok=True)
    print('LAPTOP_STYLE_EXPORTED',role,flush=True)
(OUT/('build_report_'+args.only+'.json' if args.only else 'build_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
