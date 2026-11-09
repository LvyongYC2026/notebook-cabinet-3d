"""Incremental 33-bay hybrid cabinet builder; immutable original is mandatory.

blender --background --python scripts/hybrid/build_hybrid.py -- --output output/hybrid_candidate
The initial drawers stage explicitly reports the fixed-trunk/central work still pending.
"""
import bpy, sys, json, math, hashlib, copy
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from config import PARAMETERS
from geometry import Builder, material, under, remove, bake_and_share
from drawer import build_drawer
from central_upgrade import upgrade_central
from fixed_wiring import build_fixed
ROOT=HERE.parents[1]
def arg(k,d):return sys.argv[sys.argv.index(k)+1] if k in sys.argv else d
BASE=Path(arg('--base-blend',str(ROOT/'output/cabinet/wiring_release/smart_cabinet_18bay.blend'))).resolve()
BASE_META=Path(arg('--base-metadata',str(ROOT/'output/cabinet/wiring_release/components.json'))).resolve()
OUT=Path(arg('--output',str(ROOT/'output/hybrid_candidate'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
STAGE=arg('--stage','full');P=copy.deepcopy(PARAMETERS)
if '--config' in sys.argv:
    cfg=json.loads(Path(arg('--config','')).read_text());unknown=set(cfg)-set(P)
    if unknown:raise ValueError('Unknown parameters: '+str(sorted(unknown)))
    P.update(cfg)
if P['drawer_rows']!=8 or P['drawer_columns']!=3 or P['cabinet_mm']!=[3300,650,1850]:raise ValueError('This validated layout expects 3 columns × 8 drawer rows in the 3300×650×1850 shell')
if P['laptop_mm']!=[300,210,30] or P['net_height_mm']<P['laptop_mm'][2]+100:raise ValueError('Closed laptop 30mm +100mm headroom is mandatory')
if P['lowest_support_mm']+7*P['row_pitch_mm']+P['net_height_mm']>1645:raise ValueError('Drawer stack exceeds preserved top beam underside1645mm')
source_sha=hashlib.sha256(BASE.read_bytes()).hexdigest()
if source_sha!='81c0fe823ede81c715ebc82dcd3435ecc06cef8a3c73ee331536223e4133d1c0':raise ValueError('Use immutable approved 81c0fe wiring baseline')
bpy.ops.wm.open_mainfile(filepath=str(BASE));scene=bpy.context.scene;scene.frame_set(1)
root=bpy.data.objects['CabinetRoot'];right=bpy.data.objects['Module_Right']
meta=json.loads(BASE_META.read_text());old_names=set(bpy.data.objects)

def fingerprint(objects):
    h=hashlib.sha256()
    for o in sorted(objects,key=lambda x:x.name):
        h.update(o.name.encode());h.update(str(o.type).encode())
        if o.type=='MESH':
            for v in o.data.vertices:h.update(str(tuple(v.co)).encode())
            for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
    return h.hexdigest()
preserved_a=[o for o in scene.objects if o.get('bay_id','').startswith('A') or o.name.startswith(('FixedNetwork_A','FixedAC_A'))]
preserved_a_hash=fingerprint(preserved_a)
intentional=[]
for o in [o for o in scene.objects if o.name.startswith('Bay_B') and o.type=='EMPTY']:
    intentional.extend(x.name for x in [o,*o.children_recursive]);remove(o)
for n in [o.name for o in scene.objects]:
    o=bpy.data.objects.get(n)
    if o is None:continue
    if n.startswith(('Right_CrossRail','Right_RearDuct','FixedNetwork_B','FixedAC_B','Wiring_B','DynamicCable_B','ParkingCable_B','ParkingPlug_B')):
        # Retain the existing highest crossrail as an immutable clearance boundary.
        if n.startswith('Right_CrossRail') and o.location.z>1.6:continue
        intentional.append(n);remove(o)
for k in list(meta['components']):
    if ':' in k and k.rsplit(':',1)[-1].startswith('B') and k.rsplit(':',1)[-1][1:].isdigit():del meta['components'][k]
meta['cable_paths']=[r for r in meta['cable_paths'] if not str(r.get('bay_id','')).startswith('B')]
meta['usb_connections']=[r for r in meta['usb_connections'] if not str(r.get('bay_id','')).startswith('B')]
for path in meta['cable_paths']:path['initial_occupied']=path.get('bay_id') not in P['empty_bays']
meta['wiring_design']['fixed_routes']=[r for r in meta['wiring_design']['fixed_routes'] if not str(r.get('bay_id','')).startswith('B')]
col=bpy.data.collections.new('Hybrid_33_Bay_Design');scene.collection.children.link(col);b=Builder(col)
M={k:material(k.title(),c,metal,rough,em) for k,c,metal,rough,em in [
 ('white',(.76,.79,.80),.20,.32,0),('steel',(.44,.51,.55),.75,.30,0),('black',(.012,.018,.022),.05,.45,0),('graphite',(.035,.055,.067),.35,.32,0),('silver',(.48,.54,.58),.70,.30,0),('blue',(.018,.20,.56),.05,.40,0),('purple',(.35,.055,.57),.05,.40,0),('green',(.035,.45,.22),.05,.35,.25),('label',(.58,.70,.75),.05,.40,0)]}

# Bottom 35cm is an exterior datum, never a solid beam across old A tray sweeps.
fascia=bpy.data.objects['Housing_Right_BaseFascia'];fascia.dimensions.z=.295;fascia.location.z=.2025;intentional.append(fascia.name)
right_label=bpy.data.objects['Right_BaseLabel'];right_label.data=right_label.data.copy();right_label.data.body='B / 01 — 24';intentional.append(right_label.name)
for code in ['A7','A8','A9']:
    dp=bpy.data.objects['DoorPivot_'+code]
    o=b.box('Hybrid35cmSeam_'+code,(.211,-.014,.350-dp.matrix_world.translation.z),(.414,.0006,.0015),M['graphite'],dp,'housing:Left',code,.0002,'appearance_seam')
dp=bpy.data.objects['EquipmentDoorPivot']
b.box('Hybrid35cmSeam_Center',(-.281,-.013,.350-dp.matrix_world.translation.z),(.530,.0006,.0015),M['graphite'],dp,'equipment_door',bevel=.0002,role='appearance_seam')
b.box('RightUpperInfilling',(.975,-.317,1.6465), (1.346,.014,.039),M['white'],right,'housing:Right',bevel=.0005)

for n in range(1,25):
    row=(n-1)//3;column=(n-1)%3;support=(P['lowest_support_mm']+(7-row)*P['row_pitch_mm'])/1000;cx=.525+.450*column
    bay,tray,lap=build_drawer(b,right,'B'+str(n),support,cx,P,M,meta)
    # Each horizontal separator provides the previous drawer's130mm ceiling.
    if row==0:b.box('BTopCeiling_'+str(column),(cx,-.015,support+.1306),(.420,.560,.0012),M['white'],right,'bay:B'+str(n),'B'+str(n),.0003,'structure')
    print('HYBRID_DRAWER',n,flush=True)

for code in ['A'+str(i) for i in range(1,10)]:
    r=meta['components']['bay:'+code];r.update(access_type='hinged',side='left',row=(int(code[1:])-1)//3,column=(int(code[1:])-1)%3,support_height_mm=bpy.data.objects['Bay_'+code].get('support_height_mm'),tray_node='Tray_'+code,door_node='DoorPivot_'+code,travel_mm=320)
meta['bay_ids']=['A'+str(i) for i in range(1,10)]+['B'+str(i) for i in range(1,25)]
meta['empty_bays']=P['empty_bays'];meta['bay_layout']={'left':[3,3],'right':[3,8]}
meta['refined_drawer_configuration']=copy.deepcopy(P)
meta['components']['cabinet'].update(title='33仓混合笔记本存储柜',notes='3300×650×1850 mm；左9开盖存储仓，右24闭盖抽屉；35 cm为外观分缝，中央高设备舱保留。')
meta['cable_system']='controlled_native_v3_hybrid'
meta['source_provenance']={'base_blend':'wiring-18bay/smart_cabinet_18bay.blend','base_metadata':'wiring-18bay/components.json','base_sha256':source_sha,'preserved_a_geometry_sha256':preserved_a_hash,'intentional_original_object_changes':sorted(set(intentional))}
meta['design_assumptions']=['右侧闭合笔电总厚30 mm为新假设；不是原18 mm底座厚度。','电脑承托38–150 cm，每层160 mm；130 mm有效净高保留100 mm头部余量。','全柜33路供电/锁控、48口网络为待选型设计容量；本候选阶段以build_report完成状态为准。','35 cm为统一外观线，左侧随门分段、中央高门不被内部隔断。','抽屉齐平前板320 mm外伸，房间操作空间须重验。']
meta['build_stage']=STAGE
assert fingerprint(preserved_a)==preserved_a_hash,'Original A geometry changed'
if STAGE=='full':
    netports,acports=upgrade_central(b,root,meta,M,intentional)
    build_fixed(b,root,meta,M,netports,acports,intentional)
    meta['source_provenance']['intentional_original_object_changes']=sorted(set(intentional))

if '--routes-only' in sys.argv:
    (OUT/'components.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print('ROUTES_ONLY',OUT,flush=True);sys.exit(0)

def export_root(output,exportroot,builder):
    output.parent.mkdir(parents=True,exist_ok=True)
    obs=[o for o in scene.objects if under(o,exportroot) and o.type in {'EMPTY','MESH','FONT','CURVE'}]
    bake_and_share([o for o in builder.objects if o in obs])
    for o in scene.objects:o.select_set(False)
    duplicates=[];dg=bpy.context.evaluated_depsgraph_get()
    for o in obs:
        o.hide_set(False)
        if o.type in {'FONT','CURVE'}:
            me=bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            for i,m in enumerate(me.materials):me.materials[i]=m.original if m else M['white']
            du=bpy.data.objects.new(o.name+'_Mesh',me);builder.collection.objects.link(du);du.parent=o.parent;du.matrix_local=o.matrix_local.copy()
            for k in o.keys():du[k]=o[k]
            du.select_set(True);duplicates.append(du)
        else:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,use_active_scene=True,export_apply=False,export_animations=False,export_extras=True,export_yup=True,export_cameras=False,export_lights=False,export_morph=True)
    for o in duplicates:bpy.data.objects.remove(o,do_unlink=True)
    for o in obs:o.hide_set(bool(o.get('initial_hidden',False)))

scene.frame_set(1);bpy.context.view_layer.update()
export_root(OUT/'smart_cabinet.glb',root,b)
(OUT/'components.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'smart_cabinet_33bay.blend'),compress=True)
report={'status':'candidate_geometry_first','stage':STAGE,'pending':(['48-port central switch and33-way distribution/control upgrade','new right fixed trunk wiring and real feedthroughs'] if STAGE!='full' else [])+['independent clearance and cable/asset audit'],'source_sha256':source_sha,'preserved_a_geometry_sha256':preserved_a_hash,'intentional_original_object_changes':sorted(set(intentional)),'parameters':P,'drawer_count':24,'hinged_bay_count':9,'net_height_mm':130,'geometry_roles':['structure','service','connector','slide_fixed','slide_moving','fastener','cable_fixed','cable_dynamic','laptop','tray','drawer_front'],'file_sizes_bytes':{'smart_cabinet.glb':(OUT/'smart_cabinet.glb').stat().st_size}}
(OUT/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('HYBRID_FIRST_CANDIDATE',OUT,flush=True)

# Independent editable single drawer, no duplicate full cabinet.
if '--no-single' not in sys.argv:
    for o in scene.objects:o.select_set(False)
    single_scene=bpy.data.scenes.new('Drawer_Compartment');bpy.context.window.scene=single_scene;scene=single_scene
    single_scene.unit_settings.system='METRIC';single_scene.unit_settings.scale_length=1
    scol=bpy.data.collections.new('Single_Drawer_Design');single_scene.collection.children.link(scol);sb=Builder(scol)
    sm={'unit':'mm','dimension_order':'width_X,depth_Y,height_Z','cabinet_dimensions_mm':[450,650,162],'dimensions_mm':[450,650,162],'access_type':'drawer','bay_ids':['S1'],'empty_bays':[],'components':{},'cable_paths':[],'usb_connections':[],'refined_drawer_configuration':P,'source_provenance':meta['source_provenance']}
    sr,st,sl=build_drawer(sb,None,'S1',.030,0,P,M,sm,True)
    # Root coordinate is the complete outer enclosure, support at30mm.
    for o in list(sr.children):o.location.z+=.030
    sr.location.z=0
    for path in sm['cable_paths']:
        for key in ['fixed','moving']:
            if path.get(key):path[key][1]+=.030
        for key in ['guide_points','guide_points_extended','parking_guide_points']:
            for pt in path.get(key,[]):pt[1]+=.030
    sb.box('SingleDrawerHousingFloor',(0,0,.0006),(.450,.650,.0012),M['white'],sr,'single:housing',bevel=.0003)
    sb.box('SingleDrawerHousingRoof',(0,0,.161),(.450,.650,.002),M['white'],sr,'single:housing',bevel=.0003)
    for x in [-.22425,.22425]:sb.box('SingleDrawerHousingSide',(x,.0075,.080),(.0015,.635,.160),M['white'],sr,'single:housing',bevel=.0003)
    sm['components']['single:housing']={'title':'独立抽屉仓壳体','dimensions_mm':[450,650,162],'basis':'model','notes':'独立单体含顶盖，外高162 mm；承托30 mm，最低顶面160 mm，净高130 mm。'}
    sdir=OUT/'single_drawer';sdir.mkdir(exist_ok=True)
    bpy.context.view_layer.update();export_root(sdir/'smart_cabinet_drawer.glb',sr,sb)
    (sdir/'drawer_compartment.json').write_text(json.dumps(sm,ensure_ascii=False,indent=2)+'\n')
    # Remove other scenes from the standalone file so it is genuinely standalone.
    for name in [o.name for o in bpy.data.objects if not under(o,sr)]:
        ob=bpy.data.objects.get(name)
        if ob:bpy.data.objects.remove(ob,do_unlink=True)
    for sc in list(bpy.data.scenes):
        if sc!=single_scene:bpy.data.scenes.remove(sc)
    bpy.ops.wm.save_as_mainfile(filepath=str(sdir/'smart_cabinet_drawer.blend'),compress=True)
    print('SINGLE_DRAWER_CANDIDATE',sdir,flush=True)
