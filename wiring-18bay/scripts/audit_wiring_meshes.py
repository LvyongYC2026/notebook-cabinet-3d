"""Read-only closed-mesh/normal audit for newly constructed static wiring parts."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('wiring_design') and not o.data.shape_keys]
results={};issues=[]
for ob in objects:
    key=ob.data.name
    if key not in results:
        bm=bmesh.new();bm.from_mesh(ob.data)
        volume=bm.calc_volume(signed=True)
        opened=sum(not e.is_manifold for e in bm.edges)
        finite=all(math.isfinite(c) for v in bm.verts for c in v.co)
        zero_faces=sum(f.calc_area()<1e-14 for f in bm.faces)
        results[key]={'mesh':key,'example_object':ob.name,'signed_volume_m3':volume,'nonmanifold_edges':opened,'finite_coordinates':finite,'degenerate_faces':zero_faces}
        bm.free()
        if volume< -1e-12 or opened or not finite or zero_faces:issues.append(results[key])
p=Path(bpy.data.filepath)
report={'method':'bmesh signed volume, edge manifoldness, finite coordinates and face area; newly added static MESH data only',
    'blend_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'static_objects':len(objects),'unique_meshes':len(results),'issues':issues,
    'limits':'Excludes font outlines, original source meshes, native morph meshes and full self-intersection/tolerance analysis.'}
(p.parent/'independent_wiring_mesh_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('WIRING_MESH_AUDIT',len(objects),len(results),'unique meshes',len(issues),'issues',flush=True)
