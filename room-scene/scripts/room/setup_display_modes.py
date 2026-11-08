"""Run this text in Blender to enable ROOM / PRODUCT and room view controls."""
import bpy
from mathutils import Vector

INSTALLATION=(2.55,2.575,0)
DEFAULT_CUT=['RoomWall_Front','RoomWall_Right','RoomRoof']

def descendants(ob):
    return [ob,*ob.children_recursive]

def visible_group(name,visible):
    ob=bpy.data.objects.get(name)
    if ob:
        for child in descendants(ob):
            child.hide_set(not visible);child.hide_render=not visible

def apply_display_mode(mode='ROOM',view='overview',cutaway=True):
    scene=bpy.context.scene;cab=bpy.data.objects['CabinetRoot']
    mode=mode.upper()
    if mode not in ('ROOM','PRODUCT'):raise ValueError('Display mode must be ROOM or PRODUCT')
    cab.location=scene.get('ROOM_CABINET_INSTALLATION',INSTALLATION) if mode=='ROOM' else (0,0,0)
    cab.scale=(1,1,1)
    visible_group('RoomEnvironmentRoot',mode=='ROOM')
    for name,state in [('Room_Lighting',mode=='ROOM'),('Studio_Environment',mode=='PRODUCT')]:
        col=bpy.data.collections.get(name)
        if col:
            col.hide_render=not state;col.hide_viewport=not state
    # The original cabinet animations remain intact. Installation display
    # starts closed; rear maintenance must be performed in PRODUCT mode.
    scene.frame_set(1)
    if mode=='ROOM':
        hidden=DEFAULT_CUT if cutaway else []
        if view=='side':hidden=['RoomWall_Left','RoomWall_Front','RoomRoof','RoomWorkstation','RoomSigns','RoomPlants','RoomSecurity']
        if view=='top':hidden=['RoomRoof']
        if view=='interior':hidden=[]
        for name in hidden:visible_group(name,False)
        visible_group('RoomOperationGuide',view=='operation')
        scene.camera=bpy.data.objects.get('Camera_Room_'+('top' if view=='operation' else view))
    else:
        scene.camera=bpy.data.objects.get('Camera_01_Hero')
    scene['DISPLAY_MODE']=mode;scene['ROOM_VIEW']=view
    bpy.context.view_layer.update()

class ROOM_OT_display(bpy.types.Operator):
    bl_idname='room.display_mode';bl_label='Switch room display'
    mode:bpy.props.StringProperty(default='ROOM')
    view:bpy.props.StringProperty(default='overview')
    def execute(self,context):
        apply_display_mode(self.mode,self.view);return {'FINISHED'}

class ROOM_PT_display(bpy.types.Panel):
    bl_label='Room Display';bl_idname='ROOM_PT_display'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Room Display'
    def draw(self,context):
        col=self.layout.column(align=True)
        for title,mode,view in [('Room overview','ROOM','overview'),('Interior','ROOM','interior'),('Front orthographic','ROOM','front'),('Side orthographic','ROOM','side'),('Top orthographic','ROOM','top'),('Operation space','ROOM','operation'),('Product only','PRODUCT','overview')]:
            op=col.operator('room.display_mode',text=title);op.mode=mode;op.view=view
        if context.scene.get('DISPLAY_MODE')=='ROOM':
            col.label(text='Rear clearance: 100 mm')
            col.label(text='Move cabinet for rear service')

def register():
    for cls in [ROOM_OT_display,ROOM_PT_display]:
        old=getattr(bpy.types,cls.__name__,None)
        if old:
            try:bpy.utils.unregister_class(old)
            except Exception:pass
        bpy.utils.register_class(cls)

if __name__=='__main__':register()
