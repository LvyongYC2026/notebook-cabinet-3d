"""Read-only, both-front-variant sweep and shared-ear attachment checks."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser();p.add_argument('--output',required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
scene=bpy.context.scene;scene.frame_set(1)
root=bpy.data.objects.get('CabinetRoot') or bpy.data.objects.get('SingleDrawerRoot')
single=root.name=='SingleDrawerRoot'
ids=['S1'] if single else ['B'+str(i) for i in range(1,25)]
trays={i:bpy.data.objects['SingleTray' if single else 'Tray_'+i] for i in ids}
source_hash=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()

def under(o,par):
    while o:
        if o==par:return True
        o=o.parent
    return False

def active(o,variant):
    while o:
        v=o.get('drawer_front_variant')
        if v and v!=variant:return False
        if not v and o.get('initial_hidden',False):return False
        o=o.parent
    return True

def shape(parts):
    pts=[];faces=[];owners=[];graph=bpy.context.evaluated_depsgraph_get()
    for o in parts:
        ev=o.evaluated_get(graph);me=ev.to_mesh()
        if me is None:continue
        off=len(pts);pts.extend(ev.matrix_world@v.co for v in me.vertices)
        faces.extend(tuple(off+i for i in f.vertices) for f in me.polygons)
        owners.extend([o.name]*len(me.polygons));ev.to_mesh_clear()
    if not pts:return None
    return [pts,faces,owners,Vector([min(v[i] for v in pts) for i in range(3)]),Vector([max(v[i] for v in pts) for i in range(3)]),BVHTree.FromPolygons(pts,faces)]

def moved(sh,dy):
    if not sh:return None
    t=Vector((0,dy,0));pts=[v+t for v in sh[0]]
    return [pts,sh[1],sh[2],sh[3]+t,sh[4]+t,BVHTree.FromPolygons(pts,sh[1])]

def hits(a,b):
    if a is None or b is None or any(a[4][i]<b[3][i]-1e-7 or b[4][i]<a[3][i]-1e-7 for i in range(3)):return []
    return a[5].overlap(b[5])

def attachment(o):return bool(o.get('drawer_front_shared'))
def front(o):return bool(o.get('drawer_front_variant'))
def contact_only(a,b):
    return min(a[4].z,b[4].z)-max(a[3].z,b[3].z)<=.00001

objects=[o for o in scene.objects if o.type=='MESH' and under(o,root)]
# Visibility is selected semantically below. Disabled viewport branches may
# retain cached evaluated transforms, so temporarily enable both assemblies
# for geometry evaluation; this read-only process never saves the file.
for o in scene.objects:
    if o.get('drawer_front_variant'):
        if o.animation_data:
            for curve in o.animation_data.drivers:
                if curve.data_path in {'hide_viewport','hide_render'}:curve.mute=True
        o.hide_viewport=False;o.hide_set(False)
for tray in trays.values():tray.animation_data_clear();tray.location.y=0
records=[];connections=[];expected=[];fixed_counts={};coverage={};self_checks=[]
for variant in ['metal','glass']:
    scene['drawer_front_mode']=0 if variant=='metal' else 1
    scene.frame_set(1)
    for tray in trays.values():tray.location.y=0
    bpy.context.view_layer.update()
    eligible=[o for o in objects if active(o,variant)]
    sources={i:[o for o in eligible if under(o,trays[i]) and (front(o) or attachment(o))] for i in ids}
    own={i:[o for o in eligible if under(o,trays[i]) and not front(o) and not attachment(o)] for i in ids}
    dynamic=[o for o in eligible if o.data.shape_keys and o.get('bay_id') in ids and not front(o) and not attachment(o)]
    fixed=[o for o in eligible if not front(o) and not attachment(o) and o not in dynamic and not any(under(o,t) for t in trays.values())]
    fixed_infos={o.name:shape([o]) for o in fixed}
    source_infos={i:shape(sources[i]) for i in ids}
    own_infos={i:{o.name:shape([o]) for o in own[i]} for i in ids}
    own_groups={i:shape(own[i]) for i in ids}
    fixed_counts[variant]=len(fixed)
    coverage[variant]={'source_meshes':{i:len(sources[i]) for i in ids},'active_native_cables':len(dynamic)}
    # Within one Tray all relative transforms remain constant at every travel.
    # Resolve source-part identities so only actual ear-to-bridge surface joins
    # are accepted, not unrelated parts touching the bridge.
    for i in ids:
        for name,other in own_infos[i].items():
            hh=hits(source_infos[i],other)
            if not hh:continue
            names=sorted(set(source_infos[i][2][a] for a,b in hh))
            permitted=name.startswith(i+'_FrontBridge') and all(n.startswith('DrawerFrontAttachment_'+i+'_') and contact_only(shape([bpy.data.objects[n]]),other) for n in names)
            rec={'variant':variant,'bay':i,'source_parts':names,'target':name,'reason':'constant same-Tray relative transform'}
            if permitted:expected.append(dict(rec,classification='shared ear/weld touches bridge underside, zero positive Z overlap'))
            else:self_checks.append(rec)
        at=[o for o in sources[i] if attachment(o)]
        ff=[o for o in sources[i] if front(o)]
        for ear in at:
            ei=shape([ear])
            for face in ff:
                fi=shape([face])
                if not hits(ei,fi):continue
                lower=('ReturnHorizontal' in face.name) and fi[4].z < trays[i].matrix_world.translation.z-.020
                rec={'variant':variant,'bay':i,'source_parts':[ear.name],'target':face.name}
                if lower and contact_only(ei,fi):expected.append(dict(rec,classification='shared ear/weld touches selected lower metal return top'))
                else:self_checks.append(rec)
    for travel in range(0,321,20):
        for tray in trays.values():tray.location.y=-travel/1000
        bpy.context.view_layer.update()
        current={i:moved(source_infos[i],-travel/1000) for i in ids}
        dynamic_infos={o.name:shape([o]) for o in dynamic}
        current_own={i:moved(own_groups[i],-travel/1000) for i in ids}
        intersections=[]
        for i in ids:
            a=current[i]
            for name,sh in fixed_infos.items():
                if hits(a,sh):intersections.append([i,name,'fixed'])
            for name,sh in dynamic_infos.items():
                if hits(a,sh):intersections.append([i,name,'native cable'])
            for j in ids:
                if i!=j and hits(a,current_own[j]):intersections.append([i,j,'other drawer payload'])
                if i<j and hits(a,current[j]):intersections.append([i,j,'other drawer front/attachments'])
            # Physical face-to-face attachment probes follow the actual ear,
            # source Bridge and selected front through all seventeen poses.
            for sign,label in [(-1,'Left'),(1,'Right')]:
                ear=bpy.data.objects['DrawerFrontAttachment_'+i+'_Ear_'+label]
                bridge_candidates=[o for o in own[i] if o.name.startswith(i+'_FrontBridge') and abs(o.matrix_world.translation.x-ear.matrix_world.translation.x)<.01]
                lower_candidates=[o for o in sources[i] if front(o) and 'ReturnHorizontal' in o.name and o.matrix_world.translation.z<trays[i].matrix_world.translation.z-.02]
                for kind,targets,point,direction in [('upper',bridge_candidates,(0,-.300,-.013),(0,0,1)),('lower',lower_candidates,(0,-.315,-.026),(0,0,-1))]:
                    point=ear.matrix_world@Vector(point);direction=Vector(direction)
                    best=None;target_name=None
                    for target in targets:
                        ti=shape([target]);hit,normal,index,distance=ti[5].ray_cast(point-direction*.001,direction,.002)
                        if hit is not None and (best is None or abs(distance-.001)<abs(best)):
                            best=distance-.001;target_name=target.name
                    gap=None if best is None else best*1000
                    connections.append({'variant':variant,'travel_mm':travel,'bay':i,'ear':ear.name,'joint':kind,'target':target_name,'gap_mm':gap,'passed':gap is not None and abs(gap)<.001})
        records.append({'variant':variant,'travel_mm':travel,'intersections':intersections})
        print('FRONT_MOTION',variant,travel,len(intersections),flush=True)
report={'blend_sha256':source_hash,'drawer_count':len(ids),'variant_count':2,'travel_samples_mm':list(range(0,321,20)),
        'fixed_mesh_counts':fixed_counts,'coverage':coverage,'poses':records,'same_tray_unexpected':self_checks,
        'declared_attachment_contacts':expected,'connection_probes':connections,
        'intersection_count':sum(len(r['intersections']) for r in records)+len(self_checks),
        'connection_probe_failures':sum(not c['passed'] for c in connections),
        'method':'Both variants; evaluated mesh BVH, all 24 or single moving fronts/shared ears against every active fixed mesh, native cable and other drawer payload. Same-Tray rigid relations checked once per variant; physical upper/lower joints ray-probed at each position.',
        'limits':'17 sampled positions, not continuous swept-volume, fatigue or strength certification. Glazing gasket/retainer assembly contacts are not treated as moving-mechanism collisions.'}
report['status']='passed' if not report['intersection_count'] and not report['connection_probe_failures'] else 'review_required'
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FRONT_MOTION_RESULT',report['status'],report['intersection_count'],report['connection_probe_failures'],flush=True)
