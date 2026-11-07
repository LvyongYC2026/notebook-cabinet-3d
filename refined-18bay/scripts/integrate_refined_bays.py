"""Compose the approved refined bay internals into the existing eighteen-bay cabinet.

Run with Blender --background --python-exit-code 1 --python scripts/integrate_refined_bays.py
Candidate files only: output/cabinet/refined_candidate. No website files are written.
All measurements are metres internally. Shared static meshes reduce GLB duplication.
"""
import bpy, sys, json, math, subprocess, hashlib, copy
from pathlib import Path
from collections import defaultdict
from mathutils import Vector, Matrix

def argument(flag,default):
    return Path(sys.argv[sys.argv.index(flag)+1]).resolve() if flag in sys.argv else default

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'output/cabinet/refinement_baseline'
BASE_BLEND=argument('--base-blend',BASELINE/'smart_cabinet_18bay_before_refinement.blend')
BASE_META=argument('--base-metadata',BASELINE/'components_before_refinement.json')
if not BASE_BLEND.is_file() or not BASE_META.is_file():
    raise FileNotFoundError('Missing immutable pre-refinement baseline. See refined candidate README; do not use the already-refined cabinet as its own baseline.')
OUT=argument('--output',ROOT/'output/cabinet/refined_candidate'); OUT.mkdir(parents=True,exist_ok=True)
TEMPLATE=OUT/'_template'; TEMPLATE.mkdir(exist_ok=True)
# Only internals are extracted; the 450mm wrapper shell is discarded. LED source
# z460 maps to support+413, below the assembled ceiling at support+420.
CONFIG={'width_mm':420,'depth_mm':650,'height_mm':450,'tray_mm':[376,470,2],
        'laptop_mm':[300,210,18],'laptop_center_xy_mm':[30,-75],
        'laptop_lid_height_mm':195,'laptop_opening_degrees':105,
        'led_center_mm':[0,-245,460],'font_path':''}
(TEMPLATE/'bay_configuration.json').write_text(json.dumps(CONFIG,indent=2))
source=argument('--single-builder',ROOT/'single_compartment/build_smart_cabinet.py')
if '--reuse-template' not in sys.argv:
    with (TEMPLATE/'build.log').open('w') as log:
        subprocess.run([bpy.app.binary_path,'--background','--python-exit-code','1','--python',str(source),'--',
                        '--config',str(TEMPLATE/'bay_configuration.json'),'--output',str(TEMPLATE),'--build-only'],stdout=log,stderr=subprocess.STDOUT,check=True)
single=json.loads((TEMPLATE/'model_metadata.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(BASE_BLEND))
scene=bpy.context.scene;scene.frame_set(1)
product=bpy.data.collections['01_Product / 三模块智能柜'];studio=bpy.data.collections['02_Studio / 灯光与展示场景']
meta=json.loads(BASE_META.read_text())
EMPTY={'A3','B2','B6'};SWING=95;TRAVEL=.320

def under(obj,parent):
    while obj:
        if obj==parent:return True
        obj=obj.parent
    return False
def descendants(obj):
    return [obj]+[o for c in obj.children for o in descendants(c)]
def remove(obj):
    for ob in reversed(descendants(obj)):
        if ob.name in bpy.data.objects:bpy.data.objects.remove(ob,do_unlink=True)
def empty(name,parent,loc=(0,0,0)):
    ob=bpy.data.objects.new(name,None);product.objects.link(ob);ob.parent=parent;ob.location=loc;ob.empty_display_size=.02;return ob
def mark(ob,key,bay):
    ob['component_key']=key+':'+bay;ob['bay_id']=bay;ob['basis']='model'
def box_data(name,dims,material):
    x,y,z=[q/2 for q in dims];v=[(a*x,b*y,c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]);me.materials.append(material);return me
def instance(name,mesh,parent,key,bay,loc=(0,0,0)):
    ob=bpy.data.objects.new(name,mesh);product.objects.link(ob);ob.parent=parent;ob.location=loc;mark(ob,key,bay);return ob

# Remove only superseded bay internals. Keep the cabinet, screen, equipment and rear doors.
bay_locations={}
for side,c0 in [('A',-.975),('B',.975)]:
    for n in range(1,10):
        code=side+str(n);cx=c0+((n-1)%3-1)*.45;support=[1.25,.8,.35][(n-1)//3]
        bay=bpy.data.objects['Bay_'+code];door=bpy.data.objects['DoorPivot_'+code]
        for ob in list(bay.children):
            if ob==door or any(s in ob.name for s in ('_Shelf','_Ceiling','_RearServiceRail','_RearAirDuct')):continue
            remove(ob)
        for ob in list(bpy.data.objects):
            if ob.name.startswith('DynamicCable_'+code) or ob.name==code+'_BayLight':remove(ob)
        # A shallow support plinth below the new real slide assembly, not through it.
        shelf=bpy.data.objects[code+'_Shelf'];shelf.location.z=support-.0294
        ceiling=bpy.data.objects[code+'_Ceiling']
        if n<=3:ceiling.location.z=support+.4206
        else:remove(ceiling)  # The next row shelf is also this row's 420mm-clear ceiling.
        bpy.context.view_layer.update()
        children={o:o.matrix_world.copy() for o in bay.children}
        bay.location=(cx,0,support-.047);bpy.context.view_layer.update()
        for ob,matrix in children.items():ob.matrix_world=matrix
        bay['occupied']=code not in EMPTY;bay['support_height_mm']=round(support*1000)
        bay['minimum_clearance_mm']=[420,420,420];bay_locations[code]=[cx,0,support-.047]
        door.animation_data_clear();door.rotation_euler.z=0
        door['open_degrees']=-SWING;door['swing_degrees']=-SWING;door['min_open_degrees']=SWING

print('STAGE original internals removed',flush=True)
# Keep hinge sweep clear of the existing support framework while retaining the 650mm envelope.
for ob in product.objects:
    if ob.name.startswith(('Left_FrontPost','Right_FrontPost')):ob.location.y=-.274
    if ob.name.startswith(('Left_CrossRail','Right_CrossRail')):ob.location.y=-.277;ob.location.z-=.025
    if ob.name.startswith('Housing_') and '_Side' in ob.name:
        ob.dimensions.y=.610;ob.location.y=.020
# Load the parameterised standalone reference as a temporary source scene.
tmp=bpy.data.collections.new('_RefinedTemplate');scene.collection.children.link(tmp)
with bpy.data.libraries.load(str(TEMPLATE/'smart_cabinet_single_compartment.blend'),link=False) as (available,loaded):
    loaded.objects=available.objects
source_objects=[o for o in loaded.objects if o]
for ob in source_objects:tmp.objects.link(ob)
sroot=next(o for o in source_objects if o.name=='SingleCabinetRoot')
stray=next(o for o in source_objects if o.name=='SingleTray')
slap=next(o for o in source_objects if o.name=='Laptop')
for ob in source_objects:
    if ob.animation_data:ob.animation_data_clear()
stray.location=(0,0,0)
# Resolve thickness setter/cache loss in the source's non-default tray width.
bpy.context.view_layer.update()
next(o for o in source_objects if o.name=='Tray_Deck').dimensions=(.376,.470,.002)
# Raise the complete slide mechanism 5mm, retaining the specified deck support height.
for ob in source_objects:
    if ob.name.startswith(('Rail_','Slide_')):ob.location.z+=.005
bpy.context.view_layer.update()
print('STAGE source loaded',flush=True)
dg=bpy.context.evaluated_depsgraph_get()
allowed={'interface_panel','network','ac_socket','power','adapter','adapter_bracket','cables','tray','laptop','led'}
mapping={'interface_panel':'ports','led':'light'}
groups=defaultdict(list);dynamic={}
for ob in source_objects:
    key=ob.get('component_key','').removeprefix('single:')
    if ob.type not in {'MESH','CURVE','FONT'} or key not in allowed:continue
    if ob.name.startswith('SingleDynamicCable_'):
        dynamic[ob.get('cable_kind')]=ob;continue
    anchor='laptop' if under(ob,slap) else ('tray' if under(ob,stray) else 'fixed')
    role='connector_'+ob.name.split('_')[1] if ob.name in {'Laptop_network_Connector','Laptop_power_Connector'} else 'body'
    groups[(anchor,mapping.get(key,key),role)].append(ob)

def merge_geometry(name,objects):
    vertices=[];faces=[];indices=[];materials=[];smooth=[]
    for ob in objects:
        ev=ob.evaluated_get(dg);mesh=ev.to_mesh();offset=len(vertices)
        vertices.extend([tuple(ev.matrix_world@v.co) for v in mesh.vertices])
        slots=[]
        for mat in mesh.materials:
            mat=mat.original
            if mat not in materials:materials.append(mat)
            slots.append(materials.index(mat))
        for face in mesh.polygons:
            faces.append(tuple(offset+i for i in face.vertices));indices.append(slots[face.material_index] if slots else 0);smooth.append(face.use_smooth)
        ev.to_mesh_clear()
    me=bpy.data.meshes.new(name);me.from_pydata(vertices,[],faces);me.update()
    for mat in materials:me.materials.append(mat)
    for polygon,mi,sm in zip(me.polygons,indices,smooth):polygon.material_index=mi;polygon.use_smooth=sm
    return me
print('STAGE merging groups',len(groups),flush=True)
shared={g:merge_geometry('RefinedShared_'+'_'.join(g),obs) for g,obs in groups.items()}
blue=bpy.data.materials['Blue network cable and boot'];black=bpy.data.materials['EPDM seals and cable sheath']
steel=bpy.data.materials['Zinc plated steel']

# Fixed parking leads have generous low sidewall bends and clipped connectors.
# Their socket/feed end is the same as the native lead; the free plug docks above the tray.
def bezier(a,b,c,d,steps=12):
    return [tuple((1-t)**3*Vector(a)+3*(1-t)**2*t*Vector(b)+3*(1-t)*t*t*Vector(c)+t**3*Vector(d)) for t in [i/steps for i in range(steps+1)]]
def tube(name,points,r,mat):
    vv=[];ff=[];sides=8
    for i,p in enumerate(points):
        tangent=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
        tangent.normalize();axis=Vector((1,0,0));u=tangent.cross(axis).normalized()
        if u.length<.1:u=tangent.cross(Vector((0,0,1))).normalized()
        v=tangent.cross(u).normalized()
        for j in range(sides):vv.append(tuple(Vector(p)+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides))))
    for i in range(len(points)-1):
        for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;ff.append((a,b,b+sides,a+sides))
    ff.extend([tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))])
    me=bpy.data.meshes.new(name);me.from_pydata(vv,[],ff);me.materials.append(mat)
    for p in me.polygons:p.use_smooth=True
    return me

def min_sampled_radius_mm(points):
    radii=[]
    for a,b,c in zip(points,points[1:],points[2:]):
        ab=Vector(b)-Vector(a);bc=Vector(c)-Vector(b);ac=Vector(c)-Vector(a);cross=ab.cross(ac).length
        if cross>1e-14:radii.append(ab.length*bc.length*ac.length/(2*cross)*1000)
    return min(radii) if radii else None

parking={};parking_points={};parking_radii={};dock_positions={}
for path in single['cable_paths']:
    kind=path['id'].split('_',1)[1];x,z,ny=path['fixed'];start=(x,-ny,z)
    # Left wall service strip. The forward docking plug stays clear of the adapter basket.
    dock=(-.139,-.218,.205 if kind=='network' else .240);dock_positions[kind]=dock
    via=(-.128,.120,.180 if kind=='network' else .215)
    points=bezier(start,(x,.270,z),(-.128,.270,via[2]),via,20)
    # Matching tangents at the join avoid the former kink in parked leads.
    points+=bezier(via,(-.128,.030,via[2]),(-.139,-.170,dock[2]),dock,32)[1:]
    parking_points[kind]=points
    parking_radii[kind]=min_sampled_radius_mm(points)
    if parking_radii[kind]<28:raise ValueError('Parking cable sampled bend radius below28mm: '+kind)
    parking[kind]=tube('RefinedShared_Parked_'+kind,points,path['radius_mm']/1000,blue if kind=='network' else black)
plugmeshes={k:box_data('RefinedShared_ParkingPlug_'+k,(.016,.023,.010),blue if k=='network' else black) for k in parking}
railshim=box_data('RefinedShared_RailSupportShim',(.018,.030,.00105),steel)
dockmesh=box_data('RefinedShared_ParkingDock',(.066,.026,.002),steel)
dockclip=box_data('RefinedShared_ParkingEndClip',(.003,.026,.010),black)
ledclip=box_data('RefinedShared_LEDTopClip',(.007,.021,.001),steel)
spacers={};led_feed_meshes={}
led_grommet=box_data('RefinedShared_LEDWireGrommet',(.003,.007,.007),black)

print('STAGE shared geometry built',flush=True)
cable_paths=[];created=[];parking_objects=[];moving_connectors={}
for code,location in bay_locations.items():
    bay=bpy.data.objects['Bay_'+code];occupied=code not in EMPTY
    tray=empty('Tray_'+code,bay);mark(tray,'tray',code);tray['travel_mm']=320;tray['interaction']='tray'
    lap=empty('Laptop_'+code,tray) if occupied else None
    if lap:mark(lap,'laptop',code);lap['base_dimensions_mm']=[300,210,18];lap['opening_degrees']=105
    for (anchor,key,role),mesh in shared.items():
        if anchor=='laptop' and not occupied:continue
        if role.startswith('connector_') and not occupied:continue
        parent={'fixed':bay,'tray':tray,'laptop':lap}[anchor]
        name=(code+'_PowerAdapter' if key=='adapter' and anchor=='fixed' else code+'_Refined_'+anchor+'_'+key+'_'+role)
        ob=instance(name,mesh,parent,key,code);created.append(ob)
        if role.startswith('connector_'):moving_connectors[(code,role.removeprefix('connector_'))]=[name]
    for xx in [-.193,.193]:
        for yy in [-.18,.17]:instance(code+'_Refined_fixed_tray_SupportShim',railshim,bay,'tray',code,(xx,yy,.018725))
    # Solid mounting stand-offs bridge the former template wall to the actual cabinet wall.
    wall=-.2235 if int(code[1:])%3==1 else -.2244
    supports=[]
    for yy in [-.172,-.028]:
        for zz in [.140,.368]:supports.append(('Panel',-.207,yy,zz,.008,.008))
    for yy,zz in [(.129,.166),(.129,.284),(.176,.143),(.176,.239)]:supports.append(('Raceway',-.208,yy,zz,.008,.008))
    for yy in [-.132,-.068]:supports.append(('Adapter',-.19975,yy,.126,.010,.010))
    for kind,point in dock_positions.items():supports.append(('Parking',-.211,point[1],point[2]-.006,.016,.008))
    for name,end,yy,zz,dy,dz in supports:
        dims=(end-wall,dy,dz)
        if dims not in spacers:spacers[dims]=box_data('RefinedShared_InstallationSpacer',dims,steel)
        instance(code+'_Refined_fixed_supports_'+name,spacers[dims],bay,'adapter_bracket' if name=='Adapter' else 'ports',code,((wall+end)/2,yy,zz))
    for xx in [-.143,.143]:instance(code+'_Refined_fixed_supports_LEDClip',ledclip,bay,'light',code,(xx,-.245,.4665))
    if wall not in led_feed_meshes:led_feed_meshes[wall]=tube('RefinedShared_LEDWallFeed',[(-.216,-.045,.444),(wall,-.045,.444)],.0012,black)
    instance(code+'_Refined_fixed_cables_LEDWallFeed',led_feed_meshes[wall],bay,'cables',code)
    instance(code+'_Refined_fixed_supports_LEDWireGrommet',led_grommet,bay,'cables',code,(wall+.0005,-.045,.444))

    for path in single['cable_paths']:
        kind=path['id'].split('_',1)[1]
        park=instance('ParkingCable_'+code+'_'+kind,parking[kind],bay,'cables',code)
        plug=instance('ParkingPlug_'+code+'_'+kind,plugmeshes[kind],bay,'cables',code,dock_positions[kind])
        dock=instance(code+'_Refined_ParkingDock_'+kind,dockmesh,bay,'cables',code,(-.178,dock_positions[kind][1],dock_positions[kind][2]-.006))
        instance(code+'_Refined_ParkingDockClip_'+kind,dockclip,bay,'cables',code,(-.148,dock_positions[kind][1],dock_positions[kind][2]))
        for ob in [park,plug]:
            ob['stowed']=True;ob['motion']='stowed';ob['initial_hidden']=occupied;ob.hide_render=occupied;parking_objects.append(ob)
        item=copy.deepcopy(path);item.update({'id':'cable_'+code+'_'+kind,'bay_id':code,'component_key':'cables:'+code,
            'space':'bay_local_gltf','parent_node':'Bay_'+code,'tray_node':'Tray_'+code,
            'parking_node_names':[park.name,plug.name],'moving_connector_node_names':moving_connectors.get((code,kind),[]),
            'stowed':not occupied,'motion':'native_morph' if occupied else 'stowed',
            'parking_guide_points':[[x,z,-y] for x,y,z in parking_points[kind]],
            'parking_min_sampled_radius_mm':round(parking_radii[kind],3),
            'parking_length_mm':round(sum((Vector(b)-Vector(a)).length for a,b in zip(parking_points[kind],parking_points[kind][1:]))*1000,3)})
        if occupied:
            src=dynamic[kind];me=bpy.data.meshes.new('Controlled_'+code+'_'+kind)
            me.from_pydata([tuple(v.co) for v in src.data.vertices],[],[tuple(p.vertices) for p in src.data.polygons]);me.update()
            for mat in src.data.materials:me.materials.append(mat)
            for p in me.polygons:p.use_smooth=True
            ob=bpy.data.objects.new('DynamicCable_'+code+'_'+kind,me);product.objects.link(ob);ob.parent=bay
            mark(ob,'cables',code);ob['dynamicCable']=True;ob['cable_kind']=kind
            ob.shape_key_add(name='Basis');ob.shape_key_add(name='TrayExtended320mm')
            sk=ob.data.shape_keys
            for target,source_key in zip(sk.key_blocks,src.data.shape_keys.key_blocks):
                for a,b in zip(target.data,source_key.data):a.co=b.co
            sk.key_blocks['TrayExtended320mm'].value=0
            driver=sk.key_blocks['TrayExtended320mm'].driver_add('value').driver;driver.type='SCRIPTED';driver.expression='min(max(-travel/0.32,0),1)'
            var=driver.variables.new();var.name='travel';var.type='TRANSFORMS';var.targets[0].id=tray;var.targets[0].transform_type='LOC_Y';var.targets[0].transform_space='LOCAL_SPACE'
            item['source_node_names']=[ob.name]
        else:
            item['source_node_names']=[park.name];item.pop('morph_target',None)
            item['moving']=None;item['guide_points_extended']=[]
            item['guide_points']=item['parking_guide_points'];item['rest_length_mm']=item['parking_length_mm'];item['closed_length_mm']=item['parking_length_mm'];item['extended_length_mm']=item['parking_length_mm']
        cable_paths.append(item)
    for skey,record in single['components'].items():
        key=skey.removeprefix('single:')
        if key not in allowed:continue
        key=mapping.get(key,key);rec=copy.deepcopy(record);rec['title']=code+' '+rec['title'].replace('单仓','');rec['bay_id']=code
        meta['components'][key+':'+code]=rec
    meta['components']['bay:'+code].update({'occupied':occupied,'actual_layout':'refined_420mm','notes':f'文档420 mm净空参考；内部已适配376 mm白托盘与300×210 mm笔电。当前为'+('有设备仓。' if occupied else '空电脑仓，适配器与接线保留，端线在固定卡座收纳。')})
    meta['components']['door:'+code]['notes']='左铰链，整柜机械开启限位95°，用于相邻仓避让；抽盘前门须完全开启。'
    meta['components']['door:'+code]['swing_degrees']=-SWING
    meta['components']['cables:'+code]['notes']='蓝网线、黑DC线使用低位受控恒长U形活动余量；交流输入固定连接适配器。空仓或借出状态切换固定停车线路。弯曲半径与疲劳寿命未实测。'

print('STAGE all bay instances built',flush=True)
# Drop the temporary source objects. Linked shared mesh datablocks remain in use.
# Unlink the reference collection before evaluation: Blender 5.2 can crash when
# deleting loaded objects still referenced by evaluated shape-key IDs.
scene.collection.children.unlink(tmp)
tmp.use_fake_user=False
meta.update({'cable_paths':cable_paths,'cable_system':'controlled_native_v2','refined_bay_configuration':CONFIG,
             'front_door_degrees':SWING,'min_open_degrees':SWING,
             'source_reference':'approved refined single compartment; internal geometry rebuilt for 420mm bay width',
             'design_assumptions':['柜体3300×650×1850和18仓布局不变。','笔电占位改300×210×18 mm、开105°；白色托盘376×470×2 mm。','固定接口与适配器保留实际示意尺寸，不复制单仓壳体。','前门95°机械限位；供几何展示，非制造定版。','空仓A3/B2/B6仍有固定适配器，端线停靠。']})
(OUT/'components.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))

# Demonstration poses retain familiar frame numbers, using one populated bay and an empty bay.
for code in ['A1','A3']:
    door=bpy.data.objects['DoorPivot_'+code];tray=bpy.data.objects['Tray_'+code]
    for f,angle in [(1,0),(30,0),(65,-SWING),(135,-SWING),(170,0),(360,0)]:door.rotation_euler.z=math.radians(angle);door.keyframe_insert('rotation_euler',frame=f)
    for f,travel in [(1,0),(70,0),(100,-TRAVEL),(120,-TRAVEL),(150,0),(360,0)]:tray.location.y=travel;tray.keyframe_insert('location',frame=f)
scene.frame_set(1);bpy.context.view_layer.update()

print('STAGE source dropped and metadata ready',flush=True)
# Bake only static modifiers in one dependency-graph snapshot. Native morphs stay intact.
static_bakes=[];bake_dg=bpy.context.evaluated_depsgraph_get()
for ob in list(product.objects):
    if ob.type=='MESH' and ob.modifiers and not ob.data.shape_keys:
        ev=ob.evaluated_get(bake_dg)
        baked=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bake_dg)
        for i,mat in enumerate(baked.materials):baked.materials[i]=mat.original
        static_bakes.append((ob,baked))
for ob,baked in static_bakes:ob.modifiers.clear();ob.data=baked
print('STAGE static modifiers baked',len(static_bakes),flush=True)
# Export all product nodes including initially-hidden parking alternatives; visibility is in extras.
converted=[]
bpy.ops.object.select_all(action='DESELECT')
for ob in list(product.objects):
    if ob.type not in {'EMPTY','MESH','CURVE','FONT'}:continue
    if ob.type in {'CURVE','FONT'}:
        ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=bpy.data.meshes.new_from_object(ev)
        dup=bpy.data.objects.new(ob.name+'_Mesh',mesh);product.objects.link(dup);dup.parent=ob.parent;dup.matrix_local=ob.matrix_local.copy()
        for key in ob.keys():dup[key]=ob[key]
        dup.select_set(True);converted.append(dup)
    else:ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'smart_cabinet.glb'),export_format='GLB',use_selection=True,
    export_apply=False,export_animations=False,export_extras=True,export_yup=True,
    export_materials='EXPORT',export_cameras=False,export_lights=False,export_morph=True)
for ob in converted:bpy.data.objects.remove(ob,do_unlink=True)
for ob in parking_objects:ob.hide_set(bool(ob.get('initial_hidden')))
scene.frame_set(65);scene.camera=bpy.data.objects['Camera_01_Hero']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.overlay.show_overlays=False;area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT');bpy.data.objects['CabinetRoot'].select_set(True)
bpy.context.view_layer.objects.active=bpy.data.objects['CabinetRoot']
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'smart_cabinet_18bay.blend'),compress=True)
report={'configuration':CONFIG,'cabinet_dimensions_mm':[3300,650,1850],'bay_count':18,'occupied_bays':15,'empty_bays':sorted(EMPTY),
        'front_bay_doors':18,'rear_maintenance_doors':3,'front_door_limit_degrees':SWING,'support_heights_mm':[350,800,1250],
        'actual_laptop_base_mm':[300,210,18],'actual_tray_deck_mm':[376,470,2],
        'horizontal_shelf_center_below_support_mm':29.4,'clear_height_above_support_mm':420,
        'rail_hardware_raise_mm':5,'rail_support_shim_mm':1.05,'installation_spacer_depth_mm':[12.5,24.65],
        'led_center_above_support_mm':413,'led_top_clearance_to_ceiling_mm':1,
        'parking_min_sampled_radius_mm':parking_radii,'native_cables':30,'stowed_bay_cables':6,'parking_alternatives':30,'shared_static_meshes':len(shared),
        'source_script_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'candidate_files':['smart_cabinet_18bay.blend','smart_cabinet.glb','components.json'],
        'status':'candidate_geometry_pending_independent_validation','limits':['Sampled geometry only; no load, heat, electrical or manufacturing certification.']}
(OUT/'refined_model_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('REFINED_CANDIDATE_READY',json.dumps(report,ensure_ascii=False),flush=True)
