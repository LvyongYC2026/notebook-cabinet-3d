"""Parametric single-bay product model. Local Blender 5.2 / bpy, metres internally.
Run: Blender --background --python build_smart_cabinet.py -- --preview
Run without --preview for the four full 2560x1440 Cycles images.
"""
import bpy, math, json, sys, os
from pathlib import Path
from mathutils import Vector, Matrix

OUT = Path(__file__).resolve().parent
if '--output' in sys.argv:OUT=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
PREVIEW = '--preview' in sys.argv
BUILD_ONLY = '--build-only' in sys.argv
P = {
    'width_mm':450, 'depth_mm':650, 'height_mm':450,
    'sheet_mm':1.5, 'glass_mm':6, 'door_degrees':100,
    'tray_travel_mm':320, 'laptop_mm':[320,225,18],
    'laptop_opening_degrees':105, 'tray_mm':[396,470,2],
    'network_cable_radius_mm':2.1, 'power_cable_radius_mm':2.4,
    'cable_bend_radius_mm':28,
    'interface_panel_mm':[4.5,168,250], 'interface_panel_center_mm':[-216.5,-100,254],
    'rj45_body_mm':[14,26,24], 'ac_socket_mm':[16,35,42], 'adapter_mm':[48,80,90],
    'led_center_mm':[0,-245,432], 'laptop_center_xy_mm':[25,-75], 'laptop_lid_height_mm':204,
    'resolution':[2560,1440], 'cycles_samples':96,
    'font_path':'/System/Library/Fonts/Supplemental/Arial.ttf',
}
override={}
if '--config' in sys.argv:
    cfg=Path(sys.argv[sys.argv.index('--config')+1]);override=json.loads(cfg.read_text())
    unknown=set(override)-set(P)
    if unknown:raise ValueError('Unknown configuration parameters: '+', '.join(sorted(unknown)))
    P.update(override)
for key,count,positive in [('laptop_mm',3,True),('tray_mm',3,True),('interface_panel_mm',3,True),('interface_panel_center_mm',3,False),('led_center_mm',3,False),('laptop_center_xy_mm',2,False),('rj45_body_mm',3,True),('ac_socket_mm',3,True),('adapter_mm',3,True),('resolution',2,True)]:
    value=P[key]
    if not isinstance(value,(list,tuple)) or len(value)!=count or any(not isinstance(v,(int,float)) or not math.isfinite(v) or (positive and v<=0) for v in value):
        raise ValueError(f'{key} requires {count} finite '+('positive ' if positive else '')+'numbers')
for key in ['width_mm','depth_mm','height_mm','sheet_mm','glass_mm','tray_travel_mm','cable_bend_radius_mm']:
    if not isinstance(P[key],(int,float)) or P[key]<=0:raise ValueError(key+' must be a positive number')
if not (400<=P['width_mm']<=700 and 550<=P['depth_mm']<=900 and 400<=P['height_mm']<=700):
    raise ValueError('Supported cabinet design range: width400–700, depth550–900, height400–700 mm')
if len(P['laptop_mm'])!=3 or len(P['tray_mm'])!=3:raise ValueError('laptop_mm and tray_mm require [width,depth,height]')
if P['tray_mm'][0]>P['width_mm']-40 or P['tray_mm'][1]>P['depth_mm']-120:raise ValueError('Tray exceeds reserved rail or service clearances')
if P['laptop_mm'][0]>P['tray_mm'][0]-65 or P['laptop_mm'][1]>P['tray_mm'][1]-80:raise ValueError('Laptop exceeds tray and left service allowance')
if not 90<=P['laptop_opening_degrees']<=120:raise ValueError('Laptop opening must be90–120 degrees')
if not 95<=P['door_degrees']<=110:raise ValueError('Door angle must be95–110 degrees to clear tray sweep')
if P['tray_travel_mm']>320:raise ValueError('This controlled cable design is validated for travel up to320 mm')
W,D,H = [P[k]/1000 for k in ('width_mm','depth_mm','height_mm')]
T=P['sheet_mm']/1000
if 'interface_panel_center_mm' not in override:P['interface_panel_center_mm']=[-P['width_mm']/2+8.5,-P['depth_mm']/2+225,P['height_mm']-196]
if 'led_center_mm' not in override:P['led_center_mm']=[0,-P['depth_mm']/2+80,P['height_mm']-18]
if 'laptop_center_xy_mm' not in override:P['laptop_center_xy_mm']=[25,-P['depth_mm']/2+250]
FRONT_SHIFT=(.650-D)/2
TRAVEL=P['tray_travel_mm']/1000
COL_NAMES=['Cabinet_Main','Cabinet_Door','Glass_Panel','Door_Hinges','Lock_System',
 'Laptop','Laptop_Tray','Power_Module','Network_Module','Cable_Management',
 'LED_Lighting','Ventilation','Camera_Lights']
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for co in list(bpy.data.collections): bpy.data.collections.remove(co)
COL={n:bpy.data.collections.new(n) for n in COL_NAMES}
for co in COL.values():bpy.context.scene.collection.children.link(co)
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
scene.unit_settings.scale_length=1
scene.render.engine='CYCLES';scene.cycles.samples=24 if PREVIEW else P['cycles_samples']
scene.cycles.use_denoising=True;scene.cycles.max_bounces=12
scene.cycles.transmission_bounces=8;scene.cycles.transparent_max_bounces=8
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='METAL';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='METAL'
    if any(d.use and d.type=='METAL' for d in prefs.devices):scene.cycles.device='GPU'
except Exception as exc:print('GPU fallback:',exc)
scene.render.resolution_x=1280 if PREVIEW else P['resolution'][0]
scene.render.resolution_y=720 if PREVIEW else P['resolution'][1]
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='AgX';scene.render.fps=30;scene.frame_end=180
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.82,.88,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.18

def mat(name,color,metal=0,rough=.4,emission=0,powder=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    n=m.node_tree.nodes;p=n.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal
    p.inputs['Roughness'].default_value=rough
    if emission:p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
    if powder:
        noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1700
        noise.inputs['Detail'].default_value=2
        bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.13;bump.inputs['Distance'].default_value=.000035
        m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    return m
WHITE=mat('White powder-coated steel',(.78,.80,.80),.18,.33,powder=True)
INNER=mat('Interior soft white',(.68,.72,.73),.12,.36,powder=True)
GRAPHITE=mat('Graphite service panel',(.018,.022,.027),.12,.38,powder=True)
BLACK=mat('Black polycarbonate',(.009,.014,.018),.05,.39)
RUBBER=mat('EPDM seals and cable sheath',(.008,.012,.014),0,.58)
SILVER=mat('Anodised aluminium',(.55,.59,.62),.8,.27)
STEEL=mat('Zinc plated steel',(.38,.43,.46),.78,.28)
BLUE=mat('Blue network cable and boot',(.015,.20,.50),.03,.39)
BRASS=mat('Connector contacts',(.56,.37,.12),.8,.25)
LED=mat('Warm white diffuser',(1,.84,.59),0,.24,3)
GREEN=mat('Low intensity green indicator',(.08,.50,.21),0,.25,.8)
SCREEN=mat('Unbranded locked screen',(.004,.012,.024),0,.42,.09)
SCREEN.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=.08
TEXT=mat('Subdued screen typography',(.27,.44,.50),0,.4,.15)
LABEL=mat('White markings',(.73,.79,.79),.05,.5)
GLASS=mat('Clear 6mm safety glass',(.96,.985,.99),0,.035)
g=GLASS.node_tree.nodes['Principled BSDF'];g.inputs['Transmission Weight'].default_value=1
g.inputs['IOR'].default_value=1.46
FLOOR=mat('Studio warm grey',(.68,.70,.71),0,.58)
FONT=bpy.data.fonts.load(P['font_path']) if P['font_path'] and Path(P['font_path']).is_file() else bpy.data.fonts.get('Bfont')

components={}
def component(key,title,dims,notes):
    components['single:'+key]={'title':title,'dimensions_mm':dims,'basis':'model','notes':notes}
component('housing','单仓钣金柜体',[450,650,450],'450×650×450为设计假设；1.5 mm真实板厚、折边和倒角。未做制造与强度验证。')
component('door','左铰链玻璃框门',[448,18,444],'左铰链，最大展示开启100°；门体与机构尺寸为设计示意。')
component('glass','透明安全玻璃',[390,6,390],'6 mm为文档5–6 mm评估范围内选值；透明观察窗、柔性垫及压条。')
component('hinges','双金属铰链',None,'两个同轴金属铰链；销轴和叶片独立建模。')
component('lock','嵌入拉手与门锁',None,'黑色嵌入拉手、电控锁、锁扣和门位传感器；具体型号待选。')
component('laptop','无品牌笔记本',[320,225,18],'尺寸为底座；开盖105°，银色机身。非开盖整机包络。')
component('tray','抽拉托盘',[396,470,2],'托板2 mm，含支承导轨、折边与限位；示意行程320 mm，非载荷认证。')
component('power','AC电源与独立适配器',None,'黑色AC接口与保护套；适配器位于左前独立网孔篮，篮底高于托盘扫掠区，右侧避开电脑。')
component('network','RJ45网络接口',None,'蓝色RJ45及防折保护套，统一深灰接口面板、编号和低亮状态灯。')
component('cables','强弱电分槽与活动线束',None,'蓝网线、黑电线沿侧壁独立线槽；U形余量受控，活动端随托盘移动。弯曲半径与插头需实机核验。')
component('led','暖白顶部LED',[300,20,12],'铝槽、暖白扩散罩与低压线独立建模；功率为视觉展示设置。')
component('ventilation','后部贯通散热孔',None,'后上部小块24个贯通孔，3行排列、板厚和孔壁真实建模；不代表热设计已验证。')

def link(ob,col):
    for c in list(ob.users_collection):c.objects.unlink(ob)
    COL[col].objects.link(ob);return ob
def mark(ob,key,dims=None):
    ob['component_key']='single:'+key;ob['basis']='model'
    if dims is not None:ob['dimensions_mm']=[round(v*1000,3) for v in dims]
    return ob
def empty(name,loc,col,parent=None,key=None):
    ob=bpy.data.objects.new(name,None);COL[col].objects.link(ob);ob.location=loc;ob.empty_display_size=.03
    if parent:ob.parent=parent
    if key:mark(ob,key)
    return ob
root=empty('SingleCabinetRoot',(0,0,0),'Cabinet_Main',key='housing')
root['overall_mm']=[P['width_mm'],P['depth_mm'],P['height_mm']];root['coordinate_contract']='Blender Z up, front -Y; glTF Y up, front +Z'
def box(name,loc,dims,material,col,key,parent=None,bevel=.0007):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);ob=bpy.context.object;ob.name=name;link(ob,col)
    ob.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(material);ob.parent=parent or root
    if bevel:
        b=ob.modifiers.new('Manufactured edge radius','BEVEL');b.width=min(bevel,min(dims)*.26);b.segments=3
        n=ob.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL');n.keep_sharp=True
    return mark(ob,key,dims)
def cyl(name,loc,r,depth,material,col,key,parent=None,axis='Z',vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc)
    ob=bpy.context.object;ob.name=name;link(ob,col);ob.data.materials.append(material);ob.parent=parent or root
    if axis=='X':ob.rotation_euler.y=math.pi/2
    if axis=='Y':ob.rotation_euler.x=math.pi/2
    for p in ob.data.polygons:p.use_smooth=True
    return mark(ob,key,([depth,2*r,2*r] if axis=='X' else [2*r,depth,2*r] if axis=='Y' else [2*r,2*r,depth]))
def screw(name,loc,col,key,parent=None,axis='Y',r=.0028):
    ob=cyl(name,loc,r,.0017,STEEL,col,key,parent,axis,20)
    x,y,z=loc
    if axis=='X':ds=(.0004,.0036,.00065);at=(x+.001,y,z)
    elif axis=='Y':ds=(.0036,.0004,.00065);at=(x,y-.001,z)
    else:ds=(.0036,.00065,.0004);at=(x,y,z+.001)
    box(name+'_slot',at,ds,BLACK,col,key,parent,0)
    return ob
def curve(name,points,r,material,col,key,parent=None,poly=False):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=12;cu.bevel_depth=r;cu.bevel_resolution=3
    if poly:
        sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
        for b,p in zip(sp.points,points):b.co=(*p,1)
    else:
        sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
        for b,p in zip(sp.bezier_points,points):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
    ob=bpy.data.objects.new(name,cu);COL[col].objects.link(ob);ob.parent=parent or root;cu.materials.append(material)
    return mark(ob,key)
def text(name,body,loc,size,material,col,key,parent=None,normal='front',align='LEFT'):
    cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.size=size
    if FONT:cu.font=FONT
    cu.size=size;cu.align_x=align;cu.align_y='CENTER';cu.extrude=.000015
    ob=bpy.data.objects.new(name,cu);COL[col].objects.link(ob);ob.parent=parent or root;ob.location=loc;cu.materials.append(material)
    if normal=='front':ob.rotation_euler=(math.pi/2,0,0)
    elif normal=='side':ob.rotation_euler=(math.pi/2,0,math.pi/2)
    return mark(ob,key)
def plane(name,loc,w,h,material,col,key,parent=None):
    me=bpy.data.meshes.new(name);me.from_pydata([(-w/2,0,-h/2),(w/2,0,-h/2),(w/2,0,h/2),(-w/2,0,h/2)],[],[(0,1,2,3)]);me.update()
    ob=bpy.data.objects.new(name,me);COL[col].objects.link(ob);ob.location=loc;ob.parent=parent or root;me.materials.append(material)
    return mark(ob,key,[w,0,h])

# Real sheet metal: no solid white block stands in for the enclosure.
box('Housing_Floor',(0,0,T/2),(W,D,T),WHITE,'Cabinet_Main','housing')
box('Housing_Roof',(0,0,H-T/2),(W,D,T),WHITE,'Cabinet_Main','housing')
for s in [-1,1]:
    box('Housing_LeftWall' if s<0 else 'Housing_RightWall',(s*(W/2-T/2),.0105,H/2),(T,D-.021,H-2*T),WHITE,'Cabinet_Main','housing')
    box('Housing_FrontReturn', (s*.215,-.296,H/2),(.017,T,H-.004),WHITE,'Cabinet_Main','housing')
    box('Housing_RearReturn',(s*.214,.305,H/2),(.020,T,H-.004),WHITE,'Cabinet_Main','housing')
for z in [.009,H-.009]:
    box('Housing_FrontCrossFold',(0,-.295,z),(W-.004,.032,T),WHITE,'Cabinet_Main','housing')
    box('Housing_RearCrossFold',(0,.305,z),(W-.004,.028,T),WHITE,'Cabinet_Main','housing')
for x in [-.202,.202]:
    for y in [-.27,.28]:box('MountingPad',(x,y,.0045),(.028,.032,.006),RUBBER,'Cabinet_Main','housing')

# Rear perforation panel: a welded surface grid with holes and true 1.5mm wall thickness.
holes=[]
for col in range(8):
    for row in range(3):
        cx=-.12075+col*.0345;cz=H-.105+row*.019
        holes.append((cx-.012,cx+.012,cz-.003,cz+.003))
xs=sorted(set([-W/2+T,W/2-T]+[v for h in holes for v in h[:2]]))
zs=sorted(set([T,H-T]+[v for h in holes for v in h[2:]]))
verts=[];faces=[];inds={}
def vid(x,z):
    k=(x,z)
    if k not in inds:inds[k]=len(verts);verts.append((x,D/2-T/2,z))
    return inds[k]
for xa,xb in zip(xs[:-1],xs[1:]):
    for za,zb in zip(zs[:-1],zs[1:]):
        xm=(xa+xb)/2;zm=(za+zb)/2
        if any(a<xm<b and c<zm<d for a,b,c,d in holes):continue
        faces.append((vid(xa,za),vid(xa,zb),vid(xb,zb),vid(xb,za)))
me=bpy.data.meshes.new('PerforatedRearPanelMesh');me.from_pydata(verts,[],faces);me.update()
rear=bpy.data.objects.new('Rear_Ventilation_24_Actual_Apertures',me);COL['Ventilation'].objects.link(rear);rear.parent=root;me.materials.append(WHITE)
so=rear.modifiers.new('1.5mm sheet and open hole walls','SOLIDIFY');so.thickness=T;so.offset=0
be=rear.modifiers.new('Deburred aperture edges','BEVEL');be.width=.00025;be.segments=2
rear.modifiers.new('Weighted normals','WEIGHTED_NORMAL');mark(rear,'ventilation',[.447,T,.447]);rear['actual_aperture_count']=24
for x in [-.207,.207]:
    for z in [.026,.422]:screw('RearPanel_Fastener',(x,.323,z),'Ventilation','ventilation')

# Tray, fixed support channels, captured moving rails and travel stops.
tray=empty('SingleTray',(0,0,0),'Laptop_Tray',root,'tray');tray['travel_mm']=P['tray_travel_mm'];tray['interaction']='tray'
for s in [-1,1]:
    box('Rail_Fixed_Web',(s*.207,-.012,.027),(.010,.510,.023),STEEL,'Laptop_Tray','tray')
    for z in [.015,.039]:box('Rail_Fixed_Return',(s*.203,-.012,z),(.018,.510,.0015),STEEL,'Laptop_Tray','tray')
    box('Rail_Moving',(s*.197,-.015,.033),(.008,.470,.014),SILVER,'Laptop_Tray','tray',tray)
    for y in [-.20,.12]:cyl('Slide_Roller',(s*.202,y,.032),.006,.005,BLACK,'Laptop_Tray','tray',axis='X')
    box('Slide_EndStop',(s*.204,.236,.028),(.011,.009,.018),BLACK,'Laptop_Tray','tray')
    box('Slide_FrontStop',(s*.204,-.265,.028),(.011,.008,.017),BLACK,'Laptop_Tray','tray')
    for y in [-.22,.20]:screw('Rail_MountScrew',(s*.211,y,.027),'Laptop_Tray','tray',axis='X')
box('Tray_Deck',(0,-.015,.046),(.396,.470,.002),WHITE,'Laptop_Tray','tray',tray)
box('Tray_FrontFold',(0,-.249,.039),(.396,.002,.014),WHITE,'Laptop_Tray','tray',tray)
box('Tray_RearLip',(0,.219,.053),(.396,.002,.016),WHITE,'Laptop_Tray','tray',tray)
for s in [-1,1]:box('Tray_SideFold',(s*.197,-.015,.041),(.002,.470,.010),WHITE,'Laptop_Tray','tray',tray)
box('Tray_RecessedPull',(0,-.251,.040),(.090,.003,.009),BLACK,'Laptop_Tray','tray',tray)
for x in [-.13,.15]:
    for y in [-.16,.015]:box('Laptop_RubberRest',(x,y,.0485),(.030,.025,.003),RUBBER,'Laptop_Tray','tray',tray)

# Unbranded laptop. The lid is separate and tilts 15 degrees behind vertical (105 open).
lap=empty('Laptop',(0,0,0),'Laptop',tray,'laptop')
lap['opening_degrees']=P['laptop_opening_degrees'];lap['base_dimensions_mm']=[320,225,18]
box('Laptop_LowerChassis',(.025,-.075,.059),(.320,.225,.018),SILVER,'Laptop','laptop',lap,bevel=.004)
box('Laptop_PerimeterSeam',(.025,-.075,.064),(.318,.223,.001),GRAPHITE,'Laptop','laptop',lap,bevel=.0002)
box('Laptop_UpperDeck',(.025,-.075,.0678),(.317,.222,.0016),SILVER,'Laptop','laptop',lap,bevel=.0003)
box('Keyboard_Well',(.025,-.045,.069),(.280,.108,.0015),GRAPHITE,'Laptop','laptop',lap)
for row in range(6):
    for col in range(13):
        x=.025+(col-6)*.0205;y=-.089+row*.017
        box('Key_%02d_%02d'%(row,col),(x,y,.0704),(.0175,.0135,.0014),BLACK,'Laptop','laptop',lap,bevel=.0006)
box('Laptop_Trackpad',(.025,-.151,.069),(.096,.052,.0006),STEEL,'Laptop','laptop',lap,bevel=.001)
for y in [-.134,-.113]:box('Laptop_LeftPort',(-.1355,y,.060),(.0015,.014,.006),BLACK,'Laptop','laptop',lap)
box('Laptop_RJ45Port',(-.136,-.070,.061),(.003,.015,.010),GRAPHITE,'Laptop','network',lap)
box('Laptop_PowerPort',(-.136,.006,.061),(.003,.010,.006),BLACK,'Laptop','power',lap)
for x in [-.102,.152]:cyl('Laptop_LidHingeBar',(x,.034,.069),.005,.035,STEEL,'Laptop','laptop',lap,axis='X')
lid=empty('LaptopLidPivot',(.025,.034,.070),'Laptop',lap,'laptop');lid.rotation_euler.x=math.radians(90-P['laptop_opening_degrees'])
box('Laptop_DisplayBack',(0,.001,.102),(.322,.008,.204),SILVER,'Laptop','laptop',lid,bevel=.0035)
box('Laptop_DisplayBezel',(0,-.0037,.102),(.316,.002,.198),BLACK,'Laptop','laptop',lid,bevel=.001)
plane('Laptop_LCD',(0,-.00485,.104),.300,.180,SCREEN,'Laptop','laptop',lid)
cyl('Laptop_Webcam',(0,-.0051,.197),.0015,.0005,BLACK,'Laptop','laptop',lid,axis='Y')
text('Laptop_ScreenStatus','DEVICE SECURED',(0,-.0051,.095),.005,TEXT,'Laptop','laptop',lid,align='CENTER')
text('Laptop_ScreenSubline','CONNECTION READY',(0,-.0051,.083),.0027,TEXT,'Laptop','laptop',lid,align='CENTER')
box('Laptop_LockIconBase',(0,-.0052,.124),(.011,.0004,.009),TEXT,'Laptop','laptop',lid)
curve('Laptop_LockIconArch',[(-.0036,-.0052,.128),(-.0036,-.0052,.134),(0,-.0052,.136),(.0036,-.0052,.134),(.0036,-.0052,.128)],.0006,TEXT,'Laptop','laptop',lid)

# Unified left-side dark grey service plate. +X faces the cavity, screws sit on metal.
box('ServicePanel_RecessedBezel',(-.220,.050,.254),(.004,.180,.262),STEEL,'Cabinet_Main','housing')
box('ServicePanel_GraphiteInset',(-.2165,.050,.254),(.0045,.168,.250),GRAPHITE,'Network_Module','network')
for y in [-.022,.122]:
    for z in [.140,.368]:screw('ServicePanel_M4',(-.2133,y,z),'Network_Module','network',axis='X')
text('Interface_Title','I / O  A1',(-.2138,-.012,.350),.006,LABEL,'Network_Module','network',normal='side')
text('Network_Number','LAN 01',(-.2138,-.010,.311),.0045,LABEL,'Network_Module','network',normal='side')
box('RJ45_MountingBody',(-.208,.050,.300),(.014,.026,.024),BLUE,'Network_Module','network')
box('RJ45_SocketCavity',(-.2005,.050,.300),(.0015,.016,.014),BLACK,'Network_Module','network')
for i in range(8):box('RJ45_GoldContact',(-.1995,.045+i*.0014,.304),(.001,.00055,.004),BRASS,'Network_Module','network')
box('RJ45_PluginBody',(-.193,.050,.299),(.013,.013,.010),SILVER,'Network_Module','network')
box('RJ45_BlueStrainBoot',(-.180,.050,.299),(.018,.014,.012),BLUE,'Network_Module','network',bevel=.002)
for x in [-.183,-.178,-.173]:box('RJ45_BootRib',(x,.050,.299),(.0018,.015,.013),BLUE,'Network_Module','network')
# Short molded neck overlaps the boot and fixed cable by >1mm: no floating endpoint.
cyl('RJ45_CableNeck',(-.1695,.050,.299),.0028,.005,BLUE,'Network_Module','network',axis='X')
cyl('Interface_GreenLowLED',(-.2132,.100,.327),.0026,.0015,GREEN,'Network_Module','network',axis='X')
text('AC_Number','AC 01',(-.2138,-.010,.260),.0045,LABEL,'Power_Module','power',normal='side')
box('AC_RecessedSocket',(-.207,.050,.240),(.016,.035,.042),BLACK,'Power_Module','power',bevel=.002)
box('AC_Connector',(-.192,.050,.240),(.021,.026,.030),RUBBER,'Power_Module','power',bevel=.003)
cyl('AC_CableBoot',(-.176,.050,.240),.006,.016,RUBBER,'Power_Module','power',axis='X')
text('Panel_EarthMark','PE',(-.2138,.090,.157),.004,LABEL,'Power_Module','power',normal='side')
cyl('Panel_EarthScrew',(-.2127,.112,.157),.003,.002,BRASS,'Power_Module','power',axis='X')

# Independent perforated adapter basket in the left-front service strip.
# Basket bottom86.5mm clears the entire tray sweep; right edge-153mm clears laptop-135mm.
box('Adapter_IndependentShelf',(-.183,-.100,.087),(.060,.090,.0015),WHITE,'Power_Module','power')
box('Adapter_WallMount',(-.214,-.100,.115),(.0015,.090,.058),WHITE,'Power_Module','power')
for y in [-.145,-.055]:
    for x in [-.212,-.200,-.188,-.176,-.164,-.154]:
        box('Adapter_BasketUpright',(x,y,.113),(.002,.0015,.052),WHITE,'Power_Module','power')
    for z in [.089,.102,.116,.130,.138]:
        box('Adapter_BasketCrossbar',(-.183,y,z),(.060,.0015,.0025),WHITE,'Power_Module','power')
for y in [-.132,-.068]:screw('AdapterBracket_Fastener',(-.2125,y,.126),'Power_Module','power',axis='X')
box('PowerAdapter_Block',(-.183,-.100,.135),(.048,.080,.090),BLACK,'Power_Module','power',bevel=.004)
box('PowerAdapter_RetentionBand',(-.183,-.100,.181),(.012,.083,.002),RUBBER,'Power_Module','power')
text('Adapter_Rating','DC 01',(-.202,-.1406,.157),.004,LABEL,'Power_Module','power')

# Two separate wall raceways; fixed cable sections never cross the door or sliding rails.
for name,y,z0,length in [('Network',.129,.225,.169),('Power',.176,.191,.137)]:
    box(name+'_WallRaceway',(-.218,y,z0),(.010,.018,length),INNER,'Cable_Management','cables')
    for z in [z0-length*.35,z0+length*.35]:screw(name+'_RacewayFix',(-.2118,y,z),'Cable_Management','cables',axis='X',r=.002)
network_feed=[(-.199+.031*math.cos(t*math.pi/40),-.100+.031*math.sin(t*math.pi/40),.299) for t in range(21)]
network_feed += [(-.199,.101,.299)]
network_feed += [(-.199,.101+.028*math.cos(math.pi/2-t*math.pi/40),.271+.028*math.sin(math.pi/2-t*math.pi/40)) for t in range(1,21)]
network_feed += [(-.199,.129,.094)]
network_feed += [(-.199,.157+.028*math.cos(math.pi+t*math.pi/40),.094+.028*math.sin(math.pi+t*math.pi/40)) for t in range(1,21)]
network_feed += [(-.199,.175,.066)]
curve('Network_FixedFeed',network_feed,P['network_cable_radius_mm']/1000,BLUE,'Cable_Management','cables',poly=True)
ac_feed=[(-.175+.028*math.cos(math.radians(75-i*175/32)),-.100,.212+.028*math.sin(math.radians(75-i*175/32))) for i in range(33)]
curve('AC_FixedToAdapter',ac_feed,.0028,RUBBER,'Cable_Management','cables',poly=True)
cyl('Adapter_ACInlet',(-.180,-.100,.182),.004,.008,BLACK,'Power_Module','power')
curve('Adapter_DCToGuide',[(-.183,-.055,.109),(-.188,-.042,.087),(-.213,.000,.078),(-.199,.175,.078)],P['power_cable_radius_mm']/1000,RUBBER,'Cable_Management','cables')
cyl('Adapter_DCOutlet',(-.183,-.058,.109),.003,.010,BLACK,'Power_Module','power',axis='Y')
for y,z in [(.129,.263),(.129,.164),(.176,.177),(.175,.116)]:
    box('Cable_PClipBase',(-.220,y,z),(.004,.014,.014),STEEL,'Cable_Management','cables')
    curve('Cable_PClip',[(-.216,y-.006,z-.005),(-.205,y-.006,z),(-.203,y,z+.005),(-.209,y+.006,z),(-.216,y+.006,z-.005)],.0012,BLACK,'Cable_Management','cables')

# Stable-topology cable tubes with native shape keys. The guide loop slides half as far
# as the tray, preserving its controlled U bend; no auto-run Python is needed in blend.
def lerp(a,b,n):return [tuple(Vector(a).lerp(Vector(b),i/(n-1))) for i in range(n)]
def cable_points(travel,end_y,z,port_z,xa=-.199,fixed_y=.175,loop_y=-.265,end_offset=.013):
    r=P['cable_bend_radius_mm']/1000;xb=xa+2*r;yc=(loop_y-travel*.5)
    pts=lerp((xa,fixed_y,z),(xa,yc,z),18)
    pts += [( (xa+xb)/2+r*math.cos(math.pi+i*math.pi/24),yc+r*math.sin(math.pi+i*math.pi/24),z) for i in range(1,25)]
    end=end_y-travel+end_offset
    transition=.045 if z<.070 else .080
    pts += lerp((xb,yc,z),(xb,end-transition,z),16)[1:]
    for i in range(1,25):
        t=i/24
        pts.append((xb,end-transition+transition*t,z+(port_z-z)*(.5-.5*math.cos(math.pi*t))))
    return pts
def tube_vertices(pts,r,sides=10):
    verts=[]
    for i,p in enumerate(pts):
        tang=(Vector(pts[min(i+1,len(pts)-1)])-Vector(pts[max(0,i-1)])).normalized()
        n=tang.cross(Vector((0,0,1))).normalized();b=tang.cross(n).normalized()
        for j in range(sides):verts.append(tuple(Vector(p)+r*(math.cos(j*math.tau/sides)*n+math.sin(j*math.tau/sides)*b)))
    return verts
cable_meta=[]
for kind,end_y,z,port_z,r,material in [('network',-.070,.066,.061,.0021,BLUE),('power',.006,.078,.061,.0024,RUBBER)]:
    r=P['network_cable_radius_mm' if kind=='network' else 'power_cable_radius_mm']/1000
    closed=cable_points(0,end_y,z,port_z);opened=cable_points(TRAVEL,end_y,z,port_z)
    vv=tube_vertices(closed,r);ov=tube_vertices(opened,r);ff=[];sides=10
    for i in range(len(closed)-1):
        for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;ff.append((a,b,b+sides,a+sides))
    ff += [tuple(range(sides-1,-1,-1)),tuple((len(closed)-1)*sides+j for j in range(sides))]
    mesh=bpy.data.meshes.new('Controlled_'+kind+'_Tube');mesh.from_pydata(vv,[],ff);mesh.update()
    ob=bpy.data.objects.new('SingleDynamicCable_'+kind,mesh);COL['Cable_Management'].objects.link(ob);ob.parent=root;mesh.materials.append(material)
    for face in mesh.polygons:face.use_smooth=True
    mark(ob,'cables');ob['dynamicCable']=True;ob['cable_kind']=kind
    ob.shape_key_add(name='Basis');key=ob.shape_key_add(name='TrayExtended320mm')
    for vert,co in zip(key.data,ov):vert.co=co
    fc=key.driver_add('value');dr=fc.driver;dr.type='SCRIPTED';dr.expression=f'min(max(-travel/{TRAVEL},0),1)'
    var=dr.variables.new();var.name='travel';var.type='TRANSFORMS';var.targets[0].id=tray;var.targets[0].transform_type='LOC_Y';var.targets[0].transform_space='LOCAL_SPACE'
    color='#266cac' if kind=='network' else '#141b20'
    cable_meta.append({'id':'single_'+kind,'component_key':'single:cables','space':'single_local_gltf',
        'tray_node':'SingleTray','parent_node':'SingleCabinetRoot',
        'fixed':[closed[0][0],closed[0][2],-closed[0][1]],'moving':[closed[-1][0],closed[-1][2],-closed[-1][1]],
        'guide_points':[[x,z,-y] for x,y,z in closed], 'guide_points_extended':[[x,z,-y] for x,y,z in opened],
        'radius_mm':r*1000,'color':color,'travel_mm':P['tray_travel_mm'],'bend_radius_mm':P['cable_bend_radius_mm'],
        'source_node_names':[ob.name], 'morph_target':'TrayExtended320mm',
        'rest_length_mm':round(sum((Vector(b)-Vector(a)).length for a,b in zip(closed,closed[1:]))*1000,2),
        'closed_length_mm':round(sum((Vector(b)-Vector(a)).length for a,b in zip(closed,closed[1:]))*1000,2),
        'extended_length_mm':round(sum((Vector(b)-Vector(a)).length for a,b in zip(opened,opened[1:]))*1000,2)})
    box('Laptop_'+kind+'_Connector',(-.148,end_y+.004,.061),(.030,.019,.009 if kind=='network' else .007),BLUE if kind=='network' else RUBBER,'Network_Module' if kind=='network' else 'Power_Module','network' if kind=='network' else 'power',tray)

# Recessed door assembly. Hinge pin lies on the transform pivot, all moving parts parent to it.
door=empty('SingleDoorPivot',(-.215,-.316,.225),'Cabinet_Door',root,'door')
door['interaction']='door';door['open_degrees']=-P['door_degrees']
# Left front face and both rear faces remain continuous folded sheet.
# The right outside face is a true 1.5mm perforated sheet: no white face spans the handle or LED.
for x in [0,.430]:
    for y in [-.00825,.00825]:
        if x==.430 and y<0:continue
        box('Door_VerticalFrame_Face',(x,y,0),(.018,T,.444),WHITE,'Cabinet_Door','door',door)
    for sx in [-.00825,.00825]:box('Door_VerticalFrame_Return',(x+sx,0,0),(T,.015,.444),WHITE,'Cabinet_Door','door',door)
handle_holes=[(.424,.436,-.0355,.0415),(.427,.433,.171,.177)]
hx=sorted(set([.421,.439]+[v for a,b,c,d in handle_holes for v in (a,b)]))
hz=sorted(set([-.222,.222]+[v for a,b,c,d in handle_holes for v in (c,d)]))
hverts=[];hfaces=[];hindex={}
def hvertex(x,z):
    key=(x,z)
    if key not in hindex:hindex[key]=len(hverts);hverts.append((x,-.00825,z))
    return hindex[key]
for xa,xb in zip(hx[:-1],hx[1:]):
    for za,zb in zip(hz[:-1],hz[1:]):
        if any(a<(xa+xb)/2<b and c<(za+zb)/2<d for a,b,c,d in handle_holes):continue
        hfaces.append((hvertex(xa,za),hvertex(xb,za),hvertex(xb,zb),hvertex(xa,zb)))
hmesh=bpy.data.meshes.new('RightFrontFold_RealHandleAndLEDHoles');hmesh.from_pydata(hverts,[],hfaces);hmesh.update()
hface=bpy.data.objects.new('Door_VerticalFrame_FrontPerforated',hmesh);COL['Cabinet_Door'].objects.link(hface);hface.parent=door;hmesh.materials.append(WHITE)
solid=hface.modifiers.new('Actual sheet thickness and aperture walls','SOLIDIFY');solid.thickness=T;solid.offset=0
edge=hface.modifiers.new('Deburred handle and indicator apertures','BEVEL');edge.width=.00018;edge.segments=3
hface.modifiers.new('Weighted normals','WEIGHTED_NORMAL');mark(hface,'door',[.018,T,.444])
hface['handle_aperture_mm']=[12,77];hface['indicator_aperture_mm']=[6,6]
for z in [-.213,.213]:
    for y in [-.00825,.00825]:box('Door_HorizontalFrame_Face',(.215,y,z),(.412,T,.018),WHITE,'Cabinet_Door','door',door)
    for sz in [-.00825,.00825]:box('Door_HorizontalFrame_Return',(.215,0,z+sz),(.412,.015,T),WHITE,'Cabinet_Door','door',door)

for x in [.015,.415]:box('Door_EPDM_Vertical',(x,.0035,0),(.006,.008,.400),RUBBER,'Glass_Panel','glass',door)
for z in [-.197,.197]:box('Door_EPDM_Horizontal',(.215,.0035,z),(.394,.008,.006),RUBBER,'Glass_Panel','glass',door)
box('Door_ClearGlass',(.215,.003,0),(.390,.006,.390),GLASS,'Glass_Panel','glass',door,bevel=.0006)
for x in [.022,.408]:box('Glass_RetainingStrip',(x,.0075,0),(.008,.002,.390),SILVER,'Glass_Panel','glass',door)
for z in [-.191,.191]:box('Glass_RetainingStrip',(.215,.0075,z),(.386,.002,.008),SILVER,'Glass_Panel','glass',door)
for x in [.021,.409]:
    for z in [-.181,.181]:screw('Glass_RetainerScrew',(x,.009,z),'Glass_Panel','glass',door,r=.0018)
for z in [-.152,.152]:
    cyl('Hinge_Pin',(0,0,z),.003,.054,STEEL,'Door_Hinges','hinges',door)
    for dz in [-.018,0,.018]:cyl('Hinge_Knuckle',(0,0,z+dz),.0058,.016,STEEL,'Door_Hinges','hinges',door)
    box('Hinge_DoorLeaf',(.009,.004,z),(.018,.004,.046),STEEL,'Door_Hinges','hinges',door)
    box('Hinge_FixedLeaf',(-.215,-.300,.225+z),(.016,.021,.046),STEEL,'Door_Hinges','hinges')
    for dz in [-.015,.015]:screw('Hinge_LeafScrew',(.010,-.001,z+dz),'Door_Hinges','hinges',door,r=.002)
# A recessed black cup sits behind the actual opening. Rear/sides and grasping lip
# are separate solids; the central volume remains open rather than a black decal.
box('Door_HandleCup_Back',(.430,.0055,.003),(.0118,.001,.0768),BLACK,'Lock_System','lock',door,bevel=.00025)
for x in [.42455,.43545]:box('Door_HandleCup_Side',(x,-.0006,.003),(.0009,.0132,.0768),BLACK,'Lock_System','lock',door,bevel=.0002)
for z in [-.03495,.04095]:box('Door_HandleCup_End',(.430,-.0006,z),(.010,.0132,.0009),BLACK,'Lock_System','lock',door,bevel=.0002)
box('Door_HandleGraspLip',(.430,-.0038,.023),(.010,.003,.004),RUBBER,'Lock_System','lock',door,bevel=.0007)
box('Door_LatchHousing',(.430,.015,.003),(.014,.018,.060),BLACK,'Lock_System','lock',door)
box('Door_LatchTongue',(.435,.022,.003),(.010,.004,.012),STEEL,'Lock_System','lock',door)
box('Door_FixedStrike',(.216,-.284,.228),(.014,.008,.025),STEEL,'Lock_System','lock')
box('Door_Magnet',(.428,.013,.132),(.012,.008,.012),BLACK,'Lock_System','lock',door)
box('Door_PositionSensor',(.216,-.284,.357),(.011,.010,.015),BLACK,'Lock_System','lock')
# Indicator lens passes through its own aperture and sits flush with the outside face.
cyl('Door_StatusLED_Bushing',(.430,-.0066,.174),.0035,.002,BLACK,'Lock_System','lock',door,axis='Y')
cyl('Door_StatusLED',(.430,-.00805,.174),.0027,.002,GREEN,'Lock_System','lock',door,axis='Y')
text('Door_BayLabel','A1',(.030,-.0091,.213),.009,GRAPHITE,'Cabinet_Door','door',door)
for x in [0,.430]:
    for z in [-.209,.209]:screw('Door_FrameScrew',(x,-.0075,z),'Cabinet_Door','door',door,r=.0024)

# Warm LED channel, recessed into the upper service region with a soft diffuser.
box('LED_AluminiumChannel',(0,-.070,.432),(.300,.020,.012),SILVER,'LED_Lighting','led')
box('LED_OpalDiffuser',(0,-.070,.4255),(.287,.016,.0015),LED,'LED_Lighting','led')
box('LED_FrontDiffuser',(0,-.0802,.428),(.287,.001,.004),LED,'LED_Lighting','led')
for x in [-.143,.143]:box('LED_EndCap',(x,-.070,.430),(.007,.021,.012),BLACK,'LED_Lighting','led')
curve('LED_LowVoltageWire',[(-.150,-.07,.432),(-.192,-.07,.432),(-.216,-.045,.421),(-.216,.13,.416)],.0012,RUBBER,'Cable_Management','cables')

# Independent assembly transforms keep reference detail while exposing real dimensions.
# All geometry is still separate; these transforms run before animation/export/validation.
def affine_object(ob,base,target,scale=(1,1,1)):
    m=Matrix.Translation(Vector(target)) @ Matrix.Diagonal(Vector((*scale,1))) @ Matrix.Translation(-Vector(base))
    ob.matrix_basis=m @ ob.matrix_basis

def descendants(ob):
    return [ob]+[item for child in ob.children for item in descendants(child)]
# Door frame/glass and their accessory placements respond to width and height.
door.location=(-W/2+.010,-D/2+.009,H/2)
ds=((W-.020)/.430,1,(H-.006)/.444)
for ob in list(door.children):
    affine_object(ob,(0,0,0),(0,0,0),ds)
    if ob.name.startswith('Door_VerticalFrame_Return'):ob.dimensions.x=T
    if ob.name.startswith('Door_HorizontalFrame_Return'):ob.dimensions.z=T
# Fixed structural folds retain their sheet thickness.
for ob in COL['Cabinet_Main'].objects:
    n=ob.name
    if n.startswith('Housing_FrontReturn'):
        ob.location.x=math.copysign(W/2-.010,ob.location.x);ob.location.y=-D/2+.029;ob.location.z=H/2
    elif n.startswith('Housing_RearReturn'):
        ob.location.x=math.copysign(W/2-.011,ob.location.x);ob.location.y=D/2-.020;ob.location.z=H/2
    elif n.startswith('Housing_FrontCrossFold'):ob.location.y=-D/2+.044
    elif n.startswith('Housing_RearCrossFold'):ob.location.y=D/2-.020
    elif n.startswith('MountingPad'):
        ob.location.x=math.copysign(W/2-.023,ob.location.x);ob.location.y=(-D/2+.055 if ob.location.y<0 else D/2-.045)
for ob in COL['Door_Hinges'].objects:
    if ob.parent==root:
        ob.location.x=-W/2+.010;ob.location.y+=FRONT_SHIFT;ob.location.z=H/2+(ob.location.z-.225)*ds[2]
for ob in COL['Lock_System'].objects:
    if ob.parent==root:
        ob.location.x=W/2-.009;ob.location.y+=FRONT_SHIFT;ob.location.z=H/2+(ob.location.z-.225)*ds[2]
# Moving white tray and stationary rails respond independently to tray W/D/thickness.
tsx,tsy=P['tray_mm'][0]/396,P['tray_mm'][1]/470
for ob in COL['Laptop_Tray'].objects:
    if ob!=tray:affine_object(ob,(0,-.015,.046),(0,-.015+FRONT_SHIFT,.046),(tsx,tsy,1))
tray_deck=bpy.data.objects['Tray_Deck'];tray_deck.dimensions.z=P['tray_mm'][2]/1000
tray_top_delta=(P['tray_mm'][2]-2)/2000
for ob in COL['Laptop_Tray'].objects:
    if ob.name.startswith('Laptop_RubberRest'):ob.location.z+=tray_top_delta
# Laptop chassis footprint and lid angle/height are separate editable parameters.
sx,sy=P['laptop_mm'][0]/320,P['laptop_mm'][1]/225
cx,cy=[v/1000 for v in P['laptop_center_xy_mm']]
lap.scale=(sx,sy,1);lap.location=(cx-.025*sx,cy+.075*sy,tray_top_delta)
base=bpy.data.objects['Laptop_LowerChassis'];base.dimensions.z=P['laptop_mm'][2]/1000
base.location.z=.050+P['laptop_mm'][2]/2000
height_delta=(P['laptop_mm'][2]-18)/1000
for ob in list(lap.children):
    if ob!=base:ob.location.z+=height_delta
lid.scale.z=P['laptop_lid_height_mm']/204
# Interface group is positioned from an explicit panel centre, with editable width/height.
pc=[v/1000 for v in P['interface_panel_center_mm']]
ps=[1,P['interface_panel_mm'][1]/168,P['interface_panel_mm'][2]/250]
for ob in list(COL['Network_Module'].objects)+list(COL['Power_Module'].objects)+list(COL['Cabinet_Main'].objects):
    n=ob.name
    if ob.parent!=root:continue
    if n.startswith(('ServicePanel','RJ45_','Interface_','Network_Number','AC_','Panel_Earth')):
        if n=='AC_FixedToAdapter':continue
        affine_object(ob,(-.2165,.050,.254),pc,ps)
    elif n.startswith(('Adapter_','PowerAdapter_','AdapterBracket_')):
        affine_object(ob,(-.2165,-.100,.254),pc)
plate=bpy.data.objects['ServicePanel_GraphiteInset'];plate.dimensions.x=P['interface_panel_mm'][0]/1000
# Low-voltage light location is explicit; warm light below follows the same centre.
led_delta=Vector(P['led_center_mm'])/1000-Vector((0,-.070,.432))
for ob in COL['LED_Lighting'].objects:ob.location+=led_delta
# Feed paths attach to the configured interface plate. Native moving tubes are rebuilt
# from the configured laptop side-port positions, preserving a constant-radius U bend.
for ob in COL['Cable_Management'].objects:
    if not ob.name.startswith('SingleDynamicCable'):
        ob.location+=Vector((pc[0]+.2165,pc[1]+.100,pc[2]-.254))
for ob in list(COL['Power_Module'].objects)+list(COL['Network_Module'].objects):
    if ob.parent==tray:
        affine_object(ob,(.025,-.075,.050),(cx,cy,.050+tray_top_delta+height_delta),(sx,sy,1))
for path in cable_meta:
    kind=path['id'].split('_',1)[1]
    end_base=-.070 if kind=='network' else .006
    port_x=cx+(-.136-.025)*sx
    end_y=cy+(end_base+.075)*sy
    port_z=.061+height_delta+tray_top_delta
    z=(.066 if kind=='network' else .078)+height_delta+tray_top_delta
    xa=port_x-.007-2*P['cable_bend_radius_mm']/1000
    if xa-path['radius_mm']/1000 < -W/2+.019:
        raise ValueError('Configured laptop/loop has insufficient left frame clearance; widen cabinet or reduce laptop width')
    cp=cable_points(0,end_y,z,port_z,xa,.175+FRONT_SHIFT,-.265+FRONT_SHIFT,.013*sy)
    ep=cable_points(TRAVEL,end_y,z,port_z,xa,.175+FRONT_SHIFT,-.265+FRONT_SHIFT,.013*sy)
    ob=bpy.data.objects[path['source_node_names'][0]]
    for vertex,co in zip(ob.data.vertices,tube_vertices(cp,path['radius_mm']/1000)):vertex.co=co
    for key,points in [('Basis',cp),('TrayExtended320mm',ep)]:
        for vertex,co in zip(ob.data.shape_keys.key_blocks[key].data,tube_vertices(points,path['radius_mm']/1000)):vertex.co=co
    path['fixed']=[cp[0][0],cp[0][2],-cp[0][1]];path['moving']=[cp[-1][0],cp[-1][2],-cp[-1][1]]
    path['guide_points']=[[x,z,-y] for x,y,z in cp];path['guide_points_extended']=[[x,z,-y] for x,y,z in ep]
    path['rest_length_mm']=path['closed_length_mm']=round(sum((Vector(b)-Vector(a)).length for a,b in zip(cp,cp[1:]))*1000,2)
    path['extended_length_mm']=round(sum((Vector(b)-Vector(a)).length for a,b in zip(ep,ep[1:]))*1000,2)
    feed=bpy.data.objects['Network_FixedFeed' if kind=='network' else 'Adapter_DCToGuide']
    sp=feed.data.splines[0]
    if sp.type=='POLY':sp.points[-1].co=(*(Vector(cp[0])-feed.location),1)
    else:sp.bezier_points[-1].co=Vector(cp[0])-feed.location
# Clamp fixed Bezier handles to the interior sheet envelope; this prevents automatic
# handles from taking small low-voltage wires through the metal wall.
led_wire=bpy.data.objects['LED_LowVoltageWire'];led_wire.location=led_delta
for ob in COL['Cable_Management'].objects:
    if ob.type!='CURVE':continue
    for sp in ob.data.splines:
        if sp.type!='BEZIER':continue
        for point in sp.bezier_points:
            handles=[point.handle_left.copy(),point.handle_right.copy()]
            point.handle_left_type='FREE';point.handle_right_type='FREE'
            for side,v in zip(['handle_left','handle_right'],handles):
                v.x=max(v.x,-W/2+T+ob.data.bevel_depth+.001-ob.location.x)
                setattr(point,side,v)
# Metadata matches the actual configured geometry.
components['single:housing']['dimensions_mm']=[P['width_mm'],P['depth_mm'],P['height_mm']]
components['single:housing']['notes']=f"{P['width_mm']}×{P['depth_mm']}×{P['height_mm']} mm为设计假设；{P['sheet_mm']} mm板厚、折边和倒角，未做制造强度验证。"
components['single:door']['notes']=f"左铰链，展示开启{P['door_degrees']}°；门体与机构尺寸为设计示意。"
components['single:tray']['notes']=f"托板{P['tray_mm'][2]} mm；支承导轨、折边与限位，示意行程{P['tray_travel_mm']} mm，非载荷认证。"
components['single:laptop']['notes']=f"仅底座尺寸；开盖{P['laptop_opening_degrees']}°，银色无品牌机身，非开盖整机包络。"
lap['base_dimensions_mm']=P['laptop_mm']
components['single:door']['dimensions_mm']=[round(448*ds[0],3),18,round(444*ds[2],3)]
components['single:glass']['dimensions_mm']=[round(390*ds[0],3),P['glass_mm'],round(390*ds[2],3)]
bpy.data.objects['Door_ClearGlass'].dimensions.y=P['glass_mm']/1000
components['single:tray']['dimensions_mm']=P['tray_mm']
components['single:laptop']['dimensions_mm']=P['laptop_mm']
components['single:lock']['notes']='右竖框具有真实12×77 mm拉手开孔，内置独立黑色凹盒、四周壁与抓握边；约12.5 mm内凹深度。状态灯穿独立6×6 mm安装孔。器件与孔尺寸为模型设计值。'
components['single:lock']['handle_aperture_mm']=[round(12*ds[0],3),round(77*ds[2],3)]
components['single:lock']['handle_recess_depth_mm']=12.5
components['single:lock']['indicator_aperture_mm']=[round(6*ds[0],3),round(6*ds[2],3)]
component('interface_panel','左侧统一嵌入接口面板',P['interface_panel_mm'],'XYZ尺寸：厚度沿X，面板宽度沿柜深Y，高度沿Z；独立螺丝固定、深灰喷涂面板，非选定量产器件。')
component('ac_socket','黑色AC插座体',P['ac_socket_mm'],'仅插座安装座体尺寸；插头、防折保护套及线缆独立建模。')
component('adapter','电源适配器占位',P['adapter_mm'],'仅适配器本体；无品牌，实际功率、电气规格和机型未选定。')
component('adapter_bracket','独立网孔适配器托架',[60,90,52],'托架安装在左侧，底板高于托盘扫掠区；网孔通过分立钣金条形成。')
components['single:network']['dimensions_mm']=P['rj45_body_mm']
components['single:network']['notes']='仅蓝色RJ45安装座体尺寸；编号、防折保护套、插头与网线分别建模，实际型号待定。'
for name,dims in [('RJ45_MountingBody',P['rj45_body_mm']),('AC_RecessedSocket',P['ac_socket_mm']),('PowerAdapter_Block',P['adapter_mm'])]:
    bpy.data.objects[name].dimensions=[v/1000 for v in dims]
for ob in [o for co in COL.values() for o in co.objects]:
    if ob.name.startswith(('ServicePanel','Interface_Title','Network_Number','AC_Number','Panel_Earth')):mark(ob,'interface_panel')
    elif ob.name.startswith(('AC_Recessed','AC_Connector','AC_CableBoot')):mark(ob,'ac_socket')
    elif ob.name.startswith(('PowerAdapter','Adapter_Rating')):mark(ob,'adapter')
    elif ob.name.startswith(('Adapter_Independent','Adapter_WallMount','Adapter_Basket','AdapterBracket_')):mark(ob,'adapter_bracket')

for ob in [o for co in COL.values() for o in co.objects if o.type=='MESH']:
    ob['dimensions_mm']=[round(v*1000,3) for v in ob.dimensions]

def area(name,loc,target,energy,size,size_y,color):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='RECTANGLE';data.size=size;data.size_y=size_y;data.color=color
    ob=bpy.data.objects.new(name,data);COL['Camera_Lights'].objects.link(ob);ob.location=loc
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();return ob
area('LED_Interior_Warm',tuple(Vector((0,-.068,.420))+led_delta),(0,.00,.09),4,.275,.014,(1,.80,.57))
area('Studio_Key',(.45,-.70,1.20),(0,0,.20),45,1.0,.85,(1,.97,.92))
area('Studio_Fill',(-.70,-.60,.65),(0,-.05,.22),18,.9,.75,(.83,.91,1))
area('Studio_Rim',(.30,.72,.92),(0,.05,.23),45,.85,.8,(1,.96,.90))
area('Studio_FrontSoft',(.15,-1.2,.43),(0,.0,.23),5,.75,.60,(.98,.99,1))
box('Studio_Floor',(0,0,-.015),(200,200,.025),FLOOR,'Camera_Lights','housing',bevel=0)
def camera(name,loc,target,ortho):
    data=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,data);COL['Camera_Lights'].objects.link(ob)
    ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=ortho;data.lens=50;data.clip_start=.005
    return ob
cams={
 'front_open':camera('Camera_FrontOpen',(.06,-1.85,.40),(-.045,-.14,.219),1.20),
 'internal_detail':camera('Camera_InternalDetail',(.30,-1.65,.35),(-.045,-.045,.220),.86),
 'front_view':camera('Camera_FrontView',(0,-1.75,.35),(-.030,-.035,.250),1.08),
 'door_closed':camera('Camera_DoorClosed',(.42,-1.75,.48),(0,-.04,.224),1.20),
}

# Native animation and visible pose. Tray cables use driven shape keys.
for f,a in [(1,0),(30,0),(65,-P['door_degrees']),(120,-P['door_degrees']),(180,0)]:
    door.rotation_euler.z=math.radians(a);door.keyframe_insert('rotation_euler',frame=f)
for f,t in [(1,0),(65,0),(100,-TRAVEL),(120,-TRAVEL),(155,0),(180,0)]:
    tray.location.y=t;tray.keyframe_insert('location',frame=f)
for f,label in [(1,'Closed / export'),(65,'Door 100 degrees open'),(110,'Tray 320 mm extended'),(180,'Closed')]:scene.timeline_markers.new(label,frame=f)

def bounds(objects):
    dg=bpy.context.evaluated_depsgraph_get();pts=[]
    for ob in objects:
        if ob.type in {'MESH','CURVE','FONT'}:
            ev=ob.evaluated_get(dg)
            mesh=ev.to_mesh()
            pts += [ev.matrix_world@v.co for v in mesh.vertices]
            ev.to_mesh_clear()
    return [[round(min(p[i] for p in pts)*1000,3) for i in range(3)],[round(max(p[i] for p in pts)*1000,3) for i in range(3)]]
product=[o for co in COL.values() if co.name!='Camera_Lights' for o in co.objects]
scene.frame_set(1);bpy.context.view_layer.update()
closed_bounds=bounds(product)
scene.frame_set(110);bpy.context.view_layer.update();extended_bounds=bounds(product)
scene.frame_set(1)
metadata={
 'title':'单仓精细结构模型','unit':'mm','dimension_order':['宽X','深Y','高Z'],
 'cabinet_dimensions_mm':[P['width_mm'],P['depth_mm'],P['height_mm']],'basis':'model','parameters':P,
 'coordinates':{'blender':'Z up, front -Y','gltf':'Y up, front +Z'},
 'hierarchy':{'root':'SingleCabinetRoot','door':'SingleDoorPivot','tray':'SingleTray','laptop':'Laptop'},
 'interactions':{'door':{'axis_gltf':'Y','angle_degrees':-P['door_degrees']},'tray':{'axis_gltf':'+Z','travel_mm':P['tray_travel_mm']},'laptop':{'opening_degrees':P['laptop_opening_degrees']}},
 'components':components,'cable_paths':cable_meta,
 'design_assumptions':[f"{P['width_mm']}×{P['depth_mm']}×{P['height_mm']} mm单仓外包络为设计假设，并非原文档制造定版尺寸。",f"采用{P['glass_mm']} mm玻璃、{P['tray_travel_mm']} mm行程、{P['laptop_opening_degrees']}°开盖无品牌笔记本；器件型号未确定。",'以原PDF第5页单仓场景与用户文字为主要依据；本次未收到新红框标注版，未宣称精确还原缺失标注图。','三维模型只验证视觉与部分几何关系；承载、装配公差、电气、热工与续航未实测。'],
}
triangles=0
for ob in product:
    if ob.type=='MESH':ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
validation={
 'status':'geometry_checked_render_pending','blender_version':bpy.app.version_string,
 'nominal_dimensions_mm':[P['width_mm'],P['depth_mm'],P['height_mm']], 'closed_product_bounds_xyz_mm':closed_bounds,
 'open_extended_bounds_xyz_mm':extended_bounds,'collection_names':list(COL),
 'object_counts':{'product_objects':len(product),'product_meshes':sum(o.type=='MESH' for o in product),'doors':1,'laptops':1,'trays':1,'hinges':2,'rear_apertures':24},
 'base_mesh_triangles':triangles,
 'checks':{'13_required_collections':set(COL)==set(COL_NAMES),'door_pivot_present':bool(bpy.data.objects.get('SingleDoorPivot')),
  'tray_parent_contract':lap.parent==tray,
  'laptop_open_lid_bounds_xyz_mm':bounds(descendants(lap)),
  'adapter_basket_bounds_xyz_mm':bounds([bpy.data.objects['Adapter_IndependentShelf']]),
  'tray_support_bounds_xyz_mm':bounds([o for o in COL['Laptop_Tray'].objects if o.name.startswith(('Tray_Deck','Tray_FrontFold','Tray_RearLip','Tray_SideFold'))]),
  'roof_inner_z_mm':round((H-T)*1000,3),
  'rj45_boot_short_neck':'5 mm molded neck bridges the boot to fixed network feed, with positive geometric overlap at both ends',
  'cable_closed_lengths_mm':{c['id']:c['closed_length_mm'] for c in cable_meta},
  'cable_extended_lengths_mm':{c['id']:c['extended_length_mm'] for c in cable_meta},
  'studio_export_excluded':True},
 'limitations':['No physical load, thermal, electrical, tolerance or full collision solver validation.','Door pivot and hardware are visualization design assumptions.','Open door and extended tray deliberately exceed the closed cabinet envelope.'],
}
def circumradius_mm(a,b,c):
    av,bv,cv=Vector(a),Vector(b),Vector(c)
    ab=(bv-av).length;bc=(cv-bv).length;ac=(cv-av).length;cross=(bv-av).cross(cv-bv).length
    return ab*bc*ac/(2*cross)*1000 if cross>1e-12 else None
path_checks=[]
for path in cable_meta:
    closed,opened=path['guide_points'],path['guide_points_extended']
    samples=[]
    for t in [0,.25,.5,.75,1]:
        pts=[Vector(a).lerp(Vector(b),t) for a,b in zip(closed,opened)]
        rr=[r for a,b,c in zip(pts,pts[1:],pts[2:]) if (r:=circumradius_mm(a,b,c)) is not None]
        samples.append({'travel_mm':round(t*P['tray_travel_mm'],2),'length_mm':round(sum((b-a).length for a,b in zip(pts,pts[1:]))*1000,3),'minimum_sampled_radius_mm':round(min(rr),3)})
    path_checks.append({'id':path['id'],'method':'five poses; three-point circumcircle of sampled centreline; not a cable manufacturer validation','samples':samples})
validation['cable_geometry_samples']=path_checks
validation['design_assumptions']=metadata['design_assumptions']
validation['configuration_overrides']=override

(OUT/'model_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))

# glTF exports meshes, native hierarchy, extras and the cable morph target, closed state.
# Convert curves/fonts on disposable duplicates so text and cable parts survive export.
bpy.ops.object.select_all(action='DESELECT')
export_objects=[];temporary=[]
for ob in product:
    if ob.type in {'CURVE','FONT'}:
        dup=ob.copy();dup.data=ob.data.copy();COL[ob.users_collection[0].name].objects.link(dup)
        bpy.context.view_layer.objects.active=dup;dup.select_set(True);bpy.ops.object.convert(target='MESH');dup.select_set(False)
        dup.name=ob.name+'_Mesh';temporary.append(dup);export_objects.append(dup)
    else:export_objects.append(ob)
for ob in export_objects:ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'smart_cabinet_single_compartment.glb'),export_format='GLB',use_selection=True,
 export_apply=True,export_animations=False,export_extras=True,export_yup=True,export_cameras=False,export_lights=False,
 export_materials='EXPORT',export_morph=True)
for ob in temporary:bpy.data.objects.remove(ob,do_unlink=True)

# Default .blend opens with the door open and the tray parked, hero camera selected.
scene.frame_set(65);scene.camera=cams['front_open'];scene.render.filepath=str(OUT/'render_front_open.png')
for area_ in bpy.context.screen.areas:
    if area_.type=='VIEW_3D':
        area_.spaces.active.region_3d.view_perspective='CAMERA';area_.spaces.active.shading.type='MATERIAL'
        area_.spaces.active.overlay.show_overlays=False
        area_.spaces.active.region_3d.view_camera_zoom=0
        area_.spaces.active.shading.use_scene_world=True;area_.spaces.active.shading.use_scene_lights=True
notes=bpy.data.texts.new('MODEL_README');notes.write(json.dumps(metadata,ensure_ascii=False,indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'smart_cabinet_single_compartment.blend'))
validation['file_sizes_bytes']={n:(OUT/n).stat().st_size for n in ['smart_cabinet_single_compartment.blend','smart_cabinet_single_compartment.glb']}
(OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
if not BUILD_ONLY:
    for name,frame in [('front_open',65),('internal_detail',65),('front_view',65),('door_closed',1)]:
        scene.frame_set(frame);scene.camera=cams[name]
        filename=('preview_' if PREVIEW else 'render_')+name+'.png';scene.render.filepath=str(OUT/filename)
        bpy.ops.render.render(write_still=True)
    validation['status']='preview_rendered' if PREVIEW else 'full_resolution_rendered'
    validation['render_resolution']=[scene.render.resolution_x,scene.render.resolution_y]
    validation['render_engine']='CYCLES';validation['render_samples']=scene.cycles.samples
    (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2))
print('SINGLE_COMPARTMENT_COMPLETE',str(OUT))
