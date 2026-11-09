"""Read-only independent fixed-wire endpoint and real-aperture probes.

blender -b candidate.blend -P scripts/audit_hybrid_connections.py -- \
  --metadata components.json --output connection_audit.json

Inspects exported-source evaluated geometry, not builder helpers. Route metadata
must name its source object. New B routes should provide endpoint_node_names as
[start_node, end_node], or start_node/end_node. AABB enclosure is reported as an
endpoint-envelope check; it is not an electrical-continuity certification.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--metadata',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    meta_path=Path(args.metadata);meta=json.loads(meta_path.read_text())
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    cache={}
    def geometry(name):
        if name in cache:return cache[name]
        o=bpy.data.objects.get(name)
        if o is None:return None
        objects=[n for n in [o,*o.children_recursive]if n.type in {'MESH','CURVE','FONT'}]
        vertices=[];polygons=[]
        for n in objects:
            ev=n.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            if me is None:continue
            offset=len(vertices);vertices.extend(ev.matrix_world@v.co for v in me.vertices)
            polygons.extend(tuple(offset+i for i in p.vertices)for p in me.polygons);ev.to_mesh_clear()
        if not vertices or not polygons:return None
        sh={'vertices':vertices,'tree':BVHTree.FromPolygons(vertices,polygons),'min':Vector([min(v[i]for v in vertices)for i in range(3)]),'max':Vector([max(v[i]for v in vertices)for i in range(3)])}
        cache[name]=sh;return sh
    report={'source_blend_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'metadata_sha256':hashlib.sha256(meta_path.read_bytes()).hexdigest(),'fixed_routes':[],'apertures':[],'errors':[],
            'limits':'Samples route end-ring geometry, declared connector envelopes and nine axial rays through each declared circular aperture. It does not prove whole-route collision freedom, actual connector pinning, electrical continuity or manufacturing tolerances. No scene saved.'}
    errors=report['errors'];routes=meta.get('wiring_design',{}).get('fixed_routes',[])
    points_by_route=[]
    for route in routes:
        name=route.get('name');bay=route.get('bay_id');kind=route.get('kind');pts=route.get('points_blender_m',[])
        row={'name':name,'bay_id':bay,'kind':kind,'mesh_end_ring_checks':[],'connector_checks':[]}
        sh=geometry(name)if name else None
        parent=bpy.data.objects.get(route.get('parent_node','CabinetRoot'))
        if sh is None or parent is None or len(pts)<2:
            errors.append({'check':'route_geometry_and_frame_exist','route':name});report['fixed_routes'].append(row);continue
        world=[parent.matrix_world@Vector(p)for p in pts];points_by_route.append((name,world,route.get('radius_mm',0)/1000))
        radius=route.get('radius_mm',0)/1000
        kd=KDTree(len(sh['vertices']))
        for i,v in enumerate(sh['vertices']):kd.insert(v,i)
        kd.balance()
        guide_distances=[kd.find(p)[2]for p in world]
        row['guide_point_count']=len(world);row['maximum_guide_to_mesh_vertex_mm']=round(max(guide_distances)*1000,6)
        if max(guide_distances)>radius+.001:errors.append({'check':'route_guide_points_match_actual_mesh','route':name})
        endpoint_names=route.get('endpoint_node_names') or [route.get('start_node'),route.get('end_node')]
        if len(endpoint_names)!=2:endpoint_names=[None,None]
        for index,p in enumerate([world[0],world[-1]]):
            distance=min((v-p).length for v in sh['vertices']);passed=radius>0 and distance<=radius+.0005
            row['mesh_end_ring_checks'].append({'index':index,'nearest_mesh_vertex_mm':round(distance*1000,6),'radius_mm':radius*1000,'passed':passed})
            if not passed:errors.append({'check':'route_end_ring_matches_metadata','route':name,'index':index})
            target=endpoint_names[index]
            if target:
                target_sh=geometry(target)
                if target_sh:
                    near=target_sh['tree'].find_nearest(p);dist=near[3]if near[0]is not None else None
                    enclosed=all(target_sh['min'][i]-1e-6<=p[i]<=target_sh['max'][i]+1e-6 for i in range(3))
                    ok=enclosed or (dist is not None and dist<=.00025)
                else:dist=None;enclosed=False;ok=False
                row['connector_checks'].append({'index':index,'target':target,'endpoint_in_target_bounds':enclosed,'surface_distance_mm':round(dist*1000,6)if dist is not None else None,'passed':ok})
                if not ok:errors.append({'check':'route_endpoint_connects_target','route':name,'index':index,'target':target})
        if str(bay).startswith('B') and len(row['connector_checks'])!=2:
            errors.append({'check':'new_B_route_two_declared_endpoints_required','route':name})
        report['fixed_routes'].append(row)
    apertures=meta.get('wiring_design',{}).get('real_apertures',[])
    for hole in apertures:
        name=hole.get('object');center=hole.get('center_world_blender_m');axis=hole.get('axis');diameter=hole.get('diameter_mm')
        rect=hole.get('rect_dimensions_mm') or (hole.get('dimensions_mm')if hole.get('shape')=='rectangle'else None)
        row={'object':name,'center_world_blender_m':center,'axis':axis,'diameter_mm':diameter,'rectangle_dimensions_mm':rect,'rays':[],'route_crossings':[]}
        sh=geometry(name)if name else None
        if sh is not None and rect and axis is None:
            axis='XYZ'[min(range(3),key=lambda i:sh['max'][i]-sh['min'][i])]
            row['axis']=axis;row['legacy_axis_inferred_from_plate_thickness']=True
        if sh is None or not center or axis not in ('X','Y','Z') or (not rect and(not diameter or diameter<=0)):
            errors.append({'check':'physical_aperture_contract','object':name});report['apertures'].append(row);continue
        k='XYZ'.index(axis);tangents=[i for i in range(3)if i!=k];center=Vector(center);direction=Vector([1 if i==k else 0 for i in range(3)])
        radius=diameter/2000 if diameter else None
        half=[rect[i]/2000 for i in tangents]if rect else[radius,radius]
        offsets=[Vector((0,0,0))]
        for n in range(8):
            offset=Vector((0,0,0));offset[tangents[0]]=.8*half[0]*math.cos(n*math.tau/8);offset[tangents[1]]=.8*half[1]*math.sin(n*math.tau/8);offsets.append(offset)
        span=max(abs(sh['min'][k]-center[k]),abs(sh['max'][k]-center[k]))+.005
        for index,offset in enumerate(offsets):
            start=center+offset-direction*span;hit=sh['tree'].ray_cast(start,direction,span*2)
            clear=hit[0]is None;row['rays'].append({'index':index,'clear':clear,'offset_radius_mm':round(offset.length*1000,6)})
            if not clear:errors.append({'check':'declared_aperture_has_solid_geometry','object':name,'ray':index})
        # A hole label positioned in empty space would also yield clear rays.
        # Require a surrounding material witness outside the circular opening.
        surrounding_hits=0
        for n in range(8):
            offset=Vector((0,0,0));offset[tangents[0]]=1.5*half[0]*math.cos(n*math.tau/8);offset[tangents[1]]=1.5*half[1]*math.sin(n*math.tau/8)
            hit=sh['tree'].ray_cast(center+offset-direction*span,direction,span*2)
            surrounding_hits+=int(hit[0]is not None)
        row['surrounding_material_witnesses']=surrounding_hits
        if not surrounding_hits:errors.append({'check':'aperture_not_located_in_surrounding_plate','object':name})
        for route_name,pts,cable_radius in points_by_route:
            for a,b in zip(pts,pts[1:]):
                delta=b[k]-a[k]
                if abs(delta)<1e-12:continue
                t=(center[k]-a[k])/delta
                if not 0<=t<=1:continue
                p=a.lerp(b,t);radial=math.sqrt(sum((p[i]-center[i])**2 for i in tangents))
                rectangular_margin=min(half[j]-abs(p[i]-center[i])for j,i in enumerate(tangents))
                if (rect and rectangular_margin>=0)or(not rect and radial<=radius):
                    clearance=(rectangular_margin if rect else radius-radial)-cable_radius
                    blocked=0
                    for angle in [None,*[j*math.tau/8 for j in range(8)]]:
                        offset=Vector((0,0,0))
                        if angle is not None:
                            offset[tangents[0]]=cable_radius*math.cos(angle);offset[tangents[1]]=cable_radius*math.sin(angle)
                        h=sh['tree'].ray_cast(p+offset-direction*span,direction,span*2)
                        blocked+=int(h[0]is not None)
                    row['route_crossings'].append({'route':route_name,'radial_surface_clearance_mm':round(clearance*1000,6),'actual_material_blocked_rays':blocked,'inside_merged_opening':clearance<0 and blocked==0})
                    # The new shared opening may overlap a retained legacy hole.
                    # Actual panel material, rather than the obsolete smaller
                    # aperture boundary, determines whether the cable is blocked.
                    if blocked:errors.append({'check':'actual_material_blocks_cable_at_aperture','object':name,'route':route_name,'blocked_rays':blocked})
                    break
        report['apertures'].append(row)
    expected={f'A{i}'for i in range(1,10)}|{f'B{i}'for i in range(1,25)}
    kinds={kind:{r.get('bay_id')for r in routes if r.get('kind')==kind and r.get('bay_id')}for kind in ['network','ac']}
    report['route_coverage']={k:sorted(v)for k,v in kinds.items()}
    report['coverage_pass']=all(v==expected for v in kinds.values())and bool(apertures)and len(report['apertures'])==len(apertures)
    report['endpoint_mesh_check_count']=sum(len(r['mesh_end_ring_checks'])for r in report['fixed_routes'])
    report['connector_check_count']=sum(len(r['connector_checks'])for r in report['fixed_routes'])
    report['aperture_ray_count']=sum(len(r['rays'])for r in report['apertures'])
    report['status']='passed_within_scope'if report['coverage_pass']and not errors else'review_required'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('HYBRID_CONNECTION_AUDIT',report['status'],'errors',len(errors),'route_endpoints',report['endpoint_mesh_check_count'],'aperture_rays',report['aperture_ray_count'],flush=True)
    return 0 if report['status']=='passed_within_scope'else 1


if __name__=='__main__':
    result=main()
    if result:raise SystemExit(result)
