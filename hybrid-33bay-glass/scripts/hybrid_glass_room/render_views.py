"""Read-only batch render of actual room perspective / orthographic cameras."""
import bpy,sys,json,hashlib,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from setup_display_modes import apply_display_mode
def arg(k,d):return sys.argv[sys.argv.index(k)+1] if k in sys.argv else d
views=arg('--views','overview,front,side,top,operation').split(',')
out=Path(arg('--output',str(Path(bpy.data.filepath).parent/'renders'))).resolve();out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;preview='--preview' in sys.argv
scene.render.resolution_x=1280 if preview else 2560;scene.render.resolution_y=720 if preview else 1440;scene.render.resolution_percentage=100;scene.cycles.samples=20 if preview else 64
records=[]
for v in views:
    apply_display_mode('ROOM',v)
    if v=='operation':
        # One right drawer at a time, matching the public interaction interlock.
        # Left A1 remains a hinged bay. Other modules stay closed.
        for ob in bpy.context.scene.objects:
            if ob.name.startswith('Tray_'):
                ob.animation_data_clear();ob.location.y=0
            if ob.name.startswith('DoorPivot_'):
                ob.animation_data_clear();ob.rotation_euler.z=0
        door=bpy.data.objects['DoorPivot_A1']
        door.rotation_euler.z=math.radians(float(door.get('swing_degrees',-95)))
        bpy.data.objects['Tray_A1'].location.y=-.32
        bpy.data.objects['Tray_B20'].location.y=-.32
        bpy.context.view_layer.update()
    scene.render.filepath=str(out/('room_'+v+('.preview' if preview else '')+'.png'))
    bpy.ops.render.render(write_still=True)
    p=Path(scene.render.filepath);records.append({'view':v,'camera':scene.camera.name,'projection':scene.camera.data.type,'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/('preview_manifest.json' if preview else 'render_manifest.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
