import os
import ntpath

class Obj:
    def __init__(self):
        pass

def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def get_files(ext):
    return [file for file in os.listdir(".") if file.endswith(ext)]

def read_lines(path):
    with open(path) as file:
        return [line.rstrip() for line in file]

def skip_comments(lines):
    return [line for line in lines if not line.startswith("#")]

def group_mtls(path, out_materials):
    lines = skip_comments(read_lines(path))

    # find material instances
    newmtl_indices = [i for i, x in enumerate(lines) if x.startswith("newmtl")]
    newmtl_indices.append(len(lines))

    for start, end in zip(newmtl_indices, newmtl_indices[1:]):
        out_materials[lines[start].split(" ")[1]] = "\n".join(lines[start:end])

def group_obj_per_mtl(path, out_objs):
    lines = skip_comments(read_lines(path))

    # find material references
    mat_refs = [line.split()[1] for line in lines if line.startswith("usemtl")]

    for mat in mat_refs:
        if mat not in out_objs:
            out_objs[mat] = set()
        out_objs[mat].add(path)

def copyComponent(srcList, dstDict, idx):
    # Does the component exist?
    if not idx.isdigit():
        return

    srcIdx = int(idx) - 1   # obj indices start from 1

def copyComponent(srcIdx, srcList, dstList, dstLookup):
    # Check if this component has been copied already
    if srcIdx in dstLookup:
        return dstLookup[srcIdx]

    # Copy as a new value and cache index
    dstIdx = len(dstList)

    dstList.append(srcList[srcIdx])
    dstLookup[srcIdx] = dstIdx

    return dstIdx

def getComponentIndices(vertex):
    comps = vertex.split("/")
    count = len(comps)

    vIdx = None
    vtIdx = None
    vnIdx = None

    def toIdx(list, idx):
        if idx < 0 or idx >= len(list):
            return None
        value = list[idx]
        return int(value) - 1 if value.isdigit() else None

    vIdx = toIdx(comps, 0)
    vtIdx = toIdx(comps, 1)
    vnIdx = toIdx(comps, 2)

    return vIdx, vtIdx, vnIdx


def merge_objs(mat_name, objs):

    print("Merging material " + mat_name)
    print("Objs to be merged " + str(objs))

    newPositions = []
    newNormals = []
    newUvs = []
    newFaces = []

    for obj in objs:
        lines = skip_comments(read_lines(obj))

        # Parse vertex data
        readComponents = lambda src, prefix : [line for line in src if line.startswith(prefix)]

        positions = readComponents(lines, "v")
        normals = readComponents(lines, "vn")
        uvs = readComponents(lines, "vt")

        # find material instances
        usemtl_indices = [i for i, x in enumerate(lines) if x.startswith("usemtl")]
        usemtl_indices.append(len(lines))

        positionLookup = {}
        normalLookup = {}
        uvLookup = {}

        def formatFace(v, vt, vn):
            res = "%s" % (v + 1)
            if vt is not None:
                res += "/%s" % (vt + 1)
            elif vn is not None:
                res += "/"
            if vn is not None:
                res += "/%s" % (vn + 1)
            return res

        # extract faces for each material
        for start, end in zip(usemtl_indices, usemtl_indices[1:]):
            faces = readComponents(lines[start:end], "f")
            for face in faces:
                vertexIndices = face.split(" ")[1:]

                # copy v, vt and vn
                newVertexIndices = []

                for faceVertex in vertexIndices:
                    vIdx, vtIdx, vnIdx = getComponentIndices(faceVertex)

                    outFace = [None, None, None]

                    if vIdx is not None:
                        outFace[0] = copyComponent(vIdx, positions, newPositions, positionLookup)
                    if vtIdx is not None:
                        outFace[1] = copyComponent(vtIdx, uvs, newUvs, uvLookup)
                    if vnIdx is not None:
                        outFace[2] = copyComponent(vnIdx, normals, newNormals, normalLookup)

                    newVertexIndices.append(formatFace(outFace[0], outFace[1], outFace[2]))

                newFaces.append("f %s" % " ".join(newVertexIndices))

    return newPositions, newNormals, newUvs, newFaces

def save_material(filePath, matName, contents):
    with open(filePath, "w") as file:
        file.writelines(contents)

def save_obj(filePath, matName, positions, uvs, normals, faces):
    with open(filePath, "w") as file:
        file.write("mtllib %s.mat\n" % matName)
        file.write("# vertices\n")
        file.write("\n".join(positions))
        if len(uvs) > 0:
            file.write("\n# uvs\n")
            file.write("\n".join(uvs))
        if len(normals) > 0:
            file.write("\n# normals\n")
            file.write("\n".join(normals))
        file.write("\nusemtl %s" % matName)
        file.write("\n# faces\n")
        file.write("\n".join(faces))

def main():
    unique_materials = {}
    objs_per_material = {}

    # group materials by their id
    for mtl in get_files(".mtl"):
        group_mtls(mtl, unique_materials)

    # group obj files by materials
    for obj in get_files(".obj"):
        group_obj_per_mtl(obj, objs_per_material)

    # merge objs sharing same material
    for mat in objs_per_material.keys():
        matFilePath = "out/%s.mat" % mat
        objFilePath = "out/%s.obj" % mat
        pos, norm, uvs, face = merge_objs(mat, list(objs_per_material[mat]))
        save_material(matFilePath, mat, unique_materials[mat])
        save_obj(objFilePath, mat, pos, uvs, norm, face)

    print("DONE!")
main()