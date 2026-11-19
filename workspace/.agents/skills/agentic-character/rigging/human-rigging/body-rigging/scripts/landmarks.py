"""Geometric joint prediction on a headless A-pose, normalized to unit height.

Coordinates are forward, left, up. Only the analysis copy welds UV seams.
"""
import numpy as np


def midpoint(points):
    if not len(points):
        raise ValueError("Empty anatomical section; inspect rest axes and A-pose")
    return (points.min(axis=0) + points.max(axis=0)) / 2


def normalize(vector):
    return vector / max(np.linalg.norm(vector), 1e-12)


def section(triangles, axis, level):
    heights = triangles @ axis
    faces = triangles[(heights.min(1) < level) & (heights.max(1) >= level)]
    a, b = faces, np.roll(faces, -1, axis=1)
    u, v = a @ axis, b @ axis
    cross = (u < level) != (v < level)
    return a[cross] + (b[cross] - a[cross]) * ((level-u[cross])/(v[cross]-u[cross]))[:, None]


def contours(points):
    if not len(points):
        return []
    vertices, index = np.unique(points.round(6), axis=0, return_inverse=True)
    parent = list(range(len(vertices)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in index.reshape(-1, 2):
        parent[root(a)] = root(b)
    components = {}
    for i, point in enumerate(vertices):
        components.setdefault(root(i), []).append(point)
    return [midpoint(np.asarray(part)) for part in components.values() if len(part) >= 3]


DIGITS = ("Thumb", "IndexFinger", "MiddleFinger", "RingFinger", "LittleFinger")


def predict_hand(triangles, sign, span, points):
    hand = triangles[(sign*triangles[:, :, 1]).min(1) > .63*span]
    centers = [midpoint(points[abs(sign*points[:, 1]-t*span) < .018*span])
               for t in (.70, .88)]
    axis = normalize(centers[1]-centers[0])
    maximum = (hand @ axis).max()
    levels = np.linspace(maximum-.14, maximum-.00015, 200)
    slices = [contours(section(hand, axis, z)) for z in levels]
    five = [i for i, loops in enumerate(slices) if len(loops) == 5]
    if not five:
        raise ValueError("Cannot resolve five digits; inspect the isolated hand and its projection")
    station = five[len(five)//2]
    chains = []
    for seed in sorted(slices[station], key=lambda p: -p[0]):
        path = {station: seed}
        for step in (1, -1):
            prev = seed
            for i in range(station+step, len(levels) if step == 1 else -1, step):
                if not slices[i]:
                    break
                near = min(slices[i], key=lambda x: np.linalg.norm(x-prev))
                if np.linalg.norm(near-prev) > .004 or (step < 0 and len(slices[i]) == 1):
                    break
                path[i], prev = near, near
        first, last = min(path), max(path)
        if last-first < 8:
            raise ValueError("Digit section chain too short; inspect the localized fingertip")
        chains.append(np.array([path[round(first+(last-first)*t)] for t in (0,.44,.76,1)]))
    wrist_level = min(c[0] @ axis for c in chains)-.029
    wrist = midpoint(section(hand, axis, wrist_level))
    return wrist, chains


def predict(points, faces):
    triangles = points[faces]
    up = np.array([0., 0., 1.])
    def cut(z):
        return section(triangles, up, z)
    def central(z):
        p = cut(z)
        return midpoint(p[abs(p[:,1]) < .038])
    def bridged(z):
        return np.min(abs(cut(z)[:,1])) < .0015
    crotch = next((z for z in np.linspace(.36,.75,175) if bridged(z)), None)
    if crotch is None:
        raise ValueError("Cannot detect the crotch bridge")
    thigh_section = cut(crotch-.025)
    thigh = thigh_section[(thigh_section[:,1]>0) & (thigh_section[:,1]<.52*points[:,1].max())]
    hip_z = crotch+.40*np.ptp(thigh[:,1])
    shoulders_z = .94
    neck_z = .98
    bones = {}
    spine = [central(z) for z in (hip_z, hip_z+.25*(shoulders_z-hip_z),
             hip_z+.51*(shoulders_z-hip_z), hip_z+.73*(shoulders_z-hip_z), neck_z, .998)]
    for name, a, b in zip(("Hips","Spine","Chest","Upper Chest","Neck"), spine, spine[1:]):
        bones["DEF-"+name] = (a,b)
    bones["DEF-Head"] = (spine[-1], spine[-1]+[0,0,.08])
    tips = {}
    for sign, side, short in ((1,"Left","L"),(-1,"Right","R")):
        prefix = "DEF-"+side+" "
        span = max(sign*points[:,1])
        def leg(z):
            p = cut(z)
            return p[(sign*p[:,1] > 0) & (sign*p[:,1] < .55*span)]
        def narrow(low, high):
            levels = np.linspace(low, high, 36)
            return min(levels, key=lambda z: np.ptp(leg(z)[:,1]))
        hip = central(hip_z)
        hip[1] = midpoint(leg(crotch-.018))[1]
        knee = midpoint(leg(narrow(.56*crotch,.72*crotch)))
        ankle = midpoint(leg(narrow(.065*crotch,.17*crotch)))
        foot = points[(sign*points[:,1]>0) & (points[:,2]<ankle[2])]
        toe = midpoint(foot[foot[:,0]>np.quantile(foot[:,0],.72)])
        toe_end = midpoint(foot[foot[:,0]>np.quantile(foot[:,0],.97)])
        wrist, chains = predict_hand(triangles,sign,span,points)
        sh = cut(shoulders_z)
        shoulder = midpoint(sh[sign*sh[:,1]>.60*max(sign*sh[:,1])])
        el_level = .5*(shoulder[2]+wrist[2])
        elbow_cut = cut(el_level)
        elbow = midpoint(elbow_cut[sign*elbow_cut[:,1]>.78*max(sign*elbow_cut[:,1])])
        palm = wrist+.20*(chains[2][0]-wrist)
        for part,a,b in (("leg",hip,knee),("knee",knee,ankle),("ankle",ankle,toe),
                         ("toe",toe,toe_end),("arm",shoulder,elbow),("elbow",elbow,wrist),
                         ("wrist",wrist,palm)):
            bones[prefix+part]=(a,b)
        for k,(digit,chain) in enumerate(zip(DIGITS,chains)):
            if k:
                bones["DEF-"+digit+"Palm_"+short]=(palm,chain[0])
            for j,(a,b) in enumerate(zip(chain,chain[1:])):
                name=f"DEF-{digit}{j+int(k>0)}_{short}"
                bones[name]=(a,b)
            tips[name]=int(np.argmin(np.linalg.norm(points-chain[-1],axis=1)))
    return bones, tips, crotch
