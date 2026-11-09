"""Read-only narrow check of new shell apertures and styled-mesh solids."""
import bpy,bmesh,json,hashlib,sys
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];source,out=map(Path,args[:2])
bpy.ops.wm.open_mainfile(filepath=str(source.resolve()));s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
root=bpy.data.objects['Laptop'];base=bpy.data.objects['S1_LaptopBase'];lid=bpy.data.objects['S1_LaptopClosedLid']
cases=[('wired USB',(-.121,-.220,.018),(1,0,0),.005),('wired DC',(-.121,-.075,.026),(1,0,0),.005),('spare USB',(.181,-.185,.014),(-1,0,0),.005),('audio',(.181,-.155,.014),(-1,0,0),.005),('vent',(.181,-.110,.013),(-1,0,0),.004),('finger recess',(.030,-.256,.024),(0,1,0),.004)]
checks=[]
for title,origin,direction,minimum in cases:
    distances=[]
    for obj in [base,lid]:
        matrix=obj.matrix_world.inverted()@root.matrix_world;p=matrix@Vector(origin);d=(matrix.to_3x3()@Vector(direction)).normalized()
        hit,point,normal,index=obj.ray_cast(p,d,distance=.02)
        if hit:distances.append((point-p).length)
    nearest=min(distances) if distances else None
    assert nearest is None or nearest>=minimum-1e-5,(title,nearest,minimum)
    checks.append({'opening':title,'shell_clearance_cm':None if nearest is None else nearest*100,'minimum_cm':minimum*100})
solids=[]
for obj in [base,lid,*[o for o in root.children if 'LaptopHinge' in o.name or o.get('laptop_style_detail')]]:
    if obj.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(obj.data);volume=bm.calc_volume(signed=True);bad=sum(not e.is_manifold for e in bm.edges);bm.free()
    assert volume>0 and bad==0,(obj.name,volume,bad)
    assert obj.data.materials and all(obj.data.materials[p.material_index] is not None for p in obj.data.polygons),obj.name+' unassigned material'
    solids.append({'name':obj.name,'signed_volume_m3':volume,'nonmanifold_edges':bad})
report={'status':'passed','source_blend_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'Shell aperture depth and styled mesh solid/material integrity; includes original USB/DC entry clearances, excludes connector bodies themselves. Full motion and interface retention are separately audited.','openings':checks,'styled_solids':solids}
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('STYLE_APERTURES',len(checks),len(solids))
