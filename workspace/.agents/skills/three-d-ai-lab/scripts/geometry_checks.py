"""Static inter-object triangle crossing checks; no volume or animation guarantee."""
import gc
import numpy as np
import bpy
from mathutils.bvhtree import BVHTree

def intersect_segments(a,b):
    n=len(a);points=[]
    for source,target in [(a,b),(b,a)]:
        e0=target[:,1]-target[:,0];e1=target[:,2]-target[:,0]
        normal=np.cross(e0,e1);norm=np.linalg.norm(normal,axis=1)
        normal=normal/np.maximum(norm[:,None],1e-30)
        d00=np.sum(e0*e0,1);d01=np.sum(e0*e1,1);d11=np.sum(e1*e1,1)
        det=d00*d11-d01*d01
        for i,j in [(0,1),(1,2),(2,0)]:
            start=source[:,i];delta=source[:,j]-start
            denom=np.sum(normal*delta,1)
            valid=(abs(denom)>1e-12)&(abs(det)>1e-30)
            t=np.sum(normal*(target[:,0]-start),1)/np.where(valid,denom,1)
            p=start+t[:,None]*delta;v=p-target[:,0]
            d20=np.sum(v*e0,1);d21=np.sum(v*e1,1)
            u=(d11*d20-d01*d21)/np.where(valid,det,1)
            w=(d00*d21-d01*d20)/np.where(valid,det,1)
            valid&=(t>=-1e-8)&(t<=1+1e-8)&(u>=-1e-7)&(w>=-1e-7)&(u+w<=1+1e-7)
            points.append(np.where(valid[:,None],p,np.nan))
    pts=np.stack(points,1)
    lengths=np.zeros(n);segments=np.zeros((n,2,3))
    for i in range(6):
        for j in range(i):
            d=np.linalg.norm(pts[:,i]-pts[:,j],axis=1)
            use=np.isfinite(d)&(d>lengths)
            lengths[use]=d[use];segments[use,0]=pts[use,i];segments[use,1]=pts[use,j]
    return lengths,segments


def clip_segment_lengths(segments, region):
    """Length of each segment inside an inclusive axis-aligned region."""
    start=segments[:,0];delta=segments[:,1]-start
    lower=np.zeros(len(segments));upper=np.ones(len(segments))
    valid=np.ones(len(segments),dtype=bool)
    for axis in range(3):
        parallel=abs(delta[:,axis])<1e-15
        valid &= ~parallel | ((start[:,axis]>=region['min'][axis]) & (start[:,axis]<=region['max'][axis]))
        den=np.where(parallel,1.,delta[:,axis])
        a=(region['min'][axis]-start[:,axis])/den
        b=(region['max'][axis]-start[:,axis])/den
        lower=np.maximum(lower,np.where(parallel,-np.inf,np.minimum(a,b)))
        upper=np.minimum(upper,np.where(parallel,np.inf,np.maximum(a,b)))
    return np.where(valid,np.maximum(upper-lower,0)*np.linalg.norm(delta,axis=1),0)


def mesh_data(name):
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != 'MESH' or obj.modifiers or obj.data.shape_keys:
        raise ValueError('Geometry checks require named static meshes without modifiers/morphs: ' + name)
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = np.empty((len(mesh.vertices), 3), dtype=np.float64)
    mesh.vertices.foreach_get('co', points.ravel())
    matrix = np.array(obj.matrix_world)
    points = np.einsum('ij,kj->ki', matrix[:3,:3], points) + matrix[:3,3]
    if not np.isfinite(points).all():
        raise ValueError('Nonfinite mesh coordinates')
    triangles = np.empty((len(mesh.loop_triangles), 3), dtype=np.int32)
    mesh.loop_triangles.foreach_get('vertices', triangles.ravel())
    xyz = points[triangles]
    if not len(xyz):
        raise ValueError('Empty mesh surface')
    return points, triangles, xyz.min(1), xyz.max(1)


def crossing_count(a, b, region=None):
    pa,ta,alo,ahi = a
    pb,tb,blo,bhi = b
    lo = np.maximum(alo.min(0), blo.min(0))
    hi = np.minimum(ahi.max(0), bhi.max(0))
    if region is not None:
        lo=np.maximum(lo,region['min']);hi=np.minimum(hi,region['max'])
    if (lo>hi).any():
        return {'candidate_pairs': 0, 'confirmed_crossings': 0, 'bounds_disjoint': True}
    ia = np.flatnonzero(((ahi>=lo)&(alo<=hi)).all(1))
    ib = np.flatnonzero(((bhi>=lo)&(blo<=hi)).all(1))
    A = BVHTree.FromPolygons(pa.tolist(),ta[ia].tolist(),all_triangles=True,epsilon=0)
    B = BVHTree.FromPolygons(pb.tolist(),tb[ib].tolist(),all_triangles=True,epsilon=0)
    candidates = np.asarray(A.overlap(B), dtype=np.int64).reshape(-1,2)
    del A,B
    gc.collect()
    confirmed = 0
    for offset in range(0,len(candidates),8192):
        c = candidates[offset:offset+8192]
        lengths,segments = intersect_segments(pa[ta[ia[c[:,0]]]],pb[tb[ib[c[:,1]]]])
        if region is not None:
            lengths=np.minimum(lengths,clip_segment_lengths(segments,region))
        confirmed += int((lengths>1e-7).sum())
    return {'candidate_pairs': len(candidates), 'confirmed_crossings': confirmed,
            'unconfirmed_or_tangent_candidates': len(candidates)-confirmed}


def evaluate(spec):
    names = {n for pair in spec['surface_pairs'] for n in pair['objects']}
    meshes = {name: mesh_data(name) for name in names}
    results = []
    for pair in spec['surface_pairs']:
        a,b = pair['objects']
        row = crossing_count(meshes[a],meshes[b],pair.get('region'))
        if 'region' in pair:row['region']=pair['region']
        row.update(objects=[a,b], max_crossings=pair.get('max_crossings',0))
        row['status'] = 'pass' if row['confirmed_crossings']<=row['max_crossings'] else 'fail'
        results.append(row)
    return {'status': 'pass' if all(r['status']=='pass' for r in results) else 'fail',
            'surface_pairs': results, 'segment_threshold_scene_units': 1e-7,
            'scope': 'Static noncoplanar surface crossings for explicitly named pairs',
            'not_certified': ['Coplanar overlap/contact', 'Solid containment or penetration depth',
                              'Self-intersections', 'Dynamic poses', 'Visual quality']}
