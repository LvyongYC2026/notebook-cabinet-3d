"""Room design assumptions, metres, Blender X right / Y rear / Z up."""
ROOM = {
 'interior_wdh_m':[5.10,3.00,2.80], 'wall_thickness_m':0.12,
 'cabinet_installation_m':[2.55,2.575,0.0],
 'cabinet_dimensions_m':[3.30,0.65,1.85],
 'cabinet_bounds_m':{'min':[.9,2.25,0],'max':[4.2,2.90,1.85]},
 'operation_zone_m':{'min':[.9,1.05,0],'max':[4.2,2.25,1.85]},
 'rear_clearance_m':.10, 'side_wall_clearance_m':.90,
 'reserved_side_service_band_m':.30, 'floor_thickness_m':.08,
 'door_opening_y_m':[.10,1.00], 'door_height_m':2.10,
 'door_pivot_m':[5.08,.105,0], 'door_leaf_wdh_m':[.045,.88,2.08],
 'door_display_angle_degrees':90,
 'desk_bounds_m':{'min':[.10,.10,0],'max':[.70,1.30,.75]},
 'chair_center_m':[1.02,.54,0],
 'display_mode':'ROOM', 'default_cutaway':['RoomWall_Front','RoomWall_Right','RoomRoof'],
 'font_path':'assets/room_signage_subset.ttf',
}
CAMERAS = {
 'overview':{'position':[3.8,-8.4,6.2],'target':[2.55,1.55,1.15],'projection':'perspective','lens_mm':45},
 'interior':{'position':[3.9,.45,1.62],'target':[2.55,2.45,1.15],'projection':'perspective','lens_mm':26},
 'front':{'position':[2.55,-6,1.40],'target':[2.55,1.5,1.40],'projection':'orthographic','ortho_scale_m':6.2},
 'side':{'position':[-6,1.5,1.40],'target':[2.55,1.5,1.40],'projection':'orthographic','ortho_scale_m':5.8},
 'top':{'position':[2.55,1.5,9.0],'target':[2.55,1.5,0],'projection':'orthographic','ortho_scale_m':6.2,'up':[0,1,0]},
}
SIGN_TEXTS = ['机要室','涉密设备管理区','保密管理要求','授权进入','规范使用','离开检查','管理工作台','门禁','CCTV','ACCESS CONTROL']
