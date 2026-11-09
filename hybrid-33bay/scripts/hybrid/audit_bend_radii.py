"""Read-only sampled fixed-route bend check; dimensions are design assumptions."""
import hashlib
import json
import math
import sys
from pathlib import Path

source = Path(sys.argv[1]).resolve()
metadata = json.loads(source.read_text())


def sampled_radius(points):
    best = math.inf
    index = None
    for i, (a, b, c) in enumerate(zip(points, points[1:], points[2:]), 1):
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - b[k] for k in range(3)]
        w = [c[k] - a[k] for k in range(3)]
        cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        area2 = math.sqrt(sum(x*x for x in cross))
        if area2 < 1e-12:
            continue
        radius = math.prod(math.sqrt(sum(x*x for x in q)) for q in [u, v, w]) / (2*area2) * 1000
        if radius < best:
            best, index = radius, i
    return (None if math.isinf(best) else best), index


rows = []
for route in metadata['wiring_design']['fixed_routes']:
    radius, point_index = sampled_radius(route['points_blender_m'])
    target = 25 if route['kind'] == 'ac' else 20
    rows.append(dict(name=route['name'], kind=route['kind'], minimum_sampled_radius_mm=radius,
                     point_index=point_index, design_target_mm=target,
                     passed=radius is None or radius >= target))
report = dict(metadata_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), route_count=len(rows),
              status='passed' if all(r['passed'] for r in rows) else 'review_required', routes=rows,
              method='Circumradius of every three consecutive sampled centreline points, in millimetres.',
              limits='Checks the existing geometric design targets only. Actual cable specification, bend-fatigue and installation qualification remain unverified.')
destination = source.with_name('fixed_bend_radius_audit.json')
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(report['status'], len(rows), str(destination))
