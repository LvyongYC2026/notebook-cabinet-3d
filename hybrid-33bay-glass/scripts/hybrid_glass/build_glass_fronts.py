"""Incrementally add mutually exclusive glass drawer fronts to the frozen 33-bay model.

Run in Blender 5.2.3. Existing mechanics, cables, materials and transforms are
not rebuilt. A standalone drawer receives exactly the same front construction.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import PARAMETERS
from geometry import Builder

ROOT = HERE.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base-blend', type=Path, default=ROOT/'output/hybrid_release/smart_cabinet_33bay.blend')
parser.add_argument('--base-metadata', type=Path, default=ROOT/'output/hybrid_candidate/components.json')
parser.add_argument('--single-blend', type=Path, default=ROOT/'output/hybrid_release/smart_cabinet_drawer.blend')
parser.add_argument('--single-metadata', type=Path, default=ROOT/'output/hybrid_candidate/single_drawer/drawer_compartment.json')
parser.add_argument('--output', type=Path, default=ROOT/'output/hybrid_glass_candidate')
parser.add_argument('--config', type=Path)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
P = PARAMETERS.copy()
if args.config:
    override = json.loads(args.config.read_text())
    if set(override)-set(P):
        raise ValueError('Unknown front parameter: '+str(sorted(set(override)-set(P))))
    P.update(override)
if P['default_variant'] not in {'glass', 'metal'}:
    raise ValueError('default_variant must be glass or metal')
if [P[k] for k in ['front_width_mm','front_height_mm','front_depth_mm','bottom_z_mm']] != [444,154,16,-28]:
    raise ValueError('The existing drawer envelope must remain 444×154×16 mm, with bottom Z=-28 mm')
if P['glass_thickness_mm'] != 6 or P['sheet_thickness_mm'] != 2:
    raise ValueError('This design uses the existing 6 mm glass and 2 mm front sheet assumptions')
if P['glass_center_y_mm'] != -319 or P['glass_edge_capture_mm'] != 2 or P['handle_aperture_mm'] != [112,24] or P['handle_center_z_mm'] != 108:
    raise ValueError('Glazing depth/capture and the recessed handle are fixed to the reviewed assembly; change the source construction before changing those values')
if not (12 <= P['side_frame_width_mm'] <= 20 and 14 <= P['bottom_frame_height_mm'] <= 20 and 36 <= P['top_grip_band_height_mm'] <= 42):
    raise ValueError('Frame dimensions exceed the reviewed construction ranges')
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED = {'whole':'685e035fe7484d59c2f96483ef68dbaa9ec817b27da5bdb06705f2ec7a29a2f1',
            'single':'3e13686b9ae0970db7c880815001d2f2234e184812e54e53a03f283e565101df'}
EXPECTED_META = {'whole':'77adecdb095a32f1c5adb5b2381eaa41fc93e426e4fa7cce052270064f7d623e',
                 'single':'c4ccbf2af4746b729b4306a60ca98ee955d25a5b5ca0f6527b06aa9be7e7cd34'}
GLASS_NAME = 'Glass | 6mm透明安全玻璃'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def under(obj, root):
    while obj:
        if obj == root:
            return True
        obj = obj.parent
    return False


def geometry_digest(objects):
    digest = hashlib.sha256()
    for obj in sorted(objects, key=lambda x:x.name):
        digest.update((obj.name+'|'+obj.type+'|'+(obj.parent.name if obj.parent else '')).encode())
        digest.update(struct.pack('<16d', *[v for row in obj.matrix_local for v in row]))
        if obj.type == 'MESH':
            for v in obj.data.vertices:
                digest.update(struct.pack('<3d', *v.co))
            for poly in obj.data.polygons:
                digest.update(struct.pack('<'+'I'*len(poly.vertices), *poly.vertices))
            if obj.data.shape_keys:
                for key in obj.data.shape_keys.key_blocks:
                    digest.update(key.name.encode())
                    for v in key.data:
                        digest.update(struct.pack('<3d', *v.co))
        elif obj.type == 'FONT':
            digest.update(obj.data.body.encode())
        if obj.type in {'MESH', 'CURVE', 'FONT'}:
            digest.update('|'.join(m.name if m else '' for m in obj.data.materials).encode())
    return digest.hexdigest()


def add_visibility_driver(obj, scene, variant):
    obj['drawer_front_variant'] = variant
    obj['initial_hidden'] = variant != P['default_variant']
    obj['variant_default_visible'] = variant == P['default_variant']
    for prop in ['hide_viewport', 'hide_render']:
        curve = obj.driver_add(prop)
        driver = curve.driver
        variable = driver.variables.new()
        variable.name = 'front_mode'
        variable.type = 'SINGLE_PROP'
        variable.targets[0].id_type = 'SCENE'
        variable.targets[0].id = scene
        variable.targets[0].data_path = '["drawer_front_mode"]'
        driver.expression = 'front_mode < 0.5' if variant == 'glass' else 'front_mode >= 0.5'
    obj.hide_set(False)


def make_shared_attachments(builder,tray,bay_id,key,steel):
    """A real shared metal load path from each bridge to either front return."""
    root=bpy.data.objects.new('DrawerFrontAttachment_'+bay_id,None)
    builder.collection.objects.link(root);root.parent=tray
    builder.mark(root,key('drawer_body'),bay_id,'front_attachment',None)
    profile=[(-.322,-.026),(-.308,-.026),(-.308,-.015),(-.290,-.015),
             (-.290,-.013),(-.310,-.013),(-.310,-.024),(-.322,-.024)]
    vertices=[(x,y,z) for x in [-.009,.009] for y,z in profile]
    faces=[tuple(range(7,-1,-1)),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    ears=[]
    for sign,label in [(-1,'Left'),(1,'Right')]:
        ear=builder.shared_mesh(root.name+'_Ear_'+label,vertices,faces,(sign*.170,0,0),steel,root,key('drawer_body'),bay_id,'front_attachment')
        ear['dimensions_mm']=[18,32,13];ears.append(ear.name)
        # Fillet weld prisms touch the existing return/bridge surfaces and
        # the new ear side. No screw is drawn through undrilled old metal.
        for edge in [-1,1]:
            xx=sign*.170+edge*.009
            for level,zz,ya,yb,direction in [('Lower',-.026,-.320,-.310,1),('Upper',-.013,-.306,-.294,-1)]:
                triangle=[(xx,zz),(xx+edge*.001,zz),(xx,zz+direction*.001)]
                vv=[(x,y,z) for y in [ya,yb] for x,z in triangle]
                ff=[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)]
                builder.shared_mesh(root.name+'_Weld_'+label+'_'+level+('_Outer' if edge==sign else '_Inner'),vv,ff,(0,0,0),steel,root,key('drawer_body'),bay_id,'front_attachment_weld')
    return root,ears


def make_front(builder, tray, bay_id, single, glass, scene, metadata):
    key = lambda part: 'single:'+part if single else part+':'+bay_id
    white = bpy.data.materials['Hybrid | White']
    steel = bpy.data.materials['Hybrid | Steel']
    black = bpy.data.materials['Hybrid | Black']
    graphite = bpy.data.materials['Hybrid | Graphite']
    green = bpy.data.materials['Hybrid | Green']
    original = bpy.data.objects['DrawerFront_'+bay_id]
    original_font = next((o.data.font for o in original.children_recursive if o.type=='FONT'), None)
    shared_root,ears=make_shared_attachments(builder,tray,bay_id,key,steel)
    for obj in [original, *original.children_recursive]:
        add_visibility_driver(obj, scene, 'metal')
    new = builder.empty('DrawerGlassFront_'+bay_id, tray, key('drawer_front'), bay_id)
    w = P['front_width_mm']/1000
    z0 = P['bottom_z_mm']/1000
    z1 = z0+P['front_height_mm']/1000
    side = P['side_frame_width_mm']/1000
    bottom = P['bottom_frame_height_mm']/1000
    top = P['top_grip_band_height_mm']/1000
    window_x = w/2-side
    window_bottom, window_top = z0+bottom, z1-top
    capture = P['glass_edge_capture_mm']/1000
    glass_w = 2*(window_x+capture)
    glass_h = window_top-window_bottom+2*capture
    glass_z = (window_top+window_bottom)/2
    glass_y = P['glass_center_y_mm']/1000
    thick = P['glass_thickness_mm']/1000
    def box(suffix, loc, dims, mat=white, part='drawer_front', role='drawer_front', bevel=.0004):
        return builder.box('GlassFront_'+bay_id+'_'+suffix, loc, dims, mat, new, key(part), bay_id, role, bevel)
    # Full-depth perimeter returns reproduce the original front envelope.
    for sign in [-1,1]:
        box('FrameFaceSide', (sign*(w/2-side/2),-.324,(z0+z1)/2), (side,.002,z1-z0))
        box('FrameReturnSide', (sign*(w/2-.001),-.316,(z0+z1)/2), (.002,.016,z1-z0))
    box('FrameFaceBottom', (0,-.324,z0+bottom/2), (2*window_x,.002,bottom))
    for zz in [z0+.001,z1-.001]:
        box('FrameReturnHorizontal', (0,-.316,zz), (w-.004,.016,.002))
    # A 36 mm metal grip band carries the recessed handle. The glass has no
    # handle cutout and takes no pulling load. Status and lock have real holes.
    hz = P['handle_center_z_mm']/1000
    hw, hh = [v/1000 for v in P['handle_aperture_mm']]
    holes = [(-hw/2, hw/2, hz-hh/2, hz+hh/2), (-.172,-.160,hz-.002,hz+.002), (.161,.175,hz-.007,hz+.007)]
    if any(h[2] < window_top+.002 or h[3] > z1-.002 for h in holes):
        raise ValueError('Handle/status/lock apertures must leave metal around the top grip band')
    # Partition only the top band, leaving actual apertures rather than decals.
    xs = sorted(set([-window_x,window_x]+[x for h in holes for x in h[:2]]))
    for xa,xb in zip(xs,xs[1:]):
        active = next((h for h in holes if h[0] <= (xa+xb)/2 <= h[1]), None)
        spans = [(window_top,z1)] if active is None else [(window_top,active[2]),(active[3],z1)]
        for za,zb in spans:
            box('TopSkin', ((xa+xb)/2,-.3239,(za+zb)/2), (xb-xa,.002,zb-za))
    box('HandleCupBack',(0,-.309,hz),(.116,.002,.028),black,'drawer_handle')
    for x in [-.057,.057]:
        box('HandleCupSide',(x,-.316,hz),(.002,.014,.028),black,'drawer_handle')
    for z in [hz-.013,hz+.013]:
        box('HandleCupHorizontal',(0,-.316,z),(.114,.014,.002),black,'drawer_handle')
    box('HandleGrip',(0,-.318,hz-.008),(.090,.005,.005),black,'drawer_handle')
    box('StatusLens',(-.166,-.3239,hz),(.0114,.0015,.0034),green)
    box('StatusMount',(-.166,-.322,hz),(.014,.002,.006),black)
    box('LockEscutcheon',(.168,-.324,hz),(.0134,.0016,.0134),graphite)
    box('LockBackMount',(.168,-.3225,hz),(.016,.001,.016),black)
    pane = box('GlassPane',(0,glass_y,glass_z),(glass_w,thick,glass_h),glass,'drawer_glass','glass_panel',.00035)
    pane['glass_thickness_mm'] = P['glass_thickness_mm']
    pane['dimensions_mm'] = [glass_w*1000,thick*1000,glass_h*1000]
    # Both faces have compliant edge strips; removable rear retainers bolt to
    # stand-offs on the metal frame. The glass is captured 2 mm at each edge.
    for face_y in [glass_y-thick/2-.0005, glass_y+thick/2+.0005]:
        for sign in [-1,1]:
            box('GlazingGasketSide',(sign*(window_x+capture/2),face_y,glass_z),(capture,.001,glass_h),black,role='glass_gasket',bevel=.00015)
        for zz in [window_bottom-capture/2,window_top+capture/2]:
            box('GlazingGasketHorizontal',(0,face_y,zz),(2*window_x,.001,capture),black,role='glass_gasket',bevel=.00015)
    rear_y = glass_y+thick/2+.001+.00075
    for sign in [-1,1]:
        box('GlassRetainerSide',(sign*(window_x+.003),rear_y,glass_z),(.006,.0015,glass_h),steel,role='glass_retainer')
        for zz in [0,.076]:
            box('RetainerStandOff',(sign*(window_x+.005),-.319,zz),(.004,.008,.006),steel,role='glass_retainer')
            box('RetainerScrew',(sign*(window_x+.004),rear_y+.00135,zz),(.004,.0012,.004),steel,role='fastener',bevel=.0006)
    for zz in [window_bottom-.003,window_top+.003]:
        box('GlassRetainerHorizontal',(0,rear_y,zz),(2*window_x,.0015,.006),steel,role='glass_retainer')
        for xx in [-.170,.170]:
            standoff_z = zz+(.003 if zz>glass_z else -.004)
            box('RetainerStandOff',(xx,-.319,standoff_z),(.008,.008,.004),steel,role='glass_retainer')
            box('RetainerScrew',(xx,rear_y+.00135,zz),(.004,.0012,.004),steel,role='fastener',bevel=.0006)
    builder.label('GlassFront_'+bay_id+'_Label',bay_id,(-.118,-.32495,hz-.003),.007,graphite,new,key('drawer_front'),bay_id,original_font)
    for obj in [new,*new.children_recursive]:
        add_visibility_driver(obj,scene,'glass')
    metadata['components'][key('drawer_glass')] = {'title':bay_id+' 抽屉透明玻璃','dimensions_mm':[round(glass_w*1000,3),P['glass_thickness_mm'],round(glass_h*1000,3)],'basis':'model','bay_id':bay_id,'notes':'与左侧门玻璃复用同一材质；6 mm厚度为设计假设，四边垫条与压条固定。玻璃等级、钢化工艺及负载须实际选型验证。'}
    metadata['components'][key('drawer_front')]['notes'] += '；提供互斥金属/玻璃前板，玻璃方案采用金属周框与顶部握持带，保持原抽屉外包络。'
    return {'bay_id':bay_id,'tray_node':tray.name,'metal_node_names':[original.name],'glass_node_names':[new.name],
            'glass_mesh_node':pane.name,'front_dimensions_mm':[444,16,154],
            'visible_window_mm':[round(2*window_x*1000,3),round((window_top-window_bottom)*1000,3)],
            'shared_attachment_node_names':[shared_root.name],
            'attachment_ear_nodes':ears,
            'attachment_notes':'两块共用2 mm钢制Z形耳及焊缝，从原托盘桥头底面Z=-13 mm连接到所选前板下回边顶面Z=-26 mm；尺寸、焊缝与承载仍为设计假设。'}


def export_root(path, root, builder, scene):
    objects = [o for o in scene.objects if under(o,root) and o.type in {'EMPTY','MESH','FONT','CURVE'}]
    states = {o:(o.hide_get(),o.hide_viewport,o.hide_render) for o in objects}
    variant_drivers = []
    for obj in objects:
        if obj.get('drawer_front_variant') and obj.animation_data:
            for curve in obj.animation_data.drivers:
                if curve.data_path in {'hide_viewport','hide_render'}:
                    curve.mute = True
                    variant_drivers.append(curve)
            obj.hide_viewport = False
            obj.hide_render = False
        obj.hide_set(False)
    bpy.context.view_layer.update()
    for obj in scene.objects:
        obj.select_set(False)
    duplicates = []
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        if obj.type in {'FONT','CURVE'}:
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
            for i,mat in enumerate(mesh.materials):
                if mat:mesh.materials[i]=mat.original
            duplicate = bpy.data.objects.new(obj.name+'_Mesh',mesh)
            builder.collection.objects.link(duplicate)
            duplicate.parent = obj.parent
            duplicate.matrix_local = obj.matrix_local.copy()
            for k in obj.keys():duplicate[k]=obj[k]
            duplicate.select_set(True)
            duplicates.append(duplicate)
        else:
            obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,use_active_scene=True,
                              export_apply=False,export_animations=False,export_extras=True,export_yup=True,
                              export_cameras=False,export_lights=False,export_morph=True)
    for obj in duplicates:bpy.data.objects.remove(obj,do_unlink=True)
    for obj,(hidden,disabled,render_hidden) in states.items():
        obj.hide_set(hidden)
        obj.hide_viewport=disabled
        obj.hide_render=render_hidden
    for curve in variant_drivers:curve.mute=False
    scene.frame_set(1)
    bpy.context.view_layer.update()


reports = []
for role,source,metadata_path,target in [('whole',args.base_blend,args.base_metadata,OUT),('single',args.single_blend,args.single_metadata,OUT/'single_drawer')]:
    source,metadata_path = source.resolve(),metadata_path.resolve()
    if sha(source) != EXPECTED[role] or sha(metadata_path) != EXPECTED_META[role]:
        raise ValueError('Use the immutable published 33-bay '+role+' source and metadata')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    root = bpy.data.objects['CabinetRoot' if role=='whole' else 'SingleDrawerRoot']
    original_objects = [o for o in scene.objects if under(o,root)]
    bpy.context.view_layer.update()
    before = geometry_digest(original_objects)
    metadata = json.loads(metadata_path.read_text())
    glass = bpy.data.materials.get(GLASS_NAME)
    if not glass:
        with bpy.data.libraries.load(str(args.base_blend.resolve()),link=False) as (available,loaded):
            if GLASS_NAME not in available.materials:raise ValueError('Original left-door glass material missing')
            loaded.materials=[GLASS_NAME]
        glass = bpy.data.materials[GLASS_NAME]
    collection = bpy.data.collections.new('Drawer_Front_Variants')
    scene.collection.children.link(collection)
    builder = Builder(collection)
    scene['drawer_front_mode'] = 1 if P['default_variant']=='glass' else 0
    scene.id_properties_ui('drawer_front_mode').update(min=0,max=1,description='0 = original metal drawer fronts; 1 = glass drawer fronts')
    assemblies = []
    for bay_id in (['B'+str(i) for i in range(1,25)] if role=='whole' else ['S1']):
        tray = bpy.data.objects['Tray_'+bay_id if role=='whole' else 'SingleTray']
        assemblies.append(make_front(builder,tray,bay_id,role=='single',glass,scene,metadata))
    metadata['drawer_front_variants'] = {'default':P['default_variant'],
        'options':[{'id':'glass','label':'透明玻璃'},{'id':'metal','label':'金属前板'}],
        'assemblies':assemblies,'parameters_mm':P,
        'visibility_contract':'glTF has no standard visibility flag; apply exclusive variant extras before the first frame.',
        'blender_control':'Scene custom property drawer_front_mode: 0 metal, 1 glass'}
    metadata['front_variant_source'] = {'base_package':'hybrid-33bay','blend_sha256':EXPECTED[role],
        'metadata_sha256':EXPECTED_META[role],'original_geometry_sha256':before,
        'intentional_changes':'Only original front assembly extras and visibility drivers; all original geometry, transforms, materials, cables and mechanisms are retained.'}
    bpy.context.view_layer.update()
    after = geometry_digest(original_objects)
    if before != after:raise AssertionError('Original geometry, hierarchy or materials changed')
    target.mkdir(parents=True,exist_ok=True)
    blend_name = 'smart_cabinet_33bay.blend' if role=='whole' else 'smart_cabinet_drawer.blend'
    glb_name = 'smart_cabinet.glb' if role=='whole' else 'smart_cabinet_drawer.glb'
    meta_name = 'components.json' if role=='whole' else 'drawer_compartment.json'
    export_root(target/glb_name,root,builder,scene)
    if before != geometry_digest(original_objects):raise AssertionError('Export modified source geometry')
    (target/meta_name).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(target/blend_name),compress=True)
    reports.append({'role':role,'source_blend_sha256':EXPECTED[role],'source_metadata_sha256':EXPECTED_META[role],
                    'original_object_count':len(original_objects),'original_geometry_sha256':before,
                    'preserved_original_geometry':before==after,'front_count':len(assemblies),
                    'new_object_count':len(builder.objects),'default_variant':P['default_variant'],
                    'files':{name:{'sha256':sha(target/name),'bytes':(target/name).stat().st_size} for name in [blend_name,glb_name,meta_name]}})
    print('GLASS_VARIANTS_EXPORTED',role,str(target),flush=True)
(OUT/'build_report.json').write_text(json.dumps({'status':'built_pending_independent_audit','parameters':P,'scenes':reports,
    'limits':'Visual/mechanical design assumptions; no glass-strength, load, electrical or thermal qualification.'},ensure_ascii=False,indent=2)+'\n')
