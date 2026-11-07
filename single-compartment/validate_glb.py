"""Read-only structural audit of the exported single-compartment GLB."""
import json
import math
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
magic, version, size = struct.unpack_from('<4sII', data)
assert magic == b'glTF' and version == 2 and size == len(data)
offset = 12
chunks = {}
while offset < len(data):
    length, kind = struct.unpack_from('<II', data, offset)
    chunks[kind] = data[offset + 8:offset + 8 + length]
    offset += 8 + length
doc = json.loads(chunks[0x4e4f534a])
binary = chunks.get(0x004e4942, b'')
assert all('uri' not in item for item in doc.get('buffers', [])), 'GLB needs external buffers'
assert all('uri' not in item for item in doc.get('images', [])), 'GLB needs external images'
components = set()
nodes = doc.get('nodes', [])
names = {node.get('name', '') for node in nodes}
for name in ('SingleCabinetRoot', 'SingleDoorPivot', 'SingleTray', 'Laptop'):
    assert name in names, f'Missing interaction node {name}'
for node in nodes:
    assert all(0 <= i < len(nodes) for i in node.get('children', []))
    values = node.get('matrix', []) + node.get('translation', []) + node.get('rotation', []) + node.get('scale', [])
    assert all(math.isfinite(v) for v in values)
    if node.get('extras', {}).get('component_key'):
        components.add(node['extras']['component_key'])
    assert 'camera' not in node, 'Export contains studio camera'
    assert 'KHR_lights_punctual' not in node.get('extensions', {}), 'Export contains studio lights'
sizes = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
formats = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
def values(index):
    accessor = doc['accessors'][index]
    assert 'sparse' not in accessor, 'Sparse accessor requires separate verification'
    view = doc['bufferViews'][accessor['bufferView']]
    fmt, width = formats[accessor['componentType']]
    count = sizes[accessor['type']]
    stride = view.get('byteStride', count * width)
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    assert start + max(0, accessor['count'] - 1) * stride + width * count <= len(binary)
    return [struct.unpack_from('<' + fmt * count, binary, start + i * stride) for i in range(accessor['count'])]
triangles = 0
primitive_count = 0
normal_lengths = []
for mesh in doc.get('meshes', []):
    for primitive in mesh['primitives']:
        primitive_count += 1
        assert primitive.get('mode', 4) == 4, 'Non-triangle primitive'
        attrs = primitive['attributes']
        points = values(attrs['POSITION'])
        assert all(math.isfinite(v) for point in points for v in point)
        assert 'NORMAL' in attrs, 'Missing exported normals'
        normals = values(attrs['NORMAL'])
        assert len(normals) == len(points)
        normal_lengths += [math.sqrt(sum(v*v for v in n)) for n in normals]
        if 'indices' in primitive:
            indices = values(primitive['indices'])
            assert all(0 <= i[0] < len(points) for i in indices)
            assert len(indices) % 3 == 0
            triangles += len(indices) // 3
        else:
            assert len(points) % 3 == 0
            triangles += len(points) // 3
assert min(normal_lengths) > .98 and max(normal_lengths) < 1.02, 'Non-unit normals'
report = {
    'file': path.name, 'size_bytes': len(data), 'gltf_version': version,
    'nodes': len(nodes), 'meshes': len(doc.get('meshes', [])), 'primitives': primitive_count,
    'triangles': triangles, 'materials': len(doc.get('materials', [])),
    'component_keys': sorted(components),
    'extensions_used': doc.get('extensionsUsed', []),
    'normal_length_range': [min(normal_lengths), max(normal_lengths)],
    'checks': ['valid GLB header', 'embedded buffers and textures', 'required interaction nodes',
               'finite geometry and transforms', 'valid index ranges', 'unit vertex normals',
               'no studio cameras or lights'],
    'limits': 'This file audit does not establish mechanical clearance, manufacturability or load capacity.'
}
out = path.parent / 'glb_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
