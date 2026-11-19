"""Fit reviewed root-to-tip guides to a hair mesh. Run with a SciPy Python."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra


def fit(mesh, guides):
    vertices=mesh['vertices']
    p,inv=np.unique(vertices.round(6),axis=0,return_inverse=True)
    edges=np.unique(np.sort(inv[mesh['edges']],axis=1),axis=0)
    a,b=edges[edges[:,0]!=edges[:,1]].T
    graph=coo_matrix((np.linalg.norm(p[a]-p[b],axis=1),(a,b)),shape=(len(p),len(p))).tocsr()
    graph=graph+graph.T
    names=['DEF-Head'];bones=[];columns=[];scores=[]
    for guide in guides:
        knots=np.array(guide['points'])
        width=guide['width']
        # Place free tips and first roots on the observed silhouette in 3D.
        # An attached child starts exactly at the fitted parent tail.
        for k in (0,-1):
            if k==0 and guide.get('parent'):
                knots[k]=next(b['tail'] for b in bones if b['name']==guide['parent'])
            else:
                nearest=np.argsort(np.linalg.norm(p-knots[k],axis=1))[:3]
                knots[k]=p[nearest].mean(0)
        # Refine intermediate points against a cross-section normal to the guide.
        for k in range(1,len(knots)-1):
            axis=knots[k+1]-knots[k-1];axis/=np.linalg.norm(axis)
            delta=p-knots[k];dist=np.linalg.norm(delta,axis=1)
            mask=(dist<width)&(abs(delta@axis)<width*.4)
            if mask.sum()>=3:
                correction=np.median(delta[mask],axis=0)
                knots[k]+=.65*(correction-axis*(correction@axis))
        lens=np.linalg.norm(np.diff(knots,axis=0),axis=1)
        arc=np.r_[0,np.cumsum(lens)]
        # Sample the path, then propagate affinity along mesh edges. A folded
        # neighboring strand can lie close in space but far along the surface.
        cost=np.full(len(p),np.inf);along=np.zeros(len(p))
        for k,length in enumerate(lens):
            for t in np.linspace(0,1,6):
                pos=knots[k]*(1-t)+knots[k+1]*t
                dist=np.linalg.norm(p-pos,axis=1);seeds=np.flatnonzero(dist<max(width*.48,dist.min()+.003))
                ds=dijkstra(graph,indices=seeds,min_only=True)+dist[seeds].min()
                better=ds<cost
                cost[better]=ds[better];along[better]=arc[k]+length*t
        radial=np.exp(-.5*(cost/width)**2)
        radial*=np.clip((3*width-cost)/width,0,1)
        fade=np.clip(along/(lens[0]*.8),0,1)
        fade=fade**2*(3-2*fade)
        if guide.get('parent'):fade=np.ones(len(p))
        # Interpolate segment influence in path length, including curved ends.
        centers=(arc[:-1]+arc[1:])*.5
        weights=np.stack([np.interp(along,centers,np.eye(len(lens))[i]) for i in range(len(lens))],axis=1)
        prefix='Hair.'+guide['name']
        for k in range(len(lens)):
            bone=prefix+'.'+str(k+1)
            parent=names[-1] if k else guide.get('parent','DEF-Head')
            names.append(bone);bones.append(dict(name=bone,parent=parent,head=knots[k].tolist(),tail=knots[k+1].tolist()))
        scores.append(radial);columns.append(weights*fade[:,None])
    affinities=np.stack(scores,axis=1)
    # Concentrate influence on the closest guide while retaining smooth borders.
    shares=affinities**4
    shares/=np.maximum(shares.sum(1,keepdims=True),1e-12)
    strength=np.clip(affinities.max(1)/.65,0,1)
    moving=np.concatenate([w*(shares[:,k]*strength)[:,None] for k,w in enumerate(columns)],axis=1)
    weights=np.column_stack([np.maximum(0,1-moving.sum(1)),moving])
    return bones,names,weights[inv]


if __name__=='__main__':
    mesh,spec,out=map(Path,sys.argv[1:])
    bones,names,w=fit(np.load(mesh),json.loads(spec.read_text()))
    np.savez(out,bones=json.dumps(bones),names=names,weights=w)
