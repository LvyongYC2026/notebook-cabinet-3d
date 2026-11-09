"""Hybrid 9 open-lid bays + 24 closed-lid drawers. Design dimensions in mm."""
PARAMETERS = {
    'cabinet_mm': [3300, 650, 1850],
    'drawer_columns': 3, 'drawer_rows': 8,
    'column_pitch_mm': 450, 'row_pitch_mm': 160,
    'lowest_support_mm': 380, 'net_height_mm': 130,
    'tray_travel_mm': 320, 'laptop_mm': [300, 210, 30],
    'laptop_center_xy_mm': [30, -150],
    'drawer_deck_mm': [376, 470, 2],
    'drawer_face_mm': [444, 16, 154],
    'adapter_mm': [48, 80, 90], 'nic_mm': [28, 40, 18],
    'cable_bend_radius_mm': 28,
    'network_radius_mm': 2.1, 'dc_radius_mm': 2.4, 'usb_radius_mm': 1.6,
    'empty_bays': ['A3', 'B2', 'B6', 'B20'],
    'remove_path_m': [[0,0,0],[0,.18,0],[0,.18,.12]],
    'single_dimensions_mm': [450,650,162], 'single_support_mm': 30,
}
