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
        # Read-only illustration of the existing mechanisms, in the verified
        # fully open / extended state. The editable input file is never saved.
        for bay in [s+str(i) for s in 'AB' for i in range(1,10)]:
            door=bpy.data.objects['DoorPivot_'+bay];tray=bpy.data.objects['Tray_'+bay]
            door.animation_data_clear();tray.animation_data_clear()
            door.rotation_euler.z=math.radians(float(door.get('swing_degrees',-95)))
            tray.location.y=-.32
        bpy.context.view_layer.update()
    scene.render.filepath=str(out/('room_'+v+('.preview' if preview else '')+'.png'))
    bpy.ops.render.render(write_still=True)
    p=Path(scene.render.filepath);records.append({'view':v,'camera':scene.camera.name,'projection':scene.camera.data.type,'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/('preview_manifest.json' if preview else 'render_manifest.json')).write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
