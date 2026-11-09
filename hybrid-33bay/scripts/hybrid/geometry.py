"""Small bpy geometry helpers; all dimensions are metres, Z up, front -Y."""
import bpy, math, hashlib, struct
from mathutils import Vector

def material(name, color, metal=0, rough=.45, emission=0):
    m=bpy.data.materials.get('Hybrid | '+name)
    if m:return m
    m=bpy.data.materials.new('Hybrid | '+name);m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
    if emission:
        n.inputs['Emission Color'].default_value=(*color,1);n.inputs['Emission Strength'].default_value=emission
    return m

def gltf(points):return [[float(x),float(z),float(-y)] for x,y,z in points]
def lerp(a,b,n):return [tuple(Vector(a).lerp(Vector(b),i/(n-1))) for i in range(n)]
def bezier(a,b,c,d,n=32):
    return [tuple((1-t)**3*Vector(a)+3*(1-t)**2*t*Vector(b)+3*(1-t)*t*t*Vector(c)+t**3*Vector(d)) for t in [i/n for i in range(n+1)]]
def length(points):return sum((Vector(b)-Vector(a)).length for a,b in zip(points,points[1:]))*1000
def min_radius(points):
    out=[]
    for a,b,c in zip(points,points[1:],points[2:]):
        u=Vector(b)-Vector(a);v=Vector(c)-Vector(b);w=Vector(c)-Vector(a);cross=u.cross(w).length
        if cross>1e-12:out.append(u.length*v.length*w.length/(2*cross)*1000)
    return min(out) if out else None
def tube_vertices(points,r,sides=8):
    out=[]
    for i,p in enumerate(points):
        t=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])).normalized()
        axis=Vector((0,0,1)) if abs(t.z)<.97 else Vector((1,0,0))
        u=t.cross(axis).normalized();v=t.cross(u).normalized()
        for j in range(sides):out.append(tuple(Vector(p)+r*(u*math.cos(j*math.tau/sides)+v*math.sin(j*math.tau/sides))))
    return out
def tube_faces(n,s):
    ff=[]
    for i in range(n-1):
        for j in range(s):a=i*s+j;b=i*s+(j+1)%s;ff.append((a,b,b+s,a+s))
    return ff+[tuple(range(s-1,-1,-1)),tuple((n-1)*s+j for j in range(s))]

class Builder:
    def __init__(self,collection):self.collection=collection;self.objects=[];self.pool={}
    def mark(self,o,key,bay=None,role='structure'):
        o['component_key']=key;o['basis']='model';o['hybrid_role']=role
        if bay:o['bay_id']=bay
        self.objects.append(o);return o
    def empty(self,name,parent,key,bay=None,loc=(0,0,0),role='structure'):
        o=bpy.data.objects.new(name,None);self.collection.objects.link(o);o.parent=parent;o.location=loc;o.empty_display_size=.015
        return self.mark(o,key,bay,role)
    def box(self,name,loc,dims,mat,parent,key,bay=None,bevel=.0006,role='structure'):
        token=(tuple(dims),mat.name,bevel)
        me=self.pool.get(token)
        if me is None:
            x,y,z=[q/2 for q in dims]
            vv=[(a*x,b*y,c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
            ff=[(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6),(0,1,3,2),(4,6,7,5)]
            me=bpy.data.meshes.new(name+'_Mesh');me.from_pydata(vv,[],ff);me.materials.append(mat);self.pool[token]=me
        o=bpy.data.objects.new(name,me);self.collection.objects.link(o);o.parent=parent;o.location=loc
        if bevel:
            b=o.modifiers.new('Edge radius','BEVEL');b.width=min(bevel,min(dims)*.25);b.segments=2
        return self.mark(o,key,bay,role)
    def tube(self,name,points,r,mat,parent,key,bay=None,role='cable_fixed',sides=8):
        me=bpy.data.meshes.new(name+'_Mesh');me.from_pydata(tube_vertices(points,r,sides),[],tube_faces(len(points),sides));me.materials.append(mat)
        for f in me.polygons:f.use_smooth=True
        o=bpy.data.objects.new(name,me);self.collection.objects.link(o);o.parent=parent
        return self.mark(o,key,bay,role)
    def text(self,name,body,loc,size,mat,parent,key,bay=None,rotation=(math.pi/2,0,0)):
        cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.size=size;cu.align_x='CENTER';cu.extrude=.00004;cu.materials.append(mat)
        o=bpy.data.objects.new(name,cu);self.collection.objects.link(o);o.parent=parent;o.location=loc;o.rotation_euler=rotation
        return self.mark(o,key,bay,'label')
    def screw(self,name,loc,parent,key,bay=None):
        o=self.box(name,loc,(.005,.0015,.005),bpy.data.materials['Hybrid | Steel'],parent,key,bay,.001,'fastener')
        self.box(name+'_Slot',(loc[0],loc[1]-.0008,loc[2]),(.003,.0003,.0006),bpy.data.materials['Hybrid | Black'],parent,key,bay,0,'fastener')
        return o

def under(o,p):
    while o:
        if o==p:return True
        o=o.parent
    return False
def remove(o):
    for x in reversed([o,*o.children_recursive]):
        if x.name in bpy.data.objects:bpy.data.objects.remove(x,do_unlink=True)
def mark_hidden(o,value):
    for child in [o,*o.children_recursive]:child['initial_hidden']=value;child.hide_render=value;child.hide_set(value)
def native_cable(builder,name,closed,extended,r,mat,parent,tray,key,bay):
    o=builder.tube(name,closed,r,mat,parent,key,bay,'cable_dynamic')
    o.shape_key_add(name='Basis');k=o.shape_key_add(name='TrayExtended320mm')
    for v,p in zip(k.data,tube_vertices(extended,r)):v.co=p
    dr=k.driver_add('value').driver;dr.expression='min(max(-travel/0.32,0),1)'
    v=dr.variables.new();v.name='travel';v.type='TRANSFORMS';v.targets[0].id=tray;v.targets[0].transform_type='LOC_Y';v.targets[0].transform_space='LOCAL_SPACE'
    o['dynamicCable']=True;o['cable_kind']='network' if 'network' in name else 'power';return o
def controlled_u(travel,z,end_y,xa=-.199,r=.028,fixed_y=.175,loop_y=-.265):
    xb=xa+2*r;yc=loop_y-travel/2
    pts=lerp((xa,fixed_y,z),(xa,yc,z),18)
    pts += [((xa+xb)/2+r*math.cos(math.pi+i*math.pi/24),yc+r*math.sin(math.pi+i*math.pi/24),z) for i in range(1,25)]
    pts += lerp((xb,yc,z),(xb,end_y-travel,z),25)[1:]
    return pts

def bake_and_share(objects):
    dg=bpy.context.evaluated_depsgraph_get();cache={};pool={}
    for o in objects:
        if o.type!='MESH' or o.data.shape_keys:continue
        if o.modifiers:
            token=(o.data.as_pointer(),tuple((m.type,getattr(m,'width',0),getattr(m,'segments',0)) for m in o.modifiers))
            if token not in cache:
                me=bpy.data.meshes.new_from_object(o.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
                for i,m in enumerate(me.materials):me.materials[i]=m.original if m else None
                cache[token]=me
            o.modifiers.clear();o.data=cache[token]
        me=o.data;h=hashlib.sha256()
        for m in me.materials:h.update((m.name if m else '').encode())
        for v in me.vertices:h.update(struct.pack('<3f',*v.co))
        for f in me.polygons:h.update(struct.pack('<I',len(f.vertices)));h.update(struct.pack('<'+'I'*len(f.vertices),*f.vertices))
        digest=h.digest()
        if digest in pool:o.data=pool[digest]
        else:pool[digest]=me
    return len(pool)
