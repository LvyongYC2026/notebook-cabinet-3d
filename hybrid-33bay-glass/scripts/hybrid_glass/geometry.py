"""Small static-geometry builder; existing meshes and morphs are never rebaked."""
import bpy
import math


class Builder:
    def __init__(self, collection):
        self.collection = collection
        self.objects = []
        self.mesh_pool = {}

    def mark(self, obj, key, bay_id, role, variant='glass'):
        obj['component_key'] = key
        obj['basis'] = 'model'
        obj['bay_id'] = bay_id
        obj['hybrid_role'] = role
        if variant is not None:
            obj['drawer_front_variant'] = variant
            obj['action'] = 'drawer'
        else:
            obj['drawer_front_shared'] = True
            obj['initial_hidden'] = False
        self.objects.append(obj)
        return obj

    def empty(self, name, parent, key, bay_id):
        obj = bpy.data.objects.new(name, None)
        self.collection.objects.link(obj)
        obj.parent = parent
        obj.empty_display_size = .01
        return self.mark(obj, key, bay_id, 'drawer_front')

    def box(self, name, loc, dims, material, parent, key, bay_id, role='drawer_front', bevel=.0004):
        token = (tuple(round(d, 9) for d in dims), material.name, bevel)
        mesh = self.mesh_pool.get(token)
        if mesh is None:
            x, y, z = [d/2 for d in dims]
            verts = [(a*x, b*y, c*z) for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
            faces = [(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6),(0,1,3,2),(4,6,7,5)]
            mesh = bpy.data.meshes.new(name+'_Mesh')
            mesh.from_pydata(verts, [], faces)
            mesh.materials.append(material)
            self.mesh_pool[token] = mesh
            obj = bpy.data.objects.new(name, mesh)
            self.collection.objects.link(obj)
            if bevel:
                modifier = obj.modifiers.new('Manufactured edge radius', 'BEVEL')
                modifier.width = min(bevel, min(dims)*.22)
                modifier.segments = 2
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                self.mesh_pool[token] = obj.data
        else:
            obj = bpy.data.objects.new(name, mesh)
            self.collection.objects.link(obj)
        obj.parent = parent
        obj.location = loc
        return self.mark(obj, key, bay_id, role)

    def label(self, name, body, loc, size, material, parent, key, bay_id, font=None):
        curve = bpy.data.curves.new(name, 'FONT')
        curve.body = body
        curve.size = size
        curve.align_x = 'CENTER'
        curve.extrude = .00004
        if font:
            curve.font = font
        curve.materials.append(material)
        obj = bpy.data.objects.new(name, curve)
        self.collection.objects.link(obj)
        obj.parent = parent
        obj.location = loc
        obj.rotation_euler = (math.pi/2, 0, 0)
        return self.mark(obj, key, bay_id, 'label')

    def shared_mesh(self, name, vertices, faces, loc, material, parent, key, bay_id, role):
        import bmesh
        token = ('shared',tuple(tuple(v) for v in vertices),tuple(tuple(f) for f in faces),material.name)
        mesh = self.mesh_pool.get(token)
        if mesh is None:
            mesh = bpy.data.meshes.new(name+'_Mesh')
            mesh.from_pydata(vertices,[],faces)
            bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
            mesh.materials.append(material)
            self.mesh_pool[token] = mesh
        obj=bpy.data.objects.new(name,mesh);self.collection.objects.link(obj)
        obj.parent=parent;obj.location=loc
        return self.mark(obj,key,bay_id,role,None)
