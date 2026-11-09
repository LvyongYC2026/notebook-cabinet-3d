"""Build an editable room around one immutable cabinet source asset."""
import bpy,bmesh,math,json,sys,hashlib,copy
from pathlib import Path
from mathutils import Vector

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from config import ROOM,CAMERAS,SIGN_TEXTS
from setup_display_modes import apply_display_mode
from metadata import build_metadata

def arg(flag,default):return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default
BASE=Path(arg('--base-blend',str(ROOT/'output/hybrid_candidate/smart_cabinet_33bay.blend'))).resolve()
OUT=Path(arg('--output',str(ROOT/'output/hybrid_room_candidate'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
if '--config' in sys.argv:ROOM.update(json.loads(Path(arg('--config','')).read_text()))
W,D,H=ROOM['interior_wdh_m'];C=Vector(ROOM['cabinet_installation_m']);T=ROOM['wall_thickness_m']
if min(W,D,H,T)<=0:raise ValueError('Room dimensions and wall thickness must be positive')
if (W,D,H)!=(5.1,3.0,2.8):raise ValueError('This reference layout is validated only at 5.10 x 3.00 x 2.80 m; adapt furniture and clearances before changing the room size.')
source_hash=hashlib.sha256(BASE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(BASE));scene=bpy.context.scene;scene.frame_set(1)
scene['ROOM_CABINET_INSTALLATION']=list(C)
cab=bpy.data.objects['CabinetRoot']
def under(o,p):
    while o:
        if o==p:return True
        o=o.parent
    return False
cab_objects=[o for o in scene.objects if under(o,cab)]
def cabinet_signature():
    h=hashlib.sha256()
    for o in sorted(cab_objects,key=lambda x:x.name):
        h.update(o.name.encode());h.update(o.type.encode())
        if o.type=='MESH':
            for v in o.data.vertices:h.update(bytes(memoryview(__import__('array').array('f',v.co))))
            for f in o.data.polygons:h.update(bytes(memoryview(__import__('array').array('I',f.vertices))))
    return h.hexdigest()
cab_sig=cabinet_signature()
master=bpy.data.collections.new('Cabinet_Master');scene.collection.children.link(master)
for name in ['01_Product / 三模块智能柜','Wiring_Visuals','Hybrid_33_Bay_Design']:
    col=bpy.data.collections.get(name)
    if col:
        scene.collection.children.unlink(col);master.children.link(col)
studio=bpy.data.collections.get('02_Studio / 灯光与展示场景');studio.name='Studio_Environment'
ref=bpy.data.collections.get('03_Dimensions / 尺寸与净空参考（默认隐藏）')
if ref:ref.hide_render=True;ref.hide_viewport=True
room_col=bpy.data.collections.new('Room_Environment');scene.collection.children.link(room_col)
light_col=bpy.data.collections.new('Room_Lighting');scene.collection.children.link(light_col)
camera_col=bpy.data.collections.new('Room_Cameras');scene.collection.children.link(camera_col)
objects=[];groups={};materials={}

def material(name,color,rough=.5,metal=0,emission=0,texture=False):
    m=bpy.data.materials.new('Room | '+name);m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
    if emission:n.inputs['Emission Color'].default_value=(*color,1);n.inputs['Emission Strength'].default_value=emission
    if texture:
        noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=120
        bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.13;bump.inputs['Distance'].default_value=.00045
        m.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],n.inputs['Normal'])
    materials[name]=m;return m
WALL=material('Mineral warm white',(.77,.80,.80),.82,texture=True)
FLOOR=material('Gray mineral tile',(.31,.36,.39),.58,texture=True)
GROUT=material('Grout',(.12,.16,.18),.8)
WHITE=material('Powder coated white',(.79,.83,.83),.36,.15)
EDGE=material('Graphite frames',(.045,.064,.078),.4,.35)
STEEL=material('Satin aluminum',(.43,.51,.55),.32,.76)
BLACK=material('Black polymer',(.018,.025,.032),.62)
FABRIC=material('Woven chair fabric',(.08,.12,.15),.9,texture=True)
WOOD=material('Light desk laminate',(.62,.57,.46),.58)
CYAN=material('Muted cyan status',(.05,.42,.48),.32,0,.2)
SCREEN=material('Monitor deep blue',(.018,.055,.086),.46,0,.1)
INK=material('Sign lettering',(.035,.10,.15),.6)
PAPER=material('Policy board white',(.84,.87,.86),.75)
LEAF=material('Plant leaf',(.065,.22,.105),.65)
LEAF2=material('Plant leaf light',(.13,.31,.14),.6)
SOIL=material('Potting soil',(.045,.035,.025),1)
LAMP=material('Luminaire diffuser',(.93,.96,.91),.4,0,2)
GUIDE=material('Operation guide',(.1,.57,.65),.48,0,.15)

def mark(o,key,role,collision=True):
    o['component_key']=key;o['basis']='model';o['room_role']=role;o['room_collision']=collision;o['room_environment']=True;objects.append(o);return o
def empty(name,parent=None,key='room:layout',role='group'):
    o=bpy.data.objects.new(name,None);room_col.objects.link(o);o.parent=parent;mark(o,key,role,False);return o
root=empty('RoomEnvironmentRoot');root['coordinate_space']='room_global_blender'
def group(name,key,role):
    o=empty(name,root,key,role);groups[name]=o;return o
def box(name,loc,dims,mat,parent,key,role='furniture',bevel=.003,collision=True):
    x,y,z=[a/2 for a in dims];v=[(a*x,b*y,c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
    f=[tuple(reversed(a)) for a in [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]]
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.materials.append(mat);o=bpy.data.objects.new(name,me);room_col.objects.link(o);o.parent=parent;o.location=loc;mark(o,key,role,collision)
    if bevel:
        mod=o.modifiers.new('Edge radius','BEVEL');mod.width=min(bevel,min(dims)/3);mod.segments=3
        mod=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');mod.keep_sharp=True
    return o
def cylinder(name,loc,radius,depth,mat,parent,key,role='furniture',direction=(0,0,1),vertices=24,collision=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc);o=bpy.context.object;o.name=name
    for c in list(o.users_collection):c.objects.unlink(o)
    room_col.objects.link(o);o.parent=parent;o.rotation_euler=Vector(direction).to_track_quat('Z','Y').to_euler();o.data.materials.append(mat)
    mod=o.modifiers.new('Edge radius','BEVEL');mod.width=min(.002,radius/6,depth/4);mod.segments=2
    for p in o.data.polygons:p.use_smooth=True
    return mark(o,key,role,collision)
def sphere(name,loc,scale,mat,parent,key,role='furniture',collision=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=1,location=loc);o=bpy.context.object;o.name=name
    for c in list(o.users_collection):c.objects.unlink(o)
    room_col.objects.link(o);o.parent=parent;o.scale=scale;o.data.materials.append(mat)
    for f in o.data.polygons:f.use_smooth=True
    return mark(o,key,role,collision)
def beam(name,a,b,r,mat,parent,key,role='furniture'):
    a=Vector(a);b=Vector(b);return cylinder(name,(a+b)/2,r,(b-a).length,mat,parent,key,role,b-a)
font_path=Path(ROOM.get('font_path','assets/room_signage_subset.ttf'))
if not font_path.is_absolute():font_path=HERE/font_path
if not font_path.exists():raise FileNotFoundError('Bundled OFL room signage font is required: '+str(font_path))
font=bpy.data.fonts.load(str(font_path))
def label(name,text,loc,size,parent,key='room:signs',facing='front',mat=INK):
    c=bpy.data.curves.new(name,'FONT');c.body=text;c.size=size;c.align_x='CENTER';c.align_y='CENTER';c.font=font;c.extrude=.0001;c.materials.append(mat)
    o=bpy.data.objects.new(name,c);room_col.objects.link(o);o.parent=parent;o.location=loc
    o.rotation_euler=(math.pi/2,0,{'front':0,'left':math.pi/2,'right':-math.pi/2}.get(facing,0))
    return mark(o,key,'sign',False)

# Architectural envelope is built outside the specified net room dimensions.
floor=group('RoomFloor','room:floor','floor')
box('Room_Floor_Slab',(W/2,D/2,-.047),(W+2*T,D+2*T,.066),GROUT,floor,'room:floor','floor',.004,False)
for ix in range(9):
    x0=ix*.6;x1=min(W,(ix+1)*.6)
    for iy in range(5):box('Room_FloorTile_%d_%d'%(ix,iy),((x0+x1)/2,iy*.6+.3,-.007),(x1-x0-.003,.597,.014),FLOOR,floor,'room:floor','floor',.001,False)
for side in ['Back','Left','Front','Right']:group('RoomWall_'+side,'room:walls','wall')
box('Room_BackWall',(W/2,D+T/2,H/2),(W+2*T,T,H),WALL,groups['RoomWall_Back'],'room:walls','wall',.004)
box('Room_LeftWall',(-T/2,D/2,H/2),(T,D,H),WALL,groups['RoomWall_Left'],'room:walls','wall',.004)
box('Room_FrontWall',(W/2,-T/2,H/2),(W+2*T,T,H),WALL,groups['RoomWall_Front'],'room:walls','wall',.004)
for y0,y1 in [(0,.1),(1.,D)]:box('Room_RightWallSegment',(W+T/2,(y0+y1)/2,H/2),(T,y1-y0,H),WALL,groups['RoomWall_Right'],'room:walls','wall',.003)
box('Room_DoorHeaderWall',(W+T/2,.55,(H+2.1)/2),(T,.9,H-2.1),WALL,groups['RoomWall_Right'],'room:walls','wall',.003)
# Flush skirting does not reduce the stated 100 mm cabinet-to-wall rear gap.
for name,loc,dims in [('Back',(W/2,D+.004,.05),(W,.008,.1)),('Left',(-.004,D/2,.05),(.008,D,.1)),('Front',(W/2,-.004,.05),(W,.008,.1))]:box('Room_'+name+'_Skirting',loc,dims,EDGE,groups['RoomWall_'+name],'room:walls','wall',.001)
for y0,y1 in [(0,.1),(1.,D)]:box('Room_Right_Skirting',(W+.004,(y0+y1)/2,.05),(.008,y1-y0,.1),EDGE,groups['RoomWall_Right'],'room:walls','wall',.001)
roof=group('RoomRoof','room:ceiling','ceiling')
box('Room_Roof_Slab',(W/2,D/2,H+.045),(W+2*T,D+2*T,.03),WALL,roof,'room:ceiling','ceiling',.003)
for ix in range(9):
    x0=ix*.6;x1=min(W,(ix+1)*.6)
    for iy in range(5):
        if (ix,iy) not in [(2,1),(2,3),(6,1),(6,3)]:box('Room_CeilingTile_%d_%d'%(ix,iy),((x0+x1)/2,iy*.6+.3,H+.016),(x1-x0-.016,.584,.020),WHITE,roof,'room:ceiling','ceiling',.001)
for x in [0,*[i*.6 for i in range(1,9)],W]:box('Room_Ceiling_GridX',(x,D/2,H+.015),(.016,D,.03),STEEL,roof,'room:ceiling','ceiling',.0007)
for y in [i*.6 for i in range(6)]:box('Room_Ceiling_GridY',(W/2,y,H+.015),(W,.016,.03),STEEL,roof,'room:ceiling','ceiling',.0007)
for x in [1.5,3.9]:
    for y in [.9,2.1]:
        for dx in [-.2825,.2825]:box('Room_LEDPanel_Frame',(x+dx,y,H+.015),(.015,.58,.03),STEEL,roof,'room:ceiling','ceiling',.001)
        for dy in [-.2825,.2825]:box('Room_LEDPanel_Frame',(x,y+dy,H+.015),(.55,.015,.03),STEEL,roof,'room:ceiling','ceiling',.001)
        box('Room_LEDPanel_Diffuser',(x,y,H+.002),(.55,.55,.004),LAMP,roof,'room:ceiling','ceiling',.001)

security_door=group('RoomSecurityDoor','room:security_door','door')
for y in [.07,1.03]:box('Room_SecurityDoor_Jamb',(W-.004,y,1.065),(.085,.06,2.13),EDGE,security_door,'room:security_door','door',.003)
box('Room_SecurityDoor_Header',(W-.004,.55,2.13),(.085,1.02,.06),EDGE,security_door,'room:security_door','door',.003)
doorpivot=empty('RoomDoorPivot',security_door,'room:security_door','door');doorpivot.location=ROOM['door_pivot_m'];doorpivot['swing_degrees']=90
box('Room_SecurityDoor_Leaf',(0,.44,1.05),(.045,.88,2.08),EDGE,doorpivot,'room:security_door','door',.004)
box('Room_SecurityDoor_Inset',(-.023,.44,1.16),(.003,.73,1.48),BLACK,doorpivot,'room:security_door','door',.005)
for z in [.25,1.05,1.88]:cylinder('Room_SecurityDoor_Hinge',(0,.015,z),.014,.09,STEEL,doorpivot,'room:security_door','door')
box('Room_SecurityDoor_LockEscutcheon',(-.03,.75,1.05),(.014,.055,.20),STEEL,doorpivot,'room:security_door','door',.006)
beam('Room_SecurityDoor_Handle',(-.066,.65,1.05),(-.066,.79,1.05),.012,STEEL,doorpivot,'room:security_door','door')
for yy in [.65,.79]:beam('Room_SecurityDoor_HandleStand',(-.03,yy,1.05),(-.066,yy,1.05),.009,STEEL,doorpivot,'room:security_door','door')
label('Room_Door_Authorized','授权进入',(-.026,.44,1.61),.065,doorpivot,'room:security_door','right',WHITE)
doorpivot.rotation_euler.z=math.radians(ROOM['door_display_angle_degrees'])

work=group('RoomWorkstation','room:workstation','furniture')
box('Room_Desk_Top',(.4,.7,.735),(.6,1.2,.03),WOOD,work,'room:workstation',bevel=.007)
for x in [.14,.66]:
    for y in [.15,1.25]:box('Room_Desk_Leg',(x,y,.365),(.035,.035,.72),WHITE,work,'room:workstation',bevel=.004)
box('Room_Desk_RearRail',(.135,.7,.61),(.025,1.1,.05),STEEL,work,'room:workstation',bevel=.002)
box('Room_Desk_CableTray',(.18,.7,.675),(.15,.8,.035),EDGE,work,'room:workstation',bevel=.003)
box('Room_Computer_Tower',(.32,1.085,.26),(.19,.32,.43),EDGE,work,'room:workstation',bevel=.010)
box('Room_Computer_FrontPanel',(.418,1.085,.26),(.006,.28,.38),BLACK,work,'room:workstation',bevel=.002)
cylinder('Room_Computer_Status',(.423,1.17,.42),.004,.002,CYAN,work,'room:workstation',direction=(1,0,0),vertices=16)
box('Room_Monitor_Base',(.25,.75,.759),(.18,.27,.018),STEEL,work,'room:workstation',bevel=.005)
box('Room_Monitor_Stand',(.205,.75,.868),(.035,.045,.20),EDGE,work,'room:workstation',bevel=.005)
box('Room_Monitor_Frame',(.235,.75,1.085),(.032,.50,.30),EDGE,work,'room:workstation',bevel=.009)
box('Room_Monitor_Screen',(.252,.75,1.085),(.002,.47,.267),SCREEN,work,'room:workstation',bevel=.002)
box('Room_Monitor_StatusLine',(.2535,.75,.975),(.001,.30,.003),CYAN,work,'room:workstation',bevel=.0003)
box('Room_Keyboard_Base',(.52,.71,.759),(.18,.42,.018),BLACK,work,'room:workstation',bevel=.008)
for row in range(4):
    for col in range(12):box('Room_Keyboard_Key',(.46+row*.039,.535+col*.0318,.770),(.030,.027,.004),EDGE,work,'room:workstation',bevel=.001)
box('Room_Mouse_Pad',(.51,.29,.7515),(.24,.20,.003),FABRIC,work,'room:workstation',bevel=.008)
sphere('Room_Mouse',(.51,.29,.771),(.052,.033,.018),BLACK,work,'room:workstation')
cx,cy,_=ROOM['chair_center_m']
box('Room_Chair_Seat',(cx,cy,.455),(.45,.47,.075),FABRIC,work,'room:workstation',bevel=.025)
back=box('Room_Chair_Back',(cx+.215,cy,.77),(.055,.47,.45),FABRIC,work,'room:workstation',bevel=.023);back.rotation_euler.y=-.11
beam('Room_Chair_BackSupport',(cx+.12,cy,.40),(cx+.23,cy,.66),.024,EDGE,work,'room:workstation')
cylinder('Room_Chair_GasLift',(cx,cy,.28),.026,.30,STEEL,work,'room:workstation')
for i in range(5):
    a=i*math.tau/5;end=(cx+.27*math.cos(a),cy+.27*math.sin(a),.10)
    beam('Room_Chair_StarLeg',(cx,cy,.14),end,.018,EDGE,work,'room:workstation')
    cylinder('Room_Chair_Caster',(end[0],end[1],.035),.035,.034,BLACK,work,'room:workstation',direction=(math.cos(a),math.sin(a),0),vertices=16)
    cylinder('Room_Chair_CasterStem',(end[0],end[1],.08),.009,.05,EDGE,work,'room:workstation',vertices=16)
for yy in [cy-.275,cy+.275]:
    beam('Room_Chair_ArmPost',(cx+.08,yy,.43),(cx+.08,yy,.645),.014,EDGE,work,'room:workstation')
    box('Room_Chair_ArmRest',(cx+.015,yy,.65),(.28,.05,.04),BLACK,work,'room:workstation',bevel=.015)

signs=group('RoomSigns','room:signs','sign')
box('Room_Back_SignPanel',(2.55,2.991,2.36),(1.9,.016,.30),PAPER,signs,'room:signs','sign',.007,False)
label('Room_Back_ChineseSign','涉密设备管理区',(2.55,2.981,2.36),.165,signs)
box('Room_Door_SignPanel',(5.09,.55,2.38),(.018,.68,.20),EDGE,signs,'room:signs','sign',.006,False)
label('Room_Door_Title','机要室',(5.079,.55,2.40),.09,signs,facing='right',mat=WHITE)
label('Room_Door_Subtitle','ACCESS CONTROL',(5.078,.55,2.33),.022,signs,facing='right',mat=WHITE)
box('Room_PolicyBoard_Frame',(.018,1.72,1.65),(.026,.72,.86),EDGE,signs,'room:signs','sign',.006,False)
box('Room_PolicyBoard_Paper',(.033,1.72,1.65),(.004,.68,.82),PAPER,signs,'room:signs','sign',.002,False)
for text,z,size in [('保密管理要求',1.95,.064),('授权进入',1.77,.050),('规范使用',1.60,.050),('离开检查',1.43,.050)]:label('Room_Policy_'+text,text,(.036,1.72,z),size,signs,facing='left')

security=group('RoomSecurity','room:security','security_fixture')
box('Room_AccessReader_Mount',(5.092,1.16,1.42),(.016,.12,.19),STEEL,security,'room:security','security_fixture',.004)
box('Room_AccessReader_Body',(5.073,1.16,1.42),(.028,.102,.17),EDGE,security,'room:security','security_fixture',.009)
box('Room_AccessReader_Display',(5.057,1.16,1.47),(.003,.075,.035),SCREEN,security,'room:security','security_fixture',.002)
for rr in range(3):
    for cc in range(3):box('Room_AccessReader_Button',(5.056,1.134+cc*.026,1.421-rr*.023),(.004,.017,.015),STEEL,security,'room:security','security_fixture',.002)
label('Room_AccessReader_Label','门禁',(5.098,1.16,1.56),.035,security,'room:security','right')
for i,(a,b) in enumerate([((.012,.24,2.55),(.14,.24,2.51)),((4.88,.012,2.55),(4.88,.14,2.51))]):
    box('Room_CCTV_Mount_'+str(i),a,(.025,.09,.09) if i==0 else (.09,.025,.09),WHITE,security,'room:security','security_fixture',.007)
    beam('Room_CCTV_Arm_'+str(i),a,b,.012,STEEL,security,'room:security','security_fixture')
    direct=(Vector((2.55,2.10,1.20))-Vector(b)).normalized();body=Vector(b)+direct*.045
    cylinder('Room_CCTV_Housing_'+str(i),body,.044,.115,WHITE,security,'room:security','security_fixture',direct,32)
    cylinder('Room_CCTV_Lens_'+str(i),body+direct*.059,.033,.004,BLACK,security,'room:security','security_fixture',direct,24)
    cylinder('Room_CCTV_Glass_'+str(i),body+direct*.062,.019,.002,SCREEN,security,'room:security','security_fixture',direct,24)

plants=group('RoomPlants','room:plants','plant')
def plant(name,x,y,z,scale):
    cylinder(name+'_Pot',(x,y,z+.15*scale),.16*scale,.30*scale,WHITE,plants,'room:plants','plant',vertices=32)
    cylinder(name+'_Soil',(x,y,z+.30*scale),.145*scale,.012*scale,SOIL,plants,'room:plants','plant')
    for i in range(11):
        a=i*2.399;h=(.55+.045*(i%5))*scale;rad=(.14+.025*(i%3))*scale
        end=(x+rad*math.cos(a),y+rad*math.sin(a),z+.31*scale+h)
        beam(name+'_Stem',(x,y,z+.30*scale),end,.005*scale,LEAF,plants,'room:plants','plant')
        leaf=sphere(name+'_Leaf',(end[0],end[1],end[2]+.035*scale),(.045*scale,.12*scale,.015*scale),LEAF if i%2 else LEAF2,plants,'room:plants','plant');leaf.rotation_euler=(.4,i*.15,a)
plant('Room_FloorPlant',4.78,2.68,0,1)
plant('Room_DeskPlant',.38,1.16,.75,.28)

# Display-only operation marking is excluded from the environment GLB.
guide=group('RoomOperationGuide','room:layout','display_helper')
for x in [.9,4.2]:
    for j in range(12):box('Room_Operation_Dash',(x,1.05+j*.1+.035,.003),(.009,.07,.002),GUIDE,guide,'room:layout','display_helper',0,False)
for y in [1.05,2.25]:
    for j in range(33):box('Room_Operation_Dash',(.9+j*.1+.035,y,.003),(.07,.009,.002),GUIDE,guide,'room:layout','display_helper',0,False)

def area(name,loc,target,power,size):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);light_col.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
for x in [1.5,3.9]:
    for y in [.9,2.1]:area('Room_Ceiling_Light',(x,y,2.785),(x,y,0),60,.55)
area('Room_Front_SoftFill',(3.0,-3.5,4.8),(2.55,1.7,1.0),300,4.0)
area('Room_Right_SoftFill',(6.4,.4,3.8),(2.55,1.7,1.0),150,3.0)
for name,cfg in CAMERAS.items():
    data=bpy.data.cameras.new('Camera_Room_'+name);o=bpy.data.objects.new('Camera_Room_'+name,data);camera_col.objects.link(o);o.location=cfg['position'];o.rotation_euler=(Vector(cfg['target'])-o.location).to_track_quat('-Z','Y').to_euler();data.lens=cfg.get('lens_mm',46);data.clip_start=.02;data.clip_end=100
    if cfg['projection']=='orthographic':data.type='ORTHO';data.ortho_scale=cfg['ortho_scale_m']
    if name=='top':o.rotation_euler=(0,0,0)
text=bpy.data.texts.new('display_modes.py');text.write((HERE/'setup_display_modes.py').read_text())
scene['room_installation_note']='100 mm rear gap: move cabinet before rear maintenance.'
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.render.resolution_x=2560;scene.render.resolution_y=1440;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.4
apply_display_mode('ROOM','overview')

# Export only the new environment. Temporarily offset each root child so that
# the exported root remains identity and existing cabinet-local web APIs work.
room_meshes=[o for o in objects if o.type in {'MESH','FONT'} and o.get('room_role')!='display_helper']
room_nodes=[o for o in objects if o.get('room_role')!='display_helper' and not under(o,guide)]
locations={o.name:o.location.copy() for o in root.children}
for o in root.children:o.location-=C
for o in scene.objects:o.select_set(False)
converted=[]
for o in room_nodes:
    o.hide_set(False)
    if o.type=='FONT':
        ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=bpy.data.meshes.new_from_object(ev);du=bpy.data.objects.new(o.name+'_Mesh',me);room_col.objects.link(du);du.parent=o.parent;du.matrix_local=o.matrix_local.copy()
        for k in o.keys():du[k]=o[k]
        du.select_set(True);converted.append(du)
    else:o.select_set(True)
bpy.context.view_layer.update()
export_points=[]
for o in [*room_meshes,*converted]:
    if o.type=='FONT':continue
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    export_points += [ev.matrix_world@Vector(v) for v in ev.bound_box]
lo=[min(v[i] for v in export_points) for i in range(3)];hi=[max(v[i] for v in export_points) for i in range(3)]
export_bounds={'min':[lo[0],lo[2],-hi[1]],'max':[hi[0],hi[2],-lo[1]]}
root['coordinate_space']='cabinet_local_gltf'
bpy.ops.export_scene.gltf(filepath=str(OUT/'room_environment.glb'),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_extras=True,export_yup=True,export_cameras=False,export_lights=False)
root['coordinate_space']='room_global_blender'
for o in converted:bpy.data.objects.remove(o,do_unlink=True)
for o in root.children:o.location=locations[o.name]
bpy.context.view_layer.update()
assert cabinet_signature()==cab_sig,'Cabinet mesh geometry changed unexpectedly'
meta_path=OUT/'room_metadata.json'
meta=build_metadata(ROOM,CAMERAS)
meta.update(status='modeled_candidate',root_node=root.name,cabinet_source_sha256=source_hash,cabinet_mesh_signature=cab_sig,source_script='scripts/hybrid_room/build_room.py',room_parameters={k:v for k,v in ROOM.items() if k!='font_path'})
meta['cabinet_geometry_unchanged']=True
meta['environment_nodes']=[{'name':o.name,'room_role':o.get('room_role'),'room_collision':bool(o.get('room_collision')),'component_key':o.get('component_key')} for o in room_meshes]
meta['geometry_bounds_m']=export_bounds
meta['reference_layout']={'door_wall':'right','door_opening_y_mm':[100,1000],'door_opening_height_mm':2100,'nominal_door_to_operation_zone_gap_mm':50,'desk_global_blender_bounds_m':ROOM['desk_bounds_m'],'chair_center_global_blender_m':ROOM['chair_center_m']}
meta['font']={'path':'scripts/hybrid_room/assets/room_signage_subset.ttf','license':'SIL OFL 1.1','source':'https://github.com/google/fonts/tree/main/ofl/notosanssc','texts':SIGN_TEXTS}
meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
apply_display_mode('ROOM','overview')
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':a.spaces.active.overlay.show_overlays=False;a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT');cab.select_set(True);bpy.context.view_layer.objects.active=cab
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'smart_cabinet_room_and_product.blend'),compress=True)
report={'source_blend':str(BASE.relative_to(ROOT)) if BASE.is_relative_to(ROOT) else BASE.name,'source_sha256':source_hash,'cabinet_object_count':len(cab_objects),'cabinet_mesh_signature_before_after':cab_sig,'cabinet_instances':1,'cabinet_scale':list(cab.scale),'cabinet_room_position':list(cab.location),'room_mesh_count':len(room_meshes),'glb_contains_cabinet':False,'font_license':'SIL OFL 1.1','status':'awaiting_independent_installation_audit'}
(OUT/'room_build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('ROOM_ENVIRONMENT_READY',OUT,flush=True)
