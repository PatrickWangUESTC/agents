"""Blender entry point for fitting a fresh body rig from an assembled rest mesh."""
import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from landmarks import DIGITS, normalize, predict
from refine_body import distances, refine_body, smooth


def initial_weights(points, edges, bones, tips, crotch):
    unique, inverse = np.unique(points.round(6), axis=0, return_inverse=True)
    inverse = inverse.ravel()
    graph = [[] for _ in unique]
    for i,j in np.unique(np.sort(inverse[edges],axis=1),axis=0):
        if i != j:
            gap = float(np.linalg.norm(unique[i]-unique[j]))
            graph[i].append((j,gap))
            graph[j].append((i,gap))
    domains = {}
    for side in ("L","R"):
        terminal = [f"DEF-{d}{2 if d=='Thumb' else 3}_{side}" for d in DIGITS]
        paths = []
        for name in terminal:
            seed = np.zeros(len(unique),bool)
            seed[inverse[tips[name]]] = True
            paths.append(distances(graph,seed)[inverse])
        nearest = np.argmin(paths, axis=0)
        for k,d in enumerate(DIGITS):
            for name in bones:
                if name.startswith("DEF-"+d) and name.endswith("_"+side) and "Palm" not in name:
                    domains[name] = nearest == k
    columns = []
    for name,(a,b) in bones.items():
        direction = b-a
        along = np.clip(np.einsum("ij,j->i", points-a, direction)/(direction@direction),.04,.96)
        dist = np.linalg.norm(points-a-along[:,None]*direction,axis=1)
        score = (dist**2+(.00002 if name in domains else .00014))**-3
        if name in domains:
            score *= domains[name]
        if name.endswith((" leg"," knee"," ankle"," toe")):
            sign = 1 if "Left" in name else -1
            score[(points[:,1]*sign<0)&(points[:,2]<crotch)] = 0
        columns.append(score)
    weights = np.stack(columns,axis=1)
    weights /= weights.sum(1)[:,None]
    i,j = np.r_[edges,edges[:,::-1]].T
    for _ in range(3):
        sums = np.zeros_like(weights)
        np.add.at(sums,i,weights[j])
        weights = .60*weights+.40*sums/np.maximum(1,np.bincount(i,minlength=len(points)))[:,None]
    for k,name in enumerate(bones):
        if name in domains:
            weights[:,k] *= domains[name]
    return weights


def blend_to_group(body, index, name, amount):
    """Keep at most four normalized influences after a local weight correction."""
    groups = body.vertex_groups
    row = {item.group:item.weight*(1-amount) for item in body.data.vertices[index].groups}
    target = groups[name].index
    row[target] = row.get(target,0.)+amount
    selected = sorted(row,key=row.get,reverse=True)[:4]
    total = sum(row[j] for j in selected)
    for j in row:
        groups[j].remove([index])
    for j in selected:
        if row[j]>0:
            groups[j].add([index],float(row[j]/total),"REPLACE")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body",default="body")
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--thigh-overlap", type=float, metavar="Z",
                        help="Top of verified thigh/shorts overlap, in body-height units above the soles")
    parser.add_argument("--pelvic-support", action="store_true",
                        help="Stabilize a fitted shorts/crotch bridge pulled by opposing thighs")
    parser.add_argument("--forward-degrees",type=float,default=0,
                        help="World heading in degrees about +Z, measured from +X")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    dest = args.output.resolve()
    if dest.exists() or dest.with_suffix(".landmarks.json").exists():
        raise ValueError("Select a new output filename")
    body = bpy.context.scene.objects[args.body]
    if body.type != "MESH":
        raise ValueError("Select a rest body mesh")
    world = body.matrix_world.copy()
    p = np.array([world @ v.co for v in body.data.vertices])
    angle = np.radians(args.forward_degrees)
    axes = np.array([[np.cos(angle),np.sin(angle),0],[-np.sin(angle),np.cos(angle),0],[0,0,1]])
    local = np.einsum("ij,kj->ik", p, axes)
    origin = (local.min(0)+local.max(0))/2
    origin[2] = local[:,2].min()
    height = np.ptp(local[:,2])
    if height <= 0:
        raise ValueError("Body has zero height")
    scaled = (local-origin)/height
    body.data.calc_loop_triangles()
    faces = np.array([f.vertices[:] for f in body.data.loop_triangles])
    edges = np.array([e.vertices[:] for e in body.data.edges])
    bones,tips,crotch = predict(scaled,faces)
    schema = json.loads((HERE.parents[1]/"assets/HumanArmature.json").read_text())["bones"]
    if set(bones) != {b["name"] for b in schema}:
        raise ValueError("Landmarks do not cover all bones")
    for name,(head,tail) in bones.items():
        if not np.isfinite([head,tail]).all() or np.linalg.norm(tail-head) < .0005:
            raise ValueError("Degenerate landmark segment: "+name)
    if len(set(tips.values())) != len(tips):
        raise ValueError("Finger predictions share a tip; inspect both hands before binding")
    weights = initial_weights(scaled,edges,bones,tips,crotch)
    body.parent = None
    body.matrix_world = world
    for obj in list(bpy.data.objects):
        if obj != body:
            bpy.data.objects.remove(obj,do_unlink=True)
    for mod in list(body.modifiers):
        if mod.type in {"ARMATURE","MASK"}:
            body.modifiers.remove(mod)
    body.vertex_groups.clear()
    rig = bpy.data.objects.new("HumanArmature",bpy.data.armatures.new("Body landmarks"))
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for spec in schema:
        name = spec["name"]
        a,b = bones[name]
        bone = rig.data.edit_bones.new(name)
        bone.head = (a*height+origin)@axes
        bone.tail = (b*height+origin)@axes
        if spec["parent"]:
            bone.parent = rig.data.edit_bones[spec["parent"]]
        if name.endswith(("_L","_R")):
            side = name[-1]
            index = bones[f"DEF-IndexFinger1_{side}"][0]
            little = bones[f"DEF-LittleFinger1_{side}"][0]
            along = bones[f"DEF-MiddleFinger3_{side}"][1]-bones[f"DEF-MiddleFinger1_{side}"][0]
            normal = normalize(np.cross(along,index-little))
            if normal[1]*(1 if side=="L" else -1)>0:
                normal = -normal
            curl = normal if "Thumb" not in name else normalize(normal-.8*normalize(index-little))
            bone.align_roll(Vector(np.cross(b-a,curl)@axes))
    bpy.ops.object.mode_set(mode="OBJECT")
    groups = [body.vertex_groups.new(name=n) for n in bones]
    for i,row in enumerate(weights):
        keep = row.argsort()[-4:]
        for k in keep:
            if row[k]>0:
                groups[k].add([i],float(row[k]/row[keep].sum()),"REPLACE")
    body.parent = rig
    mod = body.modifiers.new("Body skin","ARMATURE")
    mod.object = rig
    mod.use_deform_preserve_volume = True
    refine_body(body,rig,repair_lower=True,isolate_fingertips=True)
    if args.pelvic_support:
        # Blend the medial bridge back to the pelvis. Keep the outer hips and
        # each separate thigh mobile. All distances use this body’s landmarks.
        width = abs(bones["DEF-Left leg"][0][1]-bones["DEF-Right leg"][0][1])
        z = scaled[:,2]-crotch
        support = (smooth((z+.65*width)/(.52*width))
                   *smooth((.95*width-abs(scaled[:,1]))/(.48*width))
                   *smooth((.85*width-z)/(.54*width)))
        for i in np.flatnonzero(support > 0):
            blend_to_group(body, int(i), "DEF-Hips", support[i])
    if args.thigh_overlap is not None:
        top = args.thigh_overlap
        if not 0 < top < crotch:
            raise ValueError("Thigh overlap must end below the crotch bridge")
        width = abs(bones["DEF-Left leg"][0][1]-bones["DEF-Right leg"][0][1])
        # Drive the two overlapping surfaces together through the opening;
        # smoothly return to the fitted weights outside the short cuff band.
        for i,(x,y,z) in enumerate(scaled):
            if abs(y) > 1.18*width or not top-.65*width < z < top+.55*width:
                continue
            blend = smooth((z-top+.65*width)/(.30*width))*smooth((top+.55*width-z)/(.46*width))
            side = "Left" if y>0 else "Right"
            blend_to_group(body, i, f"DEF-{side} leg", blend)
    rig.show_in_front = True
    dest.parent.mkdir(parents=True,exist_ok=True)
    report = {"source":bpy.data.filepath,"body":body.name,"height":height,"tips":tips,
              "world_bones":{n:((np.asarray(pair)*height+origin)@axes).tolist() for n,pair in bones.items()}}
    bpy.ops.wm.save_as_mainfile(filepath=str(dest),compress=True)
    dest.with_suffix(".landmarks.json").write_text(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
