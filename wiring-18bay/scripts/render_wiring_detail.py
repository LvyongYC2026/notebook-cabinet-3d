import bpy,math
from mathutils import Vector
from pathlib import Path
s=bpy.context.scene;s.frame_set(65)
door=bpy.data.objects['SingleDoorPivot'];door.animation_data_clear();door.rotation_euler.z=math.radians(-100)
tray=bpy.data.objects['SingleTray'];tray.animation_data_clear();tray.location.y=-.16
cam=s.camera;cam.location=(.08,-.91,.46);target=Vector((-.065,-.14,.115));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.76
s.render.engine='CYCLES';s.cycles.samples=32;s.render.resolution_x=2560;s.render.resolution_y=1440;s.render.resolution_percentage=100
s.render.filepath=str(Path(bpy.data.filepath).parent/'preview_usb_wiring_2560.png')
bpy.ops.render.render(write_still=True)
