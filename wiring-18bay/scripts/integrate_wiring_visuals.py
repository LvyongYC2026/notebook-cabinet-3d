"""Incrementally add maintainable USB/Ethernet and fixed cabinet wiring visuals.

Blender --background --python scripts/integrate_wiring_visuals.py -- --mode single
Inputs are immutable approved assets. Outputs always go to a separate candidate.
All dimensions below are design assumptions in metres, not electrical ratings.
"""
import bpy,sys,json,math,copy,hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
def arg(k,default):return sys.argv[sys.argv.index(k)+1] if k in sys.argv else default
MODE=arg('--mode','cabinet')
OUT=Path(arg('--output',str(ROOT/'output/cabinet/wiring_candidate'))).resolve()
if MODE=='single':OUT=OUT/'single'
OUT.mkdir(parents=True,exist_ok=True)
P={'nic_wdh_mm':[28,40,18],'nic_shift_from_blue_end_mm':14,'usb_radius_mm':1.6,
   'tray_travel_mm':320,'data_radius_mm':2.1,'ac_radius_mm':2.8,
   'fixed_trunk_y_mm':282,'data_bus_height_mm':205,'ac_bus_height_mm':155,
   'duct_sheet_mm':1.0,'single_mode':MODE=='single'}
BASE=ROOT/('single_compartment/smart_cabinet_single_compartment.blend' if MODE=='single' else 'output/cabinet/smart_cabinet_18bay.blend')
META=ROOT/('single_compartment/model_metadata.json' if MODE=='single' else 'output/cabinet/components.json')
BASE=Path(arg('--base-blend',str(BASE))).resolve();META=Path(arg('--base-metadata',str(META))).resolve()
bpy.ops.wm.open_mainfile(filepath=str(BASE));scene=bpy.context.scene;scene.frame_set(1)
meta=json.loads(META.read_text());single=MODE=='single'
root=bpy.data.objects['SingleCabinetRoot' if single else 'CabinetRoot']
for ob in list(scene.objects):
 if ob.name.startswith('Studio_') or any(c.name=='Camera_Lights' for c in ob.users_collection):
  matrix=ob.matrix_world.copy();ob.parent=None;ob.matrix_world=matrix
collection=bpy.data.collections.new('Wiring_Visuals');scene.collection.children.link(collection)
created=[];routes=[];holes=[];usb_records=[]
def mat(name,color,metal=0,rough=.45):
 m=bpy.data.materials.get(name)
 if not m:
  m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
 return m
BLUE=mat('Wiring | Ethernet blue',(.018,.25,.66),.05)
PURPLE=mat('Wiring | USB violet',(.39,.075,.65),.1)
BLACK=mat('Wiring | AC and DC jacket',(.018,.025,.031))
STEEL=mat('Wiring | Satin steel',(.47,.56,.59),.7,.32)
GRAPHITE=mat('Wiring | Graphite NIC',(.045,.066,.080),.45,.3)
WHITE=mat('Wiring | White duct',(.74,.79,.80),.15)
GREEN=mat('Wiring | Active indicator',(.08,.55,.3),.1)
ORANGE=mat('Wiring | AC identifier',(.88,.34,.055))
LABEL=mat('Wiring | Lettering',(.72,.85,.90))
def component(key,title,dims,notes,bay=None):
 meta['components'][key]={'title':title,'dimensions_mm':dims,'basis':'model','notes':notes}
 if bay:meta['components'][key]['bay_id']=bay
def mark(ob,key,bay=None):
 ob['component_key']=key;ob['basis']='model';ob['wiring_design']=True
 if bay:ob['bay_id']=bay
 created.append(ob);return ob
def empty(name,parent,key,bay=None):
 ob=bpy.data.objects.new(name,None);collection.objects.link(ob);ob.parent=parent;ob.empty_display_size=.01;return mark(ob,key,bay)
def box(name,loc,dims,material,parent,key,bay=None,bevel=.0007):
 x,y,z=[v/2 for v in dims];vs=[(a*x,b*y,c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],[tuple(reversed(f)) for f in [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]]);me.materials.append(material)
 ob=bpy.data.objects.new(name,me);collection.objects.link(ob);ob.parent=parent;ob.location=loc;mark(ob,key,bay)
 if bevel:mod=ob.modifiers.new('Manufactured edge','BEVEL');mod.width=bevel;mod.segments=2
 return ob
def bezier(a,b,c,d,n=20):
 return [tuple((1-t)**3*Vector(a)+3*(1-t)**2*t*Vector(b)+3*(1-t)*t*t*Vector(c)+t**3*Vector(d)) for t in [i/n for i in range(n+1)]]
def tube_vertices(points,r,sides=8):
 out=[]
 for i,p in enumerate(points):
  tangent=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])).normalized();axis=Vector((0,0,1))
  if abs(tangent.dot(axis))>.97:axis=Vector((1,0,0))
  u=tangent.cross(axis).normalized();v=tangent.cross(u).normalized()
  for j in range(sides):out.append(tuple(Vector(p)+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides))))
 return out
def tube(name,points,r,material,parent,key,bay=None,sides=8):
 vs=tube_vertices(points,r,sides);faces=[]
 for i in range(len(points)-1):
  for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,b,b+sides,a+sides))
 faces.extend([tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))])
 me=bpy.data.meshes.new(name);me.from_pydata(vs,[],faces);me.materials.append(material)
 for f in me.polygons:f.use_smooth=True
 ob=bpy.data.objects.new(name,me);collection.objects.link(ob);ob.parent=parent;return mark(ob,key,bay)
def gltf(points):return [[x,z,-y] for x,y,z in points]
def blender(points):return [(x,-z,y) for x,y,z in points]
def length(points):return sum((Vector(b)-Vector(a)).length for a,b in zip(points,points[1:]))*1000
def min_radius(points):
 values=[]
 for a,b,c in zip(points,points[1:],points[2:]):
  ab=Vector(b)-Vector(a);bc=Vector(c)-Vector(b);ac=Vector(c)-Vector(a);cross=ab.cross(ac).length
  if cross>1e-14:values.append(ab.length*bc.length*ac.length/(2*cross)*1000)
 return min(values) if values else None
def remove_name(name):
 ob=bpy.data.objects.get(name)
 if ob:bpy.data.objects.remove(ob,do_unlink=True)
def hidden(ob,value):ob['initial_hidden']=value;ob.hide_render=value
def key(base,bay):return 'single:'+base if single else base+':'+bay
def clone_native(source,name,parent,tray,keyname,bay):
 me=bpy.data.meshes.new(name+'_mesh');me.from_pydata([v.co for v in source.data.vertices],[],[tuple(f.vertices) for f in source.data.polygons]);me.materials.clear()
 for m in source.data.materials:me.materials.append(m)
 ob=bpy.data.objects.new(name,me);collection.objects.link(ob);ob.parent=parent;mark(ob,keyname,bay)
 for old in source.data.shape_keys.key_blocks:
  sk=ob.shape_key_add(name=old.name)
  for v,w in zip(sk.data,old.data):v.co=w.co
 drive(ob,tray);return ob
def drive(ob,tray):
 sk=ob.data.shape_keys;sk.animation_data_clear();k=sk.key_blocks['TrayExtended320mm'];k.value=0
 dr=k.driver_add('value').driver;dr.type='SCRIPTED';dr.expression='min(max(-travel/0.32,0),1)';v=dr.variables.new();v.name='travel';v.type='TRANSFORMS';v.targets[0].id=tray;v.targets[0].transform_type='LOC_Y';v.targets[0].transform_space='LOCAL_SPACE'
def make_nic(bay,occupied,parent,tray,path):
 # Preserve the known U-loop. Only the final co-moving transition gently moves
 # 14mm left to a tray NIC; identical transition lengths in both shape keys.
 name='SingleDynamicCable_network' if single else 'DynamicCable_'+bay+'_network'
 ob=bpy.data.objects.get(name)
 if not ob:ob=clone_native(bpy.data.objects['DynamicCable_A1_network'],name,parent,tray,key('cables',bay),bay)
 cp=blender(path['guide_points']);ep=blender(path['guide_points_extended'])
 old_x=cp[-1][0]
 for points in [cp,ep]:
  for i in range(24):
   ix=len(points)-24+i;t=(i+1)/24;x,y,z=points[ix];points[ix]=(x-.014*(.5-.5*math.cos(math.pi*t)),y,z)
 for sk,pts in [('Basis',cp),('TrayExtended320mm',ep)]:
  vv=tube_vertices(pts,path['radius_mm']/1000,10)
  for v,w in zip(ob.data.shape_keys.key_blocks[sk].data,vv):v.co=w
 for v,w in zip(ob.data.vertices,tube_vertices(cp,path['radius_mm']/1000,10)):v.co=w
 drive(ob,tray);ob.hide_set(False);ob.hide_render=False;ob['initial_hidden']=False;ob['dynamicCable']=True;ob['cable_kind']='network'
 x,y,z=cp[-1];nic_key=key('usb_nic',bay);usb_key=key('usb',bay);nic=empty('NIC_'+bay,tray,nic_key,bay)
 # NIC occupies the clear strip left of the computer, below the fixed basket.
 nx=x-.004;ny=y+.030;nz=.057;w,d,h=[v/1000 for v in P['nic_wdh_mm']]
 body=box('NIC_'+bay+'_Housing',(nx,ny,nz),(w,d,h),GRAPHITE,nic,nic_key,bay,.002)
 body['dimensions_mm']=P['nic_wdh_mm']
 box('NIC_'+bay+'_MountFoot',(nx,ny,.04775),(w+.004,d+.006,.0015),STEEL,nic,nic_key,bay)
 for xx in [nx-w/2-.001,nx+w/2+.001]:box('NIC_'+bay+'_RetainingClip',(xx,ny,.053),(.0015,.013,.010),STEEL,nic,nic_key,bay,.0003)
 box('NIC_'+bay+'_RJ45Face',(x,y+.0101,z),(.015,.001,.010),BLACK,nic,nic_key,bay,.0002)
 plug=box('NIC_'+bay+'_EthernetPlug',(x,y+.005,z),(.012,.012,.008),BLUE,nic,nic_key,bay,.0006)
 box('NIC_'+bay+'_LinkLED',(nx+.007,ny,.0662),(.002,.004,.0007),GREEN,nic,nic_key,bay,.0002)
 # Existing computer Ethernet connector belongs to the alternative direct mode.
 for old in (["Laptop_network_Connector"] if single else [bay+'_Refined_tray_network_connector_network']):remove_name(old)
 for old in [f'ParkingCable_{bay}_network',f'ParkingPlug_{bay}_network',f'{bay}_Refined_ParkingDock_network',f'{bay}_Refined_ParkingDockClip_network']:remove_name(old)
 nic_usb=(old_x-.028,ny-d/2-.0005,.061)
 box('NIC_'+bay+'_USBDataEntry',nic_usb,(.007,.002,.005),BLACK,nic,nic_key,bay,.0002)
 # A short, controlled USB pigtail; both ends move with the same tray.
 laptop_x=old_x+.007
 end=(laptop_x-.004,-.145,.061)
 start=(nic_usb[0],nic_usb[1]-.003,.061)
 usbpts=bezier(start,(start[0],-.090,.077),(old_x-.037,-.145,.077),end,60)
 connected=empty('USBConnected_'+bay,tray,usb_key,bay)
 wire=tube('USBConnected_'+bay+'_Cable',usbpts,.0016,PURPLE,connected,usb_key,bay)
 endpoint=box('USBConnected_'+bay+'_Plug',(end[0]+.002,-.145,.061),(.012,.009,.005),PURPLE,connected,usb_key,bay,.0007)
 # The dock is on the tray, so an unplugged short USB never floats in cabinet space.
 park_end=(old_x-.036,-.178,.060)
 parked=empty('USBParked_'+bay,tray,usb_key,bay)
 pp=bezier(start,(start[0],-.105,.067),(park_end[0],-.160,.064),park_end,48)
 tube('USBParked_'+bay+'_Cable',pp,.0016,PURPLE,parked,usb_key,bay)
 box('USBParked_'+bay+'_Plug',park_end,(.012,.009,.005),PURPLE,parked,usb_key,bay,.0007)
 box('USB_'+bay+'_TrayParkingClip',(park_end[0],park_end[1],.054),(.018,.014,.004),BLACK,tray,usb_key,bay)
 for group,val in [(connected,not occupied),(parked,occupied)]:
  for item in [group,*group.children]:hidden(item,val)
 if occupied:
  lap=bpy.data.objects['Laptop' if single else 'Laptop_'+bay]
  box('Laptop_USBDataSocket_'+bay,(laptop_x,-.145,.061),(.0015,.009,.005),BLACK,lap,usb_key,bay,.0002)
 path.update({'bay_id':bay,'source_node_names':[ob.name],'moving':gltf([cp[-1]])[0],'fixed':gltf([cp[0]])[0],
  'guide_points':gltf(cp),'guide_points_extended':gltf(ep),'rest_length_mm':round(length(cp),3),'closed_length_mm':round(length(cp),3),'extended_length_mm':round(length(ep),3),
  'morph_target':'TrayExtended320mm','motion':'native_morph','stowed':False,'keep_connected_when_empty':True,'connection_mode':'tray_usb_nic',
  'parking_node_names':[],'moving_connector_node_names':[],'moving_endpoint_node':plug.name,'min_sampled_radius_mm':round(min_radius(cp),3)})
 for f in ['parking_guide_points','parking_length_mm','parking_min_sampled_radius_mm']:path.pop(f,None)
 component(nic_key,bay+' 托盘USB以太网网卡',P['nic_wdh_mm'],'28×40×18 mm为无品牌外形设计假设；USB主机侧连接电脑，RJ45经仓口接交换机。网卡留柜随盘，机型/驱动/网速待选型。',bay)
 component(usb_key,bay+' USB数据短线与随盘卡座',None,'紫色USB短线连接电脑与同托盘网卡，两端随盘；借出后电脑端停靠托盘卡座。真实上传服务另行部署。',bay)
 usb_records.append({'bay_id':bay,'nic_node':nic.name,'connected_node_names':[connected.name],'parked_node_names':[parked.name],'endpoint_plug_nodes':[endpoint.name], 'initial_occupied':occupied,'tray_node':tray.name,'connected_guide_points':gltf(usbpts),'parked_guide_points':gltf(pp),'radius_mm':1.6,'space':'tray_local_gltf','connected_min_sampled_radius_mm':round(min_radius(usbpts),3),'parked_min_sampled_radius_mm':round(min_radius(pp),3)})
 return path

ids=['S1'] if single else [s+str(n) for s in 'AB' for n in range(1,10)]
source_network=copy.deepcopy(next(p for p in meta['cable_paths'] if p['id'].endswith('_network') and not p.get('stowed')))
for bay in ids:
 par=root if single else bpy.data.objects['Bay_'+bay];tray=bpy.data.objects['SingleTray' if single else 'Tray_'+bay];occupied=single or bay not in meta['empty_bays']
 path=next(p for p in meta['cable_paths'] if p['id']==('single_network' if single else 'cable_'+bay+'_network'))
 if path.get('stowed'):
  path.clear();path.update(copy.deepcopy(source_network));path.update({'id':'cable_'+bay+'_network','component_key':'cables:'+bay,'parent_node':'Bay_'+bay,'tray_node':'Tray_'+bay})
 make_nic(bay,occupied,par,tray,path)
print('WIRING_STAGE tray NIC and USB complete',len(ids),flush=True)
if single:
 power_path=next(p for p in meta['cable_paths'] if p['id'].endswith('_power'))
 start=blender([power_path['fixed']])[0];via=(-.128,.120,.215);dock=(-.139,-.218,.240)
 pp=bezier(start,(start[0],.270,start[2]),(-.128,.270,.215),via,20)+bezier(via,(-.128,.030,.215),(-.139,-.170,.240),dock,32)[1:]
 group=empty('PowerParked_S1',root,'single:cables','S1')
 pw=tube('ParkingCable_S1_power',pp,.0024,BLACK,group,'single:cables','S1')
 pl=box('ParkingPlug_S1_power',dock,(.016,.023,.010),BLACK,group,'single:cables','S1')
 for ob in [group,pw,pl]:hidden(ob,True)
 box('PowerParking_S1_FoldedSupport',(-.181,-.218,.234),(.084,.026,.002),STEEL,root,'single:cables','S1')
 box('PowerParking_S1_EndClip',(-.148,-.218,.240),(.003,.026,.010),BLACK,root,'single:cables','S1')
 power_path.update({'bay_id':'S1','parking_node_names':[group.name],'moving_connector_node_names':['Laptop_power_Connector'],'parking_guide_points':gltf(pp),'parking_length_mm':round(length(pp),3),'parking_min_sampled_radius_mm':round(min_radius(pp),3)})

# Fixed trunk construction is kept in a separate function below so --tray-only
# can produce a reviewable first milestone without altering any source asset.
def build_fixed_wiring():
 def rounded(points,r=.025):
  # Tangent circular fillets preserve an explicit geometric bend radius;
  # short shared legs reserve half their length for each adjacent corner.
  pts=[Vector(p) for p in points];out=[tuple(pts[0])]
  for i in range(1,len(pts)-1):
   a,b,c=pts[i-1:i+2];u=a-b;v=c-b
   if min(u.length,v.length)<1e-6:continue
   un=u.normalized();vn=v.normalized();theta=math.acos(max(-1,min(1,un.dot(vn))))
   if abs(math.pi-theta)<1e-5:continue
   trim=min(r/max(math.tan(theta/2),1e-6),u.length*(.90 if i==1 else .49),v.length*(.90 if i==len(pts)-2 else .49))
   p=b+un*trim;q=b+vn*trim;center=b+(un+vn).normalized()*(trim/max(math.cos(theta/2),1e-6))
   n=un.cross(vn).normalized();rad=p-center;end=q-center
   angle=math.atan2(n.dot(rad.cross(end)),rad.dot(end));out.append(tuple(p))
   for k in range(1,11):
    t=angle*k/10;out.append(tuple(center+rad*math.cos(t)+n.cross(rad)*math.sin(t)))
  out.append(tuple(pts[-1]));return out
 def plane_point(points,axis,value,last=True):
  hits=[]
  for a,b in zip(points,points[1:]):
   if abs(b[axis]-a[axis])>1e-10 and min(a[axis],b[axis])<=value<=max(a[axis],b[axis]):
    t=(value-a[axis])/(b[axis]-a[axis]);hits.append(tuple(x+t*(y-x) for x,y in zip(a,b)))
  if not hits:raise ValueError('Route does not intersect mounting plane')
  return hits[-1 if last else 0]
 def cable(name,points,kind,parent=root,bay=None):
  k='single:fixed_'+kind if single else 'wiring:'+kind
  rr=.0028 if kind=='ac' else .0021;pts=rounded(points,.040 if kind=='ac' else (.035 if name.endswith('ExternalManagement') else .032))
  ob=tube(name,pts,rr,BLACK if kind=='ac' else BLUE,parent,k,bay)
  mr=min_radius(pts);routes.append({'name':ob.name,'kind':kind,'bay_id':bay,'parent_node':parent.name,'points_blender_m':[list(p) for p in pts],'radius_mm':rr*1000,'length_mm':round(length(pts),3),'min_sampled_radius_mm':round(mr,3) if mr is not None else None})
  return ob
 def cylinder_mesh(name,loc,r,depth,axis,material,parent,keyname,bay=None,inner=0):
  # Hollow gland / open bore: no solid cap spans the cable route.
  vs=[];faces=[];n=16
  def xyz(a,b,z):return (z,a,b) if axis=='X' else ((a,z,b) if axis=='Y' else (a,b,z))
  for rr in [r,inner or r*.62]:
   for z in [-depth/2,depth/2]:
    for i in range(n):vs.append(xyz(rr*math.cos(i*math.tau/n),rr*math.sin(i*math.tau/n),z))
  for i in range(n):
   j=(i+1)%n;faces.extend([(i,j,n+j,n+i),(2*n+j,2*n+i,3*n+i,3*n+j),(j,i,2*n+i,2*n+j),(n+i,n+j,3*n+j,3*n+i)])
  if axis=='Y':faces=[tuple(reversed(f)) for f in faces]
  me=bpy.data.meshes.new(name);me.from_pydata(vs,[],faces);me.materials.append(material)
  ob=bpy.data.objects.new(name,me);collection.objects.link(ob);ob.parent=parent;ob.location=loc;mark(ob,keyname,bay);return ob
 def fixed_side_supports(route,parent,bay,wall):
  k='single:feedthrough' if single else 'wiring:feedthrough'
  for i,yy in enumerate([.015,.105]):
   xx,_,zz=plane_point(route['points_blender_m'],1,yy);r=route['radius_mm']/1000
   if not single:xx-=parent.location.x;zz-=parent.location.z
   box('Wiring_'+bay+'_'+route['kind']+'_WallClipBracket_'+str(i),((wall+xx)/2,yy,zz-r-.002),(xx-wall,.012,.002),STEEL,parent,k,bay,.0003)
   cylinder_mesh('Wiring_'+bay+'_'+route['kind']+'_WallClip_'+str(i),(xx,yy,zz),r+.0016,.008,'Y',BLACK,parent,k,bay,inner=r+(.0004 if single else .0008))
 def cut_hole(target,center,r,axis,depth=.04,label='Service passage'):
  bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=r,depth=depth,location=center)
  cutter=bpy.context.object;cutter.name='_TemporaryBore'
  cutter.rotation_euler[1 if axis=='X' else 0]=math.pi/2 if axis in ['X','Y'] else 0
  mod=target.modifiers.new(label,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
  target.modifiers.move(len(target.modifiers)-1,0)
  bpy.context.view_layer.objects.active=target
  bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
  holes.append({'object':target.name,'center_world_blender_m':list(center),'diameter_mm':2*r*1000,'axis':axis,'purpose':label})
 def cut_rect(target,center,dims,purpose):
  bpy.ops.mesh.primitive_cube_add(size=1,location=center);cutter=bpy.context.object;cutter.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
  mod=target.modifiers.new(purpose,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;target.modifiers.move(len(target.modifiers)-1,0);bpy.context.view_layer.objects.active=target;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
  holes.append({'object':target.name,'center_world_blender_m':list(center),'rect_dimensions_mm':[v*1000 for v in dims],'purpose':purpose})
 def label(name,textvalue,loc,parent,keyname,bay=None,normal='rear',size=.007):
  cu=bpy.data.curves.new(name,'FONT');cu.body=textvalue;cu.size=size;cu.extrude=0;cu.align_x='CENTER';cu.materials.append(LABEL)
  ob=bpy.data.objects.new(name,cu);collection.objects.link(ob);ob.parent=parent;ob.location=loc;ob.rotation_euler=(math.pi/2,0,math.pi if normal=='rear' else 0);mark(ob,keyname,bay);return ob
 def duct(name,x0,x1,z,y=.283,ac=False):
  k='wiring:ducts';cx=(x0+x1)/2;w=abs(x1-x0);h=.030;depth=.040 if ac else .034
  if ac:y=.281
  # Open data tray and independently removable AC cover. Cable bores at module
  # partitions are separate real holes; no closed end-caps block a route.
  box(name+'_Backplate',(cx,y-depth/2,z),(w,.001,h),WHITE,root,k)
  for zz in [z-h/2,z+h/2]:box(name+'_Fold',(cx,y,zz),(w,depth,.001),WHITE,root,k)
  if ac:box(name+'_RemovableCover',(cx,y+depth/2,z),(w,.001,h),GRAPHITE,root,'wiring:ac_cover')
  for xx in [x0+(x1-x0)*q for q in [.15,.5,.85]]:
   box(name+'_FrameBracket',(xx,.247 if ac else .252,z),(.018,.028,.012),STEEL,root,k)
   if not ac:box(name+'_RetentionBridge',(xx,y+depth/2,z),(.009,.001,h),STEEL,root,k)
 def vertical_duct(name,x,z0,z1,ac=False):
  k='wiring:ducts';z=(z0+z1)/2;h=z1-z0
  box(name+'_Backplate',(x,.2635,z),(.026,.001,h),WHITE,root,k)
  for xx in [x-.013,x+.013]:box(name+'_Fold',(xx,.281,z),(.001,.034,h),WHITE,root,k)
  if ac:box(name+'_RemovableCover',(x,.299,z),(.026,.001,h),GRAPHITE,root,'wiring:ac_cover')
  else:
   for zz in [z0+.07,(z0+z1)/2,z1-.07]:box(name+'_RetentionBridge',(x,.299,zz),(.026,.001,.007),STEEL,root,k)

 component('single:fixed_network' if single else 'wiring:network','固定以太网主干',None,'按仓号独立星形接线；蓝线为数据，后侧固定框架走线，端接和孔洞为可视化设计，线型与布线等级待选。')
 component('single:fixed_ac' if single else 'wiring:ac','固定交流供电支路',None,'每仓1路固定AC到仓插座，适配器固定于篮；额定电流、保护器与线径尚未制造定型。')
 component('single:feedthrough' if single else 'wiring:feedthrough','固定通孔与线缆护口',None,'线缆通过实际网格开孔，护口中空；机柜模块通孔及接口孔尺寸为设计假设。')
 if single:
  # Standalone reference terminates at two rear bulkhead connectors. It does
  # not invent an external server/PDU outside the 450x650x450 envelope.
  rear=bpy.data.objects['Rear_Ventilation_24_Actual_Apertures']
  for kind,z in [('network',.300),('ac',.240)]:
   x=-.193;hole_center=(x,.32425,z);cut_hole(rear,hole_center,.006,'Y',.020,kind+' rear bulkhead')
   cylinder_mesh('SingleRear_'+kind+'_Gland',(x,.3225,z),.009,.004,'Y',BLUE if kind=='network' else BLACK,root,'single:feedthrough',inner=.004)
   # The rear-facing socket remains within the envelope. Side feed enters
   # the enclosed mounting body rather than running behind an impossible
   # 1.5mm gap between the recessed panel and the cabinet wall.
   endx=-.208 if kind=='network' else -.207
   cable('SingleFixed_'+kind,[(x,.321,z),(endx,-.083,z)],kind,root,'S1')
   fixed_side_supports(routes[-1],root,'S1',-.2235)
   cylinder_mesh('SinglePanel_'+kind+'_SideEntry',(endx,-.082,z),.0048,.010,'Y',BLACK,root,'single:feedthrough','S1',inner=.0032)
   label('SingleRear_'+kind+'_Label','NET S1' if kind=='network' else 'AC S1',(x+.045,.3245,z),root,'single:feedthrough',size=.007)
  return

 component('wiring:ducts','后侧分区线槽与固定支架',None,'数据与AC使用独立槽体；AC有可拆盖板。安装在固定框架，不挂后门；实际截面/EMC/绝缘/可维护性需深化。')
 component('wiring:ac_cover','可拆交流线槽盖板',None,'实心可拆盖板，布线查看可隐藏盖板展示内部固定AC线；不将透明显示等同物理防护。')
 component('wiring:control','18仓锁控与状态扩展端子',None,'示意18路门锁输出及两组各18路门位/锁位输入。功能容量、额定值与协议待实际模块选型，不以造型代表已验证电气能力。')
 # Remove superseded artistic central loose cables, not the controlled bay loops.
 for ob in list(bpy.data.objects):
  if ob.name.startswith(('Switch_NetworkCable','Switch_RJ45Plug','Equipment_PowerHarness','Control_Terminal')):bpy.data.objects.remove(ob,do_unlink=True)
 controller=bpy.data.objects.get('Equipment_Control12')
 if controller:controller.name='Equipment_Control18_DesignPlaceholder';controller['capacity_validated']=False
 meta['components']['controller']['notes']='18仓控制设计占位：18路锁输出＋18门位＋18锁位采集端子示意，电流/协议/扩展容量待选型验证。'
 # Terminal banks on top of the existing controller occupy otherwise clear space.
 for row,name in enumerate(['LOCK OUT','DOOR IN','LOCK IN']):
  z=.496;yy=-.036+row*.052
  box('Controller18_'+name.replace(' ','_')+'_Carrier',(.116,yy,.4905),(.153,.034,.003),GRAPHITE,root,'wiring:control',bevel=.0002)
  for i in range(18):
   xx=.044+i*.0084
   box('Controller18_'+name.replace(' ','_')+'_%02d'%(i+1),(xx,yy,z),(.0068,.028,.008),GREEN if row==0 else BLUE,root,'wiring:control',bevel=.0004)
  label('Controller18_'+str(row)+'_Label',name,(.116,yy-.015,z),root,'wiring:control',normal='front',size=.005)

 # Two horizontal base routes remain below the bay dividers and shelves.
 for side,(x0,x1) in {'A':(-1.642,-.285),'B':(.285,1.585)}.items():
  duct('Wiring_'+side+'_DataBase',x0,x1,.211,ac=False)
  duct('Wiring_'+side+'_ACBase',x0,x1,.161,ac=True)
 for xx in [-.3,.3]:
  for kind,z,rr in [('network',.211,.019),('ac',.161,.018)]:
   for ob in list(bpy.data.objects):
    if ob.name.startswith('Housing_') and '_Side' in ob.name:
     pts=[ob.matrix_world@Vector(v) for v in ob.bound_box]
     if min(v.x for v in pts)-.001<=xx<=max(v.x for v in pts)+.001:
      if kind=='ac':cut_rect(ob,(xx,.281,z),(.014,.040,.026),'Module AC rectangular bus opening')
      else:cut_hole(ob,(xx,.283,z),rr,'X',.014,'Module '+kind+' bus opening')
   if kind=='network':cylinder_mesh('Module_'+str(xx)+'_'+kind+'_EdgeGrommet',(xx,.283,z),rr+.002,.007,'X',BLACK,root,'wiring:feedthrough',inner=rr-.001)
   else:
    for yy in [.2605,.3015]:box('Wiring_Module_AC_OpeningEdge',(xx,yy,z),(.007,.0015,.028),BLACK,root,'wiring:feedthrough',bevel=.0003)
    for zz in [z-.013,z+.013]:box('Wiring_Module_AC_OpeningEdge',(xx,.281,zz),(.007,.040,.002),BLACK,root,'wiring:feedthrough',bevel=.0003)
 for side in 'AB':
  for col in range(3):
   cx=(-.975 if side=='A' else .975)+(col-1)*.45
   vertical_duct('Wiring_'+side+str(col)+'_DataRiser',cx-.164,.260,1.535,False)
   # AC rises in front of the data base channel, then enters its vertical
   # duct above the crossing. Both media retain separate physical channels.
   vertical_duct('Wiring_'+side+str(col)+'_ACRiser',cx-.199,.340,1.475,True)
   cut_rect(bpy.data.objects['Wiring_'+side+'_DataBase_Fold.001'],(cx-.164,.283,.226),(.076,.038,.012),'Data T branch '+side+str(col))
   box('Wiring_'+side+str(col)+'_DataTBackBridge',(cx-.164,.264,.243),(.076,.004,.034),WHITE,root,'wiring:ducts')
   box('Wiring_'+side+str(col)+'_BaseSupport',(cx,.256,.143),(.014,.006,.170),STEEL,root,'wiring:ducts')
   box('Wiring_'+side+str(col)+'_BaseFoot',(cx,.274,.059),(.038,.040,.002),STEEL,root,'wiring:ducts')
 # The centre-to-wing entry is a real open T junction, including the turn radius.
 for side,xx in [('A',-.300),('B',.300)]:
  cut_rect(bpy.data.objects['Wiring_'+side+'_DataBase_Fold.001'],(xx,.283,.226),(.070,.038,.012),'Central data bus T entry '+side)
 # Per-bay rear gland plate attaches to its original rear service rail. Holes
 # remain genuine even with the cover hidden for the wiring inspection mode.
 for n,bay in enumerate(ids):
  par=bpy.data.objects['Bay_'+bay];cx,_,base=par.location;row=(int(bay[1:])-1)//3;local=n%9
  plate=box('Wiring_'+bay+'_EntryPlate',(-.179,.261,.265),(.074,.0015,.104),STEEL,par,'wiring:feedthrough',bay,.0005)
  bpy.context.view_layer.update()
  for kind,z in [('network',.300),('ac',.240)]:
   endx=-.193 if kind=='network' else -.192
   cylinder_mesh('Wiring_'+bay+'_'+kind+'_SocketSideEntry',(endx,-.082,z),.0048,.010,'Y',BLACK,par,'wiring:feedthrough',bay,inner=.0032)
  for zz in [.218,.314]:
   box('Wiring_'+bay+'_PlateStandoff',(-.202,.254,zz),(.012,.018,.006),STEEL,par,'wiring:feedthrough',bay)
   box('Wiring_'+bay+'_DataMountShim',(-.164,.2623,zz),(.008,.0015,.006),STEEL,par,'wiring:feedthrough',bay)
  label('Wiring_'+bay+'_ID',bay+'  NET / AC',(-.180,.263,.270),par,'wiring:feedthrough',bay,size=.005)
  # Each data circuit begins at one actual switch front socket and ends at
  # the side entry of the fixed bay RJ45 body. Rounded intermediate segments
  # pass inside the real module holes and open rear duct volume.
  port=n+1;sr=(port-1)//12;sc=(port-1)%12;sx=-.185+sc*.033;sz=.687+sr*.021
  box('Wiring_SwitchPlug_%02d'%port,(sx,-.191,sz),(.012,.016,.009),BLUE,root,'wiring:network')
  sign=-1 if bay[0]=='A' else 1;lane_x=sign*(.274+(local%3)*.006 if bay[0]=='A' else .286-(local%3)*.006);lane_y=(.287-(local//3)*.006) if bay[0]=='A' else ([.287,.275,.281][local//3]);lane_z=(.594-(local//3)*.007) if bay[0]=='A' else ([.594,.580,.587][local//3])
  bus_z=(.205+(local%3)*.006) if bay[0]=='A' else (.217-(local%3)*.006);riser_x=cx-.170+row*.006
  front_y=(-.250-.005*n) if n<9 else (-.260+.005*(n-9) if n<12 else -.300+.005*(n-12))
  points=[(sx,-.200,sz),(sx,front_y,sz),(lane_x,front_y,sz),(lane_x,front_y,lane_z),(lane_x,lane_y,lane_z),(lane_x,lane_y,bus_z),(riser_x,lane_y,bus_z),(riser_x,lane_y,base+.300),(cx-.193,-.083,base+.300)]
  cable('FixedNetwork_'+bay,points,'network',root,bay)
  # Each controlled AC output has its own plug and fixed branch. Nine routes
  # go to each wing; no mains lead participates in tray motion.
  pcol=n%9;prow=n//9;ax=-.196+pcol*.049;az=.579+prow*.052
  box('Wiring_PDUPlug_%02d'%(n+1),(ax,.216,az),(.026,.020,.028),BLACK,root,'wiring:ac')
  ay=.267+(pcol//3)*.006+prow*.018;ac_z=(.167-(pcol%3)*.006) if prow==0 else (.155+(pcol%3)*.006);rx=cx+(-.193-row*.006 if prow==0 else -.205+row*.006);ry=.274+row*.008
  ap=[(ax,.227,az),(ax,ay,az),(ax,ay,ac_z),(rx,ay,ac_z),(rx,.180,ac_z),(rx,.180,.285),(rx,ry,.285),(rx,ry,base+.240),(cx-.192,-.083,base+.240)]
  cable('FixedAC_'+bay,ap,'ac',root,bay)
  label('Wiring_PDUBranch_%02d'%(n+1),bay,(ax,.228,az+.017),root,'wiring:ac',bay,size=.005)

 # Locate branch bores on the actual rounded centreline. The plate and
 # riser apertures are separate because the cable is still turning between them.
 for bay in ids:
  par=bpy.data.objects['Bay_'+bay];cx,_,base=par.location;col=(int(bay[1:])-1)%3
  for kind,prefix in [('network','FixedNetwork_'),('ac','FixedAC_')]:
   route=next(r for r in routes if r['name']==prefix+bay);points=route['points_blender_m']
   hr=.0075
   pos=plane_point(points,1,.261)
   cut_hole(bpy.data.objects['Wiring_'+bay+'_EntryPlate'],pos,hr,'Y',.014,bay+' '+kind+' actual route entry')
   cylinder_mesh('Wiring_'+bay+'_'+kind+'_Grommet',(pos[0]-cx,.261,pos[2]-base),hr+.002,.004,'Y',BLACK,par,'wiring:feedthrough',bay,inner=hr-.0005)
   pos=plane_point(points,1,.2635)
   target=bpy.data.objects['Wiring_'+bay[0]+str(col)+('_DataRiser_Backplate' if kind=='network' else '_ACRiser_Backplate')]
   cut_hole(target,pos,hr,'Y',.014,bay+' '+kind+' actual riser branch')
   if kind=='ac':
    pos=plane_point(points,1,.243)
    cut_hole(bpy.data.objects[bay+'_RearServiceRail'],pos,.007,'Y',.026,bay+' AC rear rail service bore')
    cylinder_mesh('Wiring_'+bay+'_ACRailBranchGland',pos,.009,.016,'Y',BLACK,root,'wiring:feedthrough',bay,inner=.0065)
   fixed_side_supports(route,par,bay,-.2235 if col==0 else -.2244)
 # One rectangular, edge-protected exit per column accommodates all three
 # AC branches, avoiding mutually overlapping individual circular glands.
 for side in 'AB':
  for col in range(3):
   names=[side+str(col+1+3*row) for row in range(3)];crossings=[]
   for bay in names:
    pts=next(r['points_blender_m'] for r in routes if r['name']=='FixedAC_'+bay)
    rx=bpy.data.objects['Bay_'+bay].location.x-.200
    # Select the low-level forward crossover, not the upper bay return.
    for a,b in zip(pts,pts[1:]):
     if min(a[1],b[1])<=.261<=max(a[1],b[1]) and a[1]!=b[1]:
      t=(.261-a[1])/(b[1]-a[1]);v=tuple(x+t*(y-x) for x,y in zip(a,b))
      if abs(v[0]-rx)<.05 and v[2]<.20:crossings.append(v)
    crossings.extend(tuple(v) for v in pts if abs(v[0]-rx)<.10 and .255<v[1]<.268 and v[2]<.20)
   x0=min(p[0] for p in crossings)-.008;x1=max(p[0] for p in crossings)+.008
   z0=min(p[2] for p in crossings)-.007;z1=max(p[2] for p in crossings)+.007
   cx=(x0+x1)/2;zz=(z0+z1)/2
   cut_rect(bpy.data.objects['Wiring_'+side+'_ACBase_Backplate'],(cx,.261,zz),(x1-x0,.018,z1-z0),'Shared AC column exit '+side+str(col))
   for x in [x0-.001,x1+.001]:box('Wiring_'+side+str(col)+'_ACSharedExit_Edge',(x,.261,zz),(.002,.003,z1-z0+.004),BLACK,root,'wiring:feedthrough',bevel=.0003)
   for z in [z0-.001,z1+.001]:box('Wiring_'+side+str(col)+'_ACSharedExit_Edge',(cx,.261,z),(x1-x0,.003,.002),BLACK,root,'wiring:feedthrough',bevel=.0003)

 # Ports19--23 visibly end on identifiable device management connectors;
 # port24 is deliberately spare. The external port is a disabled design stub.
 targets=[('Server',(.012,.111,.514)),('LockController',(.202,.075,.466)),('PDUManagement',(0,.212,.605)),('UPSManagement',(-.15,.176,.32)),('ExternalManagement',(.22,.285,.80))]
 for q,(name,end) in enumerate(targets,19):
  sr=(q-1)//12;sc=(q-1)%12;sx=-.185+sc*.033;sz=.687+sr*.021
  box('Wiring_SwitchPlug_%02d'%q,(sx,-.191,sz),(.012,.016,.009),BLUE,root,'wiring:network')
  box('Wiring_'+name+'_DataConnector',end,(.016,.014,.012),GRAPHITE,root,'wiring:network')
  # Dedicated right side management bundle avoids the PDU face and shelves.
  lane=.293;yy=.299-(q-19)*.006;front=-.270+.005*(q-19);top=.862-(q-19)*.008
  inside={'Server':.223,'LockController':.247,'PDUManagement':.217,'UPSManagement':.252}.get(name,.235)
  front_inside={'LockController':.233,'UPSManagement':.225,'PDUManagement':.2344}.get(name,.230)
  manage_points=[(sx,-.200,sz),(sx,front,sz),(lane,front,sz),(lane,front,top),(lane,yy,top)]
  if name=='LockController':manage_points += [(inside,yy,top),(inside,front_inside,top),(inside,front_inside,.600),(inside,.246,.520),(inside,.246,end[2]),(end[0],.246,end[2])]
  elif name!='ExternalManagement':manage_points += [(inside,yy,top),(inside,front_inside,top),(inside,front_inside,end[2]),(end[0],front_inside,end[2])]
  manage_points.append(end)
  cable('FixedNetwork_'+name,manage_points,'network')
  label('Wiring_'+name+'_ID',str(q)+' '+name,(end[0],end[1]+.009,end[2]+.012),root,'wiring:network',size=.005)
 box('Wiring_ExternalManagement_FixedPlate',(.22,.292,.8),(.064,.002,.04),STEEL,root,'wiring:network')
 box('Wiring_ExternalManagement_FrameBracket',(.252,.270,.781),(.012,.044,.014),STEEL,root,'wiring:network')
 box('Wiring_ExternalManagement_DisabledDustCap',(.22,.302,.8),(.018,.003,.014),BLACK,root,'wiring:network')
 # Feed architecture is explicit at rear service terminals, with a continuous
 # upstream feed to the PDU and separate UPS backed control branch.
 component('wiring:distribution','交流分支与UPS后备连接示意',None,'市电→保护/检修隔离→PDU非后备与UPS关键后备；黑护套内L/N/PE不分芯渲染。PE连续性及交流额定、过流/漏电/短路保护由电气深化验证。')
 for name,loc,txt in [('Input',(.20,.246,.135),'MAINS'),('NonBackup',(.20,.246,.30),'NON BACKUP'),('Critical',(-.05,.246,.30),'UPS / CTRL')]:
  box('Wiring_'+name+'_Terminal',loc,(.024,.020,.024),GRAPHITE,root,'wiring:distribution')
  label('Wiring_'+name+'_Tag',txt,(loc[0],loc[1]+.011,loc[2]+.018),root,'wiring:distribution',size=.005)
 cable('FixedAC_MainsToInput',[(.20,.297,.135),(.20,.246,.135)],'ac')
 cable('FixedAC_InputToDistribution',[(.20,.246,.135),(.20,.246,.30)],'ac')
 cable('FixedAC_DistributionToPDU',[(.20,.246,.30),(.290,.290,.30),(.290,.160,.30),(.290,.160,.490),(.290,.235,.490),(0,.235,.490),(0,.208,.551)],'ac')
 cable('FixedAC_DistributionToUPS',[(.20,.246,.30),(.240,.230,.30),(.240,.230,.22),(-.15,.230,.22),(-.15,.174,.22)],'ac')
 cable('FixedAC_UPSToCritical',[(-.15,.174,.26),(-.15,.233,.26),(-.05,.233,.26),(-.05,.246,.30)],'ac')
 box('Wiring_UPS_InputSocket',(-.15,.174,.22),(.025,.008,.025),BLACK,root,'wiring:distribution')
 box('Wiring_UPS_OutputSocket',(-.15,.174,.26),(.025,.008,.025),BLACK,root,'wiring:distribution')
 for name,end in [('Host',(-.18,.106,.530)),('Switch',(.18,.126,.700)),('ControlPower_ACInput',(.12,.010,.560))]:
  box('Wiring_'+name+'_PowerInlet',end,(.018,.008,.014),BLACK,root,'wiring:distribution')
  if name=='Host':pts=[(-.058,.246,.30),(-.058,.274,.34),(-.058,.274,.530),(-.058,.190,.530),(-.18,.190,.530),end]
  elif name=='Switch':pts=[(-.05,.246,.30),(-.05,.2405,.350),(.260,.2405,.350),(.260,.2405,.700),(.18,.2405,.700),end]
  else:pts=[(-.042,.246,.30),(.012,.260,.30),(.012,.260,.366),(.275,.260,.366),(.275,.260,.560),(.275,.000,.560),end]
  cable('FixedAC_CriticalTo'+name,pts,'ac')
 # The existing Equipment_DC24V housing represents the AC/DC converter.
 # Its AC input is distinct from a low-voltage DC output to the control board.
 supply=bpy.data.objects.get('Equipment_DC24V')
 if supply:supply['function']='AC input to isolated 24V DC output design placeholder';supply['rating_validated']=False
 box('Wiring_ControlPower_24VDC_Output',(.187,.011,.544),(.016,.010,.010),GREEN,root,'wiring:control')
 box('Wiring_Controller_24VDC_Input',(.201,.005,.465),(.008,.012,.012),GREEN,root,'wiring:control')
 label('Wiring_ControlPower_ACIN_Label','AC IN',(.120,.005,.574),root,'wiring:control',normal='front',size=.005)
 label('Wiring_ControlPower_DCOUT_Label','24V DC OUT',(.187,.004,.554),root,'wiring:control',normal='front',size=.004)
 dc=bezier((.187,.009,.544),(.245,.009,.544),(.245,.005,.465),(.202,.005,.465),40)
 ob=tube('FixedDC_ControlPowerToController',dc,.0015,BLACK,root,'wiring:control')
 routes.append({'name':ob.name,'kind':'dc_control','bay_id':None,'parent_node':root.name,'points_blender_m':[list(p) for p in dc],'radius_mm':1.5,'length_mm':round(length(dc),3),'min_sampled_radius_mm':round(min_radius(dc),3)})
 meta['control_power_topology']={'input':'UPS critical AC branch','converter_node':'Equipment_DC24V','ac_input_node':'Wiring_ControlPower_ACInput_PowerInlet','dc_output_node':'Wiring_ControlPower_24VDC_Output','controller_input_node':'Wiring_Controller_24VDC_Input','dc_route_node':ob.name,'output_voltage_design_v':24,'rating_validated':False}
 meta['switch_port_plan']=[{'port':i+1,'endpoint':b,'role':'bay_data'} for i,b in enumerate(ids)]+[{'port':i,'endpoint':n,'role':'device_or_management'} for i,n in enumerate(['server','lock_controller','pdu','ups','external_management'],19)]+[{'port':24,'endpoint':'spare','role':'spare'}]
if '--tray-only' not in sys.argv:build_fixed_wiring()

meta['usb_connections']=usb_records
for bay in ids:
 cable_key=key('cables',bay)
 if cable_key in meta['components']:meta['components'][cable_key]['notes']='蓝Ethernet保持连接托盘USB网卡，空仓与借出后仍随320 mm抽盘；黑DC按电脑占用切换活动/固定停车。弯曲半径与耐久需实际线型验证。'
meta['wiring_view']={'fixed_component_keys':(['single:fixed_network','single:fixed_ac','single:feedthrough'] if single else ['wiring:network','wiring:ac','wiring:ducts','wiring:feedthrough','wiring:distribution','wiring:control']),'removable_cover_component_keys':[] if single else ['wiring:ac_cover'],'description':'后侧固定框架分区走线；展开维护门查看，不分离模块。'}
meta['wiring_design']={'status':'modeled_design_proposal','parameters':P,'script':'scripts/integrate_wiring_visuals.py','fixed_routes':routes,'real_apertures':holes,'basis':'model','manufacturing_validated':False,'usb_upload_service_implemented':False}
meta['design_assumptions']=meta.get('design_assumptions',[])+['USB网卡、固定线槽与端接尺寸为设计假设；非制造/电气定型。','网卡留在托盘，空仓与借出后Ethernet仍随盘；紫USB短线电脑端停靠托盘。']
scene.frame_set(1);bpy.context.view_layer.update()
def under(o,p):
 while o:
  if o==p:return True
  o=o.parent
 return False
objects=[o for o in scene.objects if under(o,root) and o.type in {'EMPTY','MESH','CURVE','FONT'} and not o.name.startswith('Studio_') and not any(c.name=='Camera_Lights' for c in o.users_collection)]
bakes=[];dg=bpy.context.evaluated_depsgraph_get()
for ob in objects:
 if ob.type=='MESH' and ob.modifiers and not ob.data.shape_keys:
  me=bpy.data.meshes.new_from_object(ob.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
  for i,m in enumerate(me.materials):me.materials[i]=m.original if m else WHITE
  bakes.append((ob,me))
for ob,me in bakes:ob.modifiers.clear();ob.data=me
# Recalculate closed new static-mesh normals without changing native morph
# vertex order. Retain every editable object and audit signed volume below.
import bmesh
normal_audit=[]
for ob in created:
 if ob.type!='MESH' or ob.data.shape_keys:continue
 bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 vol=bm.calc_volume(signed=True)
 if vol<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces));vol=-vol
 closed=all(e.is_manifold for e in bm.edges)
 bm.to_mesh(ob.data);bm.free();ob.data.update()
 normal_audit.append({'node':ob.name,'closed_manifold':closed,'signed_volume_m3':vol})
# Share exactly identical newly-created static meshes across the 18 bays.
# Node names, hierarchy and per-object extras stay independent for interaction.
import struct
mesh_pool={};shared_meshes=0
for ob in created:
 if ob.type!='MESH' or ob.data.shape_keys:continue
 me=ob.data;h=hashlib.sha256()
 for m in me.materials:h.update((m.name if m else '').encode())
 for v in me.vertices:h.update(struct.pack('<3f',*v.co))
 for f in me.polygons:
  h.update(struct.pack('<IIB',len(f.vertices),f.material_index,int(f.use_smooth)))
  h.update(struct.pack('<'+'I'*len(f.vertices),*f.vertices))
 digest=h.digest()
 if digest in mesh_pool:ob.data=mesh_pool[digest];shared_meshes+=1
 else:mesh_pool[digest]=me
print('WIRING_SHARED_MESHES',shared_meshes,flush=True)
for ob in scene.objects:ob.select_set(False)
converted=[]
for ob in objects:
 ob.hide_set(False)
 if ob.type in {'CURVE','FONT'}:
  ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=bpy.data.meshes.new_from_object(ev)
  for i,m in enumerate(me.materials):me.materials[i]=m.original if m else WHITE
  dup=bpy.data.objects.new(ob.name+'_Mesh',me);collection.objects.link(dup);dup.parent=ob.parent;dup.matrix_local=ob.matrix_local.copy()
  for k in ob.keys():dup[k]=ob[k]
  dup.select_set(True);converted.append(dup)
 else:ob.select_set(True)
filename='smart_cabinet_single_compartment' if single else 'smart_cabinet'
bpy.ops.export_scene.gltf(filepath=str(OUT/(filename+'.glb')),export_format='GLB',use_selection=True,export_apply=False,export_animations=False,export_extras=True,export_yup=True,export_materials='EXPORT',export_cameras=False,export_lights=False,export_morph=True)
for ob in converted:bpy.data.objects.remove(ob,do_unlink=True)
for ob in objects:ob.hide_set(bool(ob.get('initial_hidden',False)))
scene.frame_set(65)
bpy.ops.object.select_all(action='DESELECT');root.select_set(True);bpy.context.view_layer.objects.active=root
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('smart_cabinet_single_compartment.blend' if single else 'smart_cabinet_18bay.blend')),compress=True)
(OUT/('model_metadata.json' if single else 'components.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
report={'mode':MODE,'status':'candidate_pending_validation','base_blend':str(BASE.relative_to(ROOT)) if BASE.is_relative_to(ROOT) else BASE.name,'base_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),'parameters':P,'created_objects':len(created),'usb_connections':len(usb_records),'network_native_count':len(ids),'fixed_routes':len(routes),'real_apertures':holes,'static_normals':{'meshes':len(normal_audit),'negative_signed_volume':sum(r['signed_volume_m3']<0 for r in normal_audit),'non_manifold':[r['node'] for r in normal_audit if not r['closed_manifold']]},'usb_radius_samples':[{k:v for k,v in r.items() if 'radius' in k or k=='bay_id'} for r in usb_records]}
(OUT/'wiring_model_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('WIRING_CANDIDATE',OUT,flush=True)
