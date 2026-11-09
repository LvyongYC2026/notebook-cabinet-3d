"""Read-only perspective product and drawer-context previews."""
import bpy, math, sys
from pathlib import Path
from mathutils import Vector
argv=sys.argv[sys.argv.index('--')+1:]
source,out=map(Path,argv[:2]);context='--drawer' in argv;whole='--whole' in argv;final='--final' in argv
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()));s=bpy.context.scene
s['drawer_front_mode']=1;s.frame_set(1)
model=bpy.data.objects['CabinetRoot' if whole else 'SingleDrawerRoot'];root=model if whole else bpy.data.objects['Laptop']
def under(obj,parent):
    while obj:
        if obj==parent:return True
        obj=obj.parent
    return False
for obj in s.objects:
    if obj.animation_data:
        for curve in obj.animation_data.drivers:
            if curve.data_path in {'hide_viewport','hide_render'}:curve.mute=True
    if obj.get('drawer_front_variant'):obj.hide_render=obj['drawer_front_variant']!='glass'
    if obj.type in {'LIGHT','CAMERA'}:obj.hide_render=True
    if obj.type in {'MESH','FONT','CURVE'} and (not under(obj,model) or (not context and not whole and not under(obj,root))):obj.hide_render=True
    if obj.get('initial_hidden',False) and not obj.get('drawer_front_variant'):obj.hide_render=True
if whole:
    bpy.data.objects['Tray_B24'].location.y=-.32
    target=Vector((0,-.10,.93));pos=Vector((2.9,-6.2,2.7));lens=65;floor_z=-.004
elif context:
    bpy.data.objects['SingleTray'].location.y=-.32
    for obj in s.objects:
        if obj.name.startswith(('SingleDrawerHousingRoof','SingleDrawerHousingSide')):obj.hide_render=True
    target=Vector((0,-.20,.10));pos=Vector((.85,-1.45,1.00));lens=52;floor_z=-.002
else:
    target=Vector((.03,-.15,.048));pos=Vector((.48,-.64,.43));lens=65;floor_z=.0299
bpy.context.view_layer.update()
world=bpy.data.worlds.new('Laptop Style Preview World');s.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.69,.74,1);world.node_tree.nodes['Background'].inputs[1].default_value=.22
camdata=bpy.data.cameras.new('StylePerspectiveCamera');cam=bpy.data.objects.new('StylePerspectiveCamera',camdata);s.collection.objects.link(cam)
cam.location=pos;cam.rotation_euler=(target-pos).to_track_quat('-Z','Y').to_euler();camdata.type='PERSP';camdata.lens=lens;s.camera=cam
lighting=[('Key',(-3,-4,6),850,4),('Fill',(4,-2,4),450,3),('Rim',(0,3,5),650,3)] if whole else [('Key',(-.5,-.65,1.1),60,.75),('Fill',(.6,-.2,.7),28,.65),('Rim',(.1,.5,.8),45,.55)]
for name,location,power,size in lighting:
    light=bpy.data.lights.new('Style'+name,'AREA');light.energy=power;light.shape='DISK';light.size=size
    obj=bpy.data.objects.new('Style'+name,light);s.collection.objects.link(obj);obj.location=location;obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,floor_z));floor=bpy.context.object;floor.name='PreviewOnly_Floor'
mat=bpy.data.materials.new('PreviewOnly_Floor');mat.diffuse_color=(.25,.28,.32,1);mat.use_nodes=True;mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.25,.28,.32,1);mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.7;floor.data.materials.append(mat)
s.render.engine='CYCLES';s.cycles.samples=96 if final else 32;s.cycles.use_denoising=True
s.render.resolution_x=2560 if final else 1280;s.render.resolution_y=1920 if final else 960;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(out.resolve());s.view_settings.view_transform='AgX';s.render.film_transparent=False
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='METAL'
    s.cycles.device='GPU'
except Exception:pass
out.parent.mkdir(parents=True,exist_ok=True);bpy.ops.render.render(write_still=True)
