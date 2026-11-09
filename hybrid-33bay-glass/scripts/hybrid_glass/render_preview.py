import bpy,sys,math
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];src=Path(args[0]).resolve();out=Path(args[1]).resolve();kind=args[2];final='--final' in args
bpy.ops.wm.open_mainfile(filepath=str(src));s=bpy.context.scene
variant=args[args.index('--variant')+1] if '--variant' in args else 'glass'
if variant not in {'glass','metal'}:raise ValueError('Unknown front variant')
s['drawer_front_mode']=1 if variant=='glass' else 0
s.frame_set(1);bpy.context.view_layer.update()
for o in s.objects:
 if o.type in {'LIGHT','CAMERA'}:o.hide_render=True
 if o.get('initial_hidden',False) and not o.get('drawer_front_variant'):o.hide_render=True
if kind=='drawer':
 bpy.data.objects['SingleTray'].location.y=-.32
 bpy.data.objects['SingleDrawerHousingRoof'].hide_render=True
 for o in s.objects:
  if o.name.startswith('SingleDrawerHousingSide'):o.hide_render=True
 pos=(.7,-1.25,.95);target=(0,-.12,.09);ortho=1.15
elif kind=='rear':
 for name in ['RearDoorPivot_Left','RearDoorPivot_Center','RearDoorPivot_Right']:
  for o in bpy.data.objects[name].children_recursive:o.hide_render=True
 pos=(3.2,6.8,3.0);target=(0,0,.93);ortho=4.1
else:
 pos=(4,-6.8,3.1);target=(0,0,.93);ortho=4.1
world=bpy.data.worlds.new('Preview World');s.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.7,.74,.8,1);world.node_tree.nodes['Background'].inputs[1].default_value=.22
camdata=bpy.data.cameras.new('PreviewCamera');cam=bpy.data.objects.new('PreviewCamera',camdata);s.collection.objects.link(cam);cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=ortho;s.camera=cam
for name,loc,power,size in [('Key',(-3,-4,6),850,4),('Fill',(4,-2,4),500,3),('Rim',(0,3,5),650,3)]:
 ld=bpy.data.lights.new(name,'AREA');ld.energy=power;ld.shape='DISK';ld.size=size;lo=bpy.data.objects.new(name,ld);s.collection.objects.link(lo);lo.location=(loc[0],-loc[1],loc[2]) if kind=='rear' else loc;lo.rotation_euler=(Vector(target)-lo.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='CYCLES';s.cycles.samples=64 if final else 24;s.cycles.use_denoising=True
s.render.resolution_x=2560 if final else 1280;s.render.resolution_y=1920 if final else 960;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.filepath=str(out);s.view_settings.view_transform='AgX';s.render.film_transparent=False
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='METAL'
 s.cycles.device='GPU'
except Exception:pass
bpy.ops.render.render(write_still=True)
