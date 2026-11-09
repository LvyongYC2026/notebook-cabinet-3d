"""Complete web contract generated from source; never reads prior output."""
import copy,json
from pathlib import Path

def build_metadata(room,cameras):
    here=Path(__file__).resolve().parent
    meta=json.loads((here/'metadata_template.json').read_text())
    cx,cy,cz=room['cabinet_installation_m'];w,d,h=room['interior_wdh_m']
    def gl(p):return [round(p[0]-cx,6),round(p[2]-cz,6),round(cy-p[1],6)]
    meta['dimensions_cm']=[v*100 for v in [w,d,h]]
    meta['dimensions_mm']=[v*1000 for v in [w,d,h]]
    meta['interior_bounds_m']={'min':gl([0,d,0]),'max':gl([w,0,h])}
    meta['bounds_m']=copy.deepcopy(meta['interior_bounds_m'])
    meta['coordinate_mapping']={'blender_room_origin':'interior left-front floor corner',
        'blender_room_to_cabinet_translation_m':[-cx,-cy,-cz],
        'blender_xyz_to_gltf':'[x,z,-y]',
        'cabinet_room_position_blender_m':[cx,cy,cz],
        'cabinet_web_position_gltf_m':[0,0,0],'cabinet_scale':[1,1,1]}
    meta['camera']={}
    for name,cfg in cameras.items():
        v=copy.deepcopy(cfg);v['position']=gl(cfg['position']);v['target']=gl(cfg['target'])
        if name=='top':v['up']=[0,0,-1]
        v['cutaway_node_names']=list(room['default_cutaway'])
        if name=='side':v['cutaway_node_names']=['RoomWall_Left','RoomWall_Front','RoomRoof','RoomWorkstation','RoomSigns','RoomPlants','RoomSecurity']
        if name=='top':v['cutaway_node_names']=['RoomRoof']
        if name=='interior':v['cutaway_node_names']=[]
        meta['camera'][name]=v
    zone=room['operation_zone_m'];a=zone['min'];b=zone['max']
    meta['operation_zone_bounds_m']={'min':gl([a[0],b[1],a[2]]),'max':gl([b[0],a[1],b[2]])}
    meta['room_parameters']={k:v for k,v in room.items() if k!='font_path'}
    return meta
