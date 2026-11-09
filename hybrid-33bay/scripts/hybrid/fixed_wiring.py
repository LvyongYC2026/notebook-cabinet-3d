"""Separated fixed AC/data services and a real rear patch interface.
Geometry is a routing study; all service ratings and actual cable choice remain open.
"""
import bpy,math,sys
from mathutils import Vector
from geometry import bezier,length,min_radius,remove

def rounded(points,r=.028):
    p=[Vector(q) for q in points];out=[tuple(p[0])]
    for i in range(1,len(p)-1):
        u=p[i-1]-p[i];v=p[i+1]-p[i]
        if min(u.length,v.length)<1e-8:continue
        un=u.normalized();vn=v.normalized();theta=math.acos(max(-1,min(1,un.dot(vn))))
        if abs(math.pi-theta)<1e-5:continue
        trim=min(r/max(math.tan(theta/2),1e-9),u.length*(.9 if i==1 else .49),v.length*(.9 if i==len(p)-2 else .49))
        a=p[i]+un*trim;q=p[i]+vn*trim;c=p[i]+(un+vn).normalized()*(trim/max(math.cos(theta/2),1e-9));n=un.cross(vn).normalized();rad=a-c;end=q-c;angle=math.atan2(n.dot(rad.cross(end)),rad.dot(end));out.append(tuple(a))
        for j in range(1,9):
            t=angle*j/8;out.append(tuple(c+rad*math.cos(t)+n.cross(rad)*math.sin(t)))
    out.append(tuple(p[-1]));return out

def rear_patch_x(i):return -.184+.016*i

def switch_jumper_points(i):
    port=i+10;pr,pc=divmod(port-1,24);sx=-.199+pc*.0173;sz=.687+pr*.021;rx=sx+.0085;tx=rear_patch_x(i)
    p=bezier((sx,-.200,sz),(rx,-.230,sz),(rx,-.235,sz+.053),(rx,-.235,sz+.093),40)
    low=i<15;rz=.940 if low else 1.065;top=1.340 if low else 1.530;inner=rx*.75
    p+=bezier((rx,-.235,sz+.093),(rx,-.235,sz+.143),(inner,-.235,rz-.050),(inner,-.235,rz),32)[1:]
    p+=bezier((inner,-.235,rz),(inner,-.235,top),(tx,.312,top),(tx,.312,.932),72)[1:]
    return p

def field_network_points(i):
    row,col=divmod(i,3);cx=.525+.45*col;support=1.5-.16*row;tx=rear_patch_x(i);ny=[.307,.313,.319][col];cy=[.260,.268,.276][col];bz=.215+.006*row;nx=cx-.120-.007*row
    p=bezier((tx,.312,.888),(tx,.312,.835),(tx,ny,.790),(tx,ny,.730),28)
    p+=rounded([(tx,ny,.730),(tx,ny,bz),(.215,ny,bz)],.025)[1:]
    p+=bezier((.215,ny,bz),(.241,ny,bz),(.251,cy,bz),(.277,cy,bz),32)[1:]
    p+=rounded([(.277,cy,bz),(nx,cy,bz),(nx,cy,bz+.045)],.028)[1:]
    p+=bezier((nx,cy,bz+.045),(nx,cy,bz+.090),(nx,.312,bz+.120),(nx,.312,bz+.160),32)[1:]
    p+=rounded([(nx,.312,bz+.160),(nx,.312,support+.090),(cx-.199,.267,support+.090)],.028)[1:]
    return p

def field_ac_points(i):
    row,col=divmod(i,3);cx=.525+.45*col;support=1.5-.16*row;ax=-.189+.054*row;az=.611+.032*col;ay0=[.286,.293,.300][col];ab=.160+.007*row;arx=cx+.199-.007*row
    p=rounded([(ax,.228,az),(ax,ay0,az),(ax,ay0,ab),(arx,ay0,ab),(arx,ay0,ab+.045)],.028)
    p+=bezier((arx,ay0,ab+.045),(arx,ay0,ab+.090),(arx,.288,ab+.120),(arx,.288,ab+.160),24)[1:]
    p+=rounded([(arx,.288,ab+.160),(arx,.288,support+.115),(cx-.100,.245,support+.115)],.028)[1:]
    return p

def build_fixed(b,root,meta,M,netports,acports,intentional):
    routes=meta['wiring_design']['fixed_routes'];apertures=meta['wiring_design']['real_apertures']
    apertures[:]=[r for r in apertures if bpy.data.objects.get(r.get('object',''))]
    def route(name,points,kind,bay=None,ends=None):
        old=bpy.data.objects.get(name)
        if old:intentional.append(name);remove(old)
        rad=.0028 if kind=='ac' else .0021
        ob=b.tube(name,points,rad,M['black'] if kind=='ac' else M['blue'],root,'wiring:'+kind,bay,'cable_fixed',8)
        rec={'name':name,'source_node_names':[name],'kind':kind,'bay_id':bay,'parent_node':root.name,'points_blender_m':[list(x) for x in points],'radius_mm':rad*1000,'length_mm':round(length(points),4),'min_sampled_radius_mm':min_radius(points)}
        if ends:rec['endpoint_node_names']=ends
        routes[:]=[r for r in routes if r['name']!=name];routes.append(rec);return rec
    # Keep the complete original downstream A and management routing. Only
    # the short front fan-out is rebuilt for the standard 2x24 switch face.
    source_routes=[(i,'FixedNetwork_A'+str(i)) for i in range(1,10)]+[(i,n) for i,n in enumerate(['FixedNetwork_Server','FixedNetwork_LockController','FixedNetwork_PDUManagement','FixedNetwork_UPSManagement','FixedNetwork_ExternalManagement'],34)]
    for port,name in source_routes:
        rec=next(r for r in routes if r['name']==name);pts=rec['points_blender_m'];sx,sy,sz=netports[port]
        # The first long line parallel X ends at the old fixed side lane.
        corner=[]
        for i,(a,c) in enumerate(zip(pts,pts[1:])):
            if abs(c[0]-a[0])>.01 and abs(c[1]-a[1])<1e-6 and abs(c[2]-a[2])<1e-6:corner.append(i)
        ix=corner[0];oldx=pts[ix+1][0];fy=pts[ix][1]
        # At the end of the following fillet the side lane has constant X/Y.
        j=ix+1
        while j+1<len(pts) and (abs(pts[j+1][0]-pts[j][0])>1e-7 or abs(pts[j+1][1]-pts[j][1])>1e-7):j+=1
        # Extend along its straight vertical to preserve the lower fillet.
        if j+1<len(pts) and abs(pts[j+1][0]-pts[j][0])<1e-6 and abs(pts[j+1][1]-pts[j][1])<1e-6:j+=1
        anchor=list(pts[j]);tail=[list(q) for q in pts[j+1:]]
        if name.startswith('FixedNetwork_A'):
            span=max(range(len(pts)-1),key=lambda q:abs(pts[q+1][0]-pts[q][0]));anchor[0]+=.006
            for q in range(j+1,span+1):tail[q-j-1][0]+=.006
        lane=anchor[0]
        prefix=rounded([(sx,sy,sz),(sx,fy,sz),(lane,fy,sz),anchor],.032)
        combined=prefix+tail
        if name.startswith('FixedNetwork_A'):
            # The external data riser stays at the rear-entry X of the fixed
            # socket, outside the preserved blue internal service lead.
            end=pts[-1];start=list(pts[span]);start[0]+=.006
            combined=prefix+[list(q) for q in tail[:span-j]]
            vi=max(range(span+1,len(pts)-1),key=lambda k:abs(pts[k+1][2]-pts[k][2]));rx=pts[vi][0];ry=start[1]
            leg=rounded([start,(rx,ry,start[2]),(rx,ry,end[2]),(end[0],.235,end[2]),end],.032)
            combined+=leg[1:]
        route(name,combined,'network',rec.get('bay_id'),['HybridSwitch_Plug_%02d'%port,rec['bay_id']+'_Refined_fixed_network_body'] if rec.get('bay_id') else None)
    targets=[('Server',(.012,.111,.514)),('LockController',(.202,.075,.466)),('PDUManagement',(0,.212,.605)),('UPSManagement',(-.15,.176,.32)),('ExternalManagement',(.22,.285,.80))]
    for i,(name,end) in enumerate(targets):
        sx,sy,sz=netports[34+i];lane=.293;yy=.280;front=-.270+.005*i;top=.862-.008*i
        inside={'Server':.223,'LockController':.247,'PDUManagement':.217,'UPSManagement':.252}.get(name,.235)
        fi={'LockController':.233,'UPSManagement':.225,'PDUManagement':.2344}.get(name,.230)
        q=[(sx,sy,sz),(sx,front,sz),(lane,front,sz),(lane,front,top),(lane,yy,top)]
        if name=='LockController':q += [(inside,yy,top),(inside,fi,top),(inside,fi,.600),(inside,.246,.520),(inside,.246,end[2]),(end[0],.246,end[2])]
        elif name!='ExternalManagement':q += [(inside,yy,top),(inside,fi,top),(inside,fi,end[2]),(end[0],fi,end[2])]
        q.append(end);route('FixedNetwork_'+name,rounded(q,.035 if name=='ExternalManagement' else .032),'network')
    for bay_id in ['A'+str(i) for i in range(1,10)]:
        old=next(r for r in routes if r['name']=='FixedAC_'+bay_id);pts=old['points_blender_m'];end=pts[-1];zn=end[2]
        vi=max((j for j in range(len(pts)-1) if abs(pts[j+1][2]-pts[j][2])>.050),default=0)
        rx,ry,_=pts[vi+1];rr=.035;start=(rx,ry,zn-rr);q=pts[:vi+2]+[start]
        q += [(rx,ry-rr+rr*math.cos(t),zn-rr+rr*math.sin(t)) for t in [math.pi*k/48 for k in range(1,25)]]
        sy=ry-rr;xx=end[0]+.002;dy=(sy-.200)/3
        q+=bezier((rx,sy,zn),(rx,sy-dy,zn),(xx,.200+dy,zn),(xx,.200,zn),24)[1:]
        q+=bezier((xx,.200,zn),(xx,.100,zn),(end[0],0,zn),end,40)[1:]
        route(old['name'],q,'ac',bay_id,['HybridPDU_Plug_%02d'%int(bay_id[1:]),bay_id+'_Refined_fixed_ac_socket_body'])
    # Re-seat the inherited EXTERNAL side-lead clamps on the new lead path.
    # Refined A in-bay mechanisms and their internal wiring are untouched.
    for bay_id in ['A'+str(i) for i in range(1,10)]:
        par=bpy.data.objects['Bay_'+bay_id];cx,_,base=par.location;wall=-.2235 if (int(bay_id[1:])-1)%3==0 else -.2244
        for kind in ['network','ac']:
            pp=next(r['points_blender_m'] for r in routes if r['name']==('FixedNetwork_' if kind=='network' else 'FixedAC_')+bay_id)
            for k,yy in enumerate([.015,.105]):
                hits=[]
                for a,z in zip(pp,pp[1:]):
                    if abs(z[1]-a[1])>1e-9 and min(a[1],z[1])<=yy<=max(a[1],z[1]):
                        t=(yy-a[1])/(z[1]-a[1]);hits.append([u+t*(v-u) for u,v in zip(a,z)])
                if not hits:continue
                xx,_,zz=hits[-1];localx=xx-cx;localz=zz-base
                ob=bpy.data.objects.get('Wiring_'+bay_id+'_'+kind+'_WallClip_'+str(k))
                if ob:ob.location.x=localx;ob.location.z=localz;intentional.append(ob.name)
                ob=bpy.data.objects.get('Wiring_'+bay_id+'_'+kind+'_WallClipBracket_'+str(k))
                if ob:ob.location.x=(wall+localx)/2;ob.location.z=localz-(.0028 if kind=='ac' else .0021)-.002;ob.dimensions.x=localx-wall;intentional.append(ob.name)
    for bay_id in ['A'+str(i) for i in range(1,10)]:
        for kind in ['network','ac']:
            pp=next(r['points_blender_m'] for r in routes if r['name']==('FixedNetwork_' if kind=='network' else 'FixedAC_')+bay_id)
            names=['Wiring_'+bay_id+'_'+kind+'_Grommet']+(['Wiring_'+bay_id+'_ACRailBranchGland'] if kind=='ac' else [])
            for name in names:
                ob=bpy.data.objects.get(name)
                if not ob:continue
                yy=ob.matrix_world.translation.y;hits=[]
                for a,z in zip(pp,pp[1:]):
                    if abs(z[1]-a[1])>1e-9 and min(a[1],z[1])<=yy<=max(a[1],z[1]):
                        t=(yy-a[1])/(z[1]-a[1]);hits.append(Vector([v+t*(w-v) for v,w in zip(a,z)]))
                if hits:ob.location=ob.parent.matrix_world.inverted()@hits[-1] if ob.parent else hits[-1];intentional.append(ob.name)
    # The inherited mains inlet remains connected at the same terminal, with
    # its enclosure moved down20mm to clear the new low-level AC branches.
    inlet=bpy.data.objects.get('Mains_Inlet')
    if inlet:inlet.location.z-=.020;intentional.append(inlet.name)
    for old in [o for o in bpy.context.scene.objects if o.name.startswith('Wiring_Module_AC_OpeningEdge') or ('Module_' in o.name and o.name.endswith('network_EdgeGrommet'))]:
        intentional.append(old.name);remove(old)

    # Real horizontal 24-position rear patch rack. Separate plug bodies on
    # both faces make the connection to the field circuits explicit.
    key='wiring:patch_panel';zplate=.910;yplate=.312
    for y in [.303,.320]:b.box('HybridRearPatch_Edge',(0,y,zplate),(.400,.002,.002),M['steel'],root,key,bevel=.0003,role='service')
    for i in range(25):
        x=-.192+i*.016;b.box('HybridRearPatch_Web',(x,yplate,zplate),(.003,.016,.002),M['steel'],root,key,bevel=.0003,role='service')
    for x in [-.230,.230]:b.box('HybridRearPatch_Mount',(x,.300,zplate),(.060,.026,.003),M['steel'],root,key,bevel=.0004,role='fastener')
    for x in [-.260,.260]:
        b.box('HybridRearPatch_MountRiser',(x,.248,.840),(.006,.006,.140),M['steel'],root,key,bevel=.0004,role='fastener')
        b.box('HybridRearPatch_MountReturn',(x,.280,zplate),(.006,.064,.003),M['steel'],root,key,bevel=.0004,role='fastener')
    for i in range(24):
        code='B'+str(i+1);x=rear_patch_x(i)
        for label,z in [('Input',.923),('Output',.897)]:
            o=b.box('HybridRearPatch_'+label+'_'+code,(x,yplate,z),(.013,.016,.018),M['blue'],root,key,code,.0007,'connector');o['port_number']=i+10
        b.box('HybridRearPatch_Coupler_'+code,(x,yplate,zplate),(.012,.014,.022),M['black'],root,key,code,.0005,'connector')
    # Source jumpers occupy two separated height bands; in each band the
    # monotonic fan-out preserves conductor ordering across the cabinet.
    for i in range(24):
        code='B'+str(i+1);port=i+10
        route('HybridNetwork_SwitchToPatch_'+code,switch_jumper_points(i),'network',code,['HybridSwitch_Plug_%02d'%port,'HybridRearPatch_Input_'+code])
        route('FixedNetwork_'+code,field_network_points(i),'network',code,['HybridRearPatch_Output_'+code,code+'_FixedNetworkSocket'])
        route('FixedAC_'+code,field_ac_points(i),'ac',code,['HybridPDU_Plug_%02d'%port,code+'_FixedACSocket'])
    if '--routes-only' in sys.argv:return routes
    # Support bars attach to the actual per-bay rear plates, with hollow
    # clips surrounding each present vertical cable. Bottom trays have legs
    # seated on the preserved58mm high structural floor.
    def clip(name,loc,inner,outer):
        vv=[];ff=[];n=12;h=.004
        for rad in [outer,inner]:
            for zz in [-h,h]:
                for j in range(n):vv.append((rad*math.cos(j*math.tau/n),rad*math.sin(j*math.tau/n),zz))
        for i in range(n):
            j=(i+1)%n;ff.extend([(i,j,n+j,n+i),(2*n+j,2*n+i,3*n+i,3*n+j),(j,i,2*n+i,2*n+j),(n+i,n+j,3*n+j,3*n+i)])
        me=bpy.data.meshes.new(name);me.from_pydata(vv,[],ff);me.materials.append(M['black']);o=bpy.data.objects.new(name,me);b.collection.objects.link(o);o.parent=root;o.location=loc;b.mark(o,'wiring:ducts',role='service')
    for c in range(3):
        cx=.525+c*.450
        for kind,x,y in [('network',cx-.145,.312),('ac',cx+.175,.288)]:
            bar_y=y-.006 if kind=='network' else y+.006
            width=.084
            for z in [.42,.60,.92,1.24,1.56]:
                b.box('Hybrid_'+kind+'_CableSupport_%d'%c,(x,bar_y,z),(width,.004,.012),M['steel'],root,'wiring:ducts',bevel=.0004,role='service')
                b.box('Hybrid_'+kind+'_SupportBracket_%d'%c,(x,.299,z),(.028,.014,.002),M['steel'],root,'wiring:ducts',bevel=.0004,role='fastener')
                for row in range(8):
                    support=1.5-.16*row;end=support+(.090 if kind=='network' else .115)
                    if z>end-.030:continue
                    xx=cx-.120-.007*row if kind=='network' else cx+.199-.007*row
                    clip('Hybrid_'+kind+'_VerticalClip_%d_%d'%(c,row),(xx,y,z),.0026 if kind=='network' else .0033,.0045 if kind=='network' else .0040)
    for kind,yy,zz,depth in [('ac',.2915,.150,.023),('network',.268,.205,.028)]:
        b.box('Hybrid_'+kind+'_BottomTrough',(.975,yy,zz),(1.310,depth,.002),M['steel'],root,'wiring:ducts',bevel=.0004,role='service')
        for xx in [.34,.975,1.61]:
            b.box('Hybrid_'+kind+'_TroughLeg',(xx,yy,(.058+zz-.001)/2),(.012,.012,zz-.001-.058),M['steel'],root,'wiring:ducts',bevel=.0005,role='fastener')
    # Hollow, numbered module passage frames are added only where actual
    # routes cross original sheet metal; booleans leave a real opening.
    bpy.context.view_layer.update()
    new_routes=[r for r in routes if not r['name'].startswith('HybridNetwork_SwitchToPatch')]
    candidate_panels=[o for o in bpy.context.scene.objects if o.type=='MESH' and (o.name.startswith(('Housing_','Right_Partition')) or o.name.endswith('_RearServicePlate') or 'RearPost' in o.name or o.name.startswith('Center_FrontFrame') or o.name.startswith('Equipment_RearMountFrame') or (o.name.startswith('Wiring_A') and any(t in o.name for t in ['Backplate','EntryPlate','DataRiser_Fold'])) or (o.name.startswith('A') and o.name.endswith('_RearServiceRail')))]
    def cut_rect(target,center,dims,label):
        bpy.ops.mesh.primitive_cube_add(size=1,location=center);cu=bpy.context.object;cu.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        bpy.context.view_layer.objects.active=target
        if target.data.users>1:target.data=target.data.copy()
        mod=target.modifiers.new(label,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cu
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
            if not target.data.vertices or not target.data.polygons:
                raise ValueError('Service passage removed all structure: '+target.name)
        finally:bpy.data.objects.remove(cu,do_unlink=True)
    # Route-plane crossings are grouped by panel to avoid overlapping bores.
    crossings={}
    for pan in candidate_panels:
        bb=[pan.matrix_world@Vector(v) for v in pan.bound_box];lo=[min(v[j] for v in bb) for j in range(3)];hi=[max(v[j] for v in bb) for j in range(3)];axis=min(range(3),key=lambda j:hi[j]-lo[j])
        if hi[axis]-lo[axis]>(.040 if 'RearPost' in pan.name or 'FrontFrame' in pan.name or pan.name.endswith('_RearServiceRail') else .012):continue
        plane=(lo[axis]+hi[axis])/2
        for r in new_routes:
            for aa,zz in zip(r['points_blender_m'],r['points_blender_m'][1:]):
                # Clip the complete centreline segment against the solid's
                # expanded box, not only one nominal centre plane. This also
                # catches a corner entering a post through its adjacent face.
                t0,t1=0.,1.;valid=True;rad=r['radius_mm']/1000
                for kk in range(3):
                    delta=zz[kk]-aa[kk];low=lo[kk]-rad;high=hi[kk]+rad
                    if abs(delta)<1e-10:
                        if not low<=aa[kk]<=high:valid=False;break
                    else:
                        ta=(low-aa[kk])/delta;tb=(high-aa[kk])/delta;t0=max(t0,min(ta,tb));t1=min(t1,max(ta,tb))
                        if t0>t1:valid=False;break
                if valid:
                    for t in [t0,t1]:
                        pp=[v+t*(w-v) for v,w in zip(aa,zz)];pp[axis]=plane
                        crossings.setdefault(pan.name,[]).append((pp,axis,r))
    for name,hits in crossings.items():
        pan=bpy.data.objects[name]
        if name in ['Wiring_A%d_ACRiser_Backplate'%i for i in range(3)]:
            # Replace the old triangulated circular-hole slab with the same
            # bounded slab before making the three larger replacement slots.
            # Exact Boolean on the old near-tangent circle/rectangle boundary
            # incorrectly discarded the whole plate at the third cut.
            import bmesh
            vv=[tuple(v) for v in pan.bound_box];materials=list(pan.data.materials)
            me=bpy.data.meshes.new(name+'_ReplacementSlab')
            me.from_pydata(vv,[],[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)])
            bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
            for mat in materials:me.materials.append(mat)
            pan.data=me
        pbb=[pan.matrix_world@Vector(v) for v in pan.bound_box];panel_lo=[min(q[k] for q in pbb) for k in range(3)];panel_hi=[max(q[k] for q in pbb) for k in range(3)]
        # Each compact cluster gets an open rectangular edge-protected slot.
        axis=hits[0][1];other=[j for j in range(3) if j!=axis]
        groups=[]
        for p,ax,r in hits:
            group=next((g for g in groups if all(abs(p[k]-g[0][0][k])<.080 for k in other)),None)
            if group is None:group=[];groups.append(group)
            group.append((p,ax,r))
        changed=True
        while changed:
            changed=False
            for ia in range(len(groups)):
                if changed:break
                for ib in range(ia+1,len(groups)):
                    def bounds(gg,k):return (min(p[k]-r['radius_mm']/1000-.006 for p,_,r in gg),max(p[k]+r['radius_mm']/1000+.006 for p,_,r in gg))
                    if all(bounds(groups[ia],k)[0]<=bounds(groups[ib],k)[1]+.005 and bounds(groups[ib],k)[0]<=bounds(groups[ia],k)[1]+.005 for k in other):
                        groups[ia]+=groups.pop(ib);changed=True;break
        for gidx,g in enumerate(groups):
            lo=[min(p[k]-r['radius_mm']/1000-.006 for p,_,r in g) for k in range(3)];hi=[max(p[k]+r['radius_mm']/1000+.006 for p,_,r in g) for k in range(3)];center=[(a+z)/2 for a,z in zip(lo,hi)];dims=[z-a for a,z in zip(lo,hi)];dims[axis]=.040
            cut_rect(pan,center,dims,'Hybrid real service passage');intentional.append(name)
            apertures.append({'object':name,'shape':'rectangle','center_world_blender_m':center,'axis':'XYZ'[axis],'dimensions_mm':[x*1000 for x in dims],'inner_clearance_mm':6,'route_names':sorted(set(r['name'] for _,_,r in g))})
            if 'RearPost' in name:
                # Forward U reinforcement remains ahead of the rear-door
                # fold sweep; low bus lines pass behind its front upright.
                z0=min(.100,lo[2]-.030);z1=max(.320,hi[2]+.030)
                b.box('Hybrid_ServiceSlot_Forward_'+name,(center[0],.254,(z0+z1)/2),(.014,.004,z1-z0),M['steel'],root,'wiring:feedthrough',bevel=.0004,role='service')
                for zz in [z0,z1]:b.box('Hybrid_ServiceSlot_Return_'+name,(center[0],.277,zz),(.014,.046,.002),M['steel'],root,'wiring:feedthrough',bevel=.0004,role='service')
            else:
                for edge_axis in other:
                    span_axis=next(k for k in other if k!=edge_axis)
                    for bound in [lo[edge_axis],hi[edge_axis]]:
                        if bound<=panel_lo[edge_axis]+.002 or bound>=panel_hi[edge_axis]-.002:continue
                        slo=max(lo[span_axis],panel_lo[span_axis]);shi=min(hi[span_axis],panel_hi[span_axis])
                        cc=center.copy();cc[edge_axis]=bound;cc[span_axis]=(slo+shi)/2;dd=[.002,.002,.002];dd[axis]=.002;dd[span_axis]=shi-slo
                        b.box('Hybrid_ServiceOpening_Edge_'+name,cc,dd,M['black'],root,'wiring:feedthrough',bevel=.0002,role='service')
    meta['wiring_design'].update(status='hybrid_candidate_requires_independent_audit',manufacturing_validated=False,script='scripts/hybrid/build_hybrid.py')
    meta['components']['wiring:patch_panel']={'title':'右24仓后部配线端接板','dimensions_mm':[400,26,46],'basis':'model','notes':'24个独立双面RJ45耦合端接，交换机至端接板跳线与后部固定支线分别可辨；端接外形为待选型示意。'}
    meta['wiring_view']['fixed_component_keys']=list(dict.fromkeys(meta['wiring_view']['fixed_component_keys']+['wiring:patch_panel']))
    return routes
