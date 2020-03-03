import os
import ntpath
import numpy
import uuid
import shutil
import hashlib
from PyTexturePacker import Packer
from PIL import Image

class Obj:
    def __init__(self):
        pass

def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def get_files(ext, folder="."):
    return [os.path.join(folder, file) for file in os.listdir(folder) if file.endswith(ext)]

def read_lines(path):
    with open(path) as file:
        return [line.rstrip() for line in file]

def write_lines(path, lines):
    with open(path, "w") as file:
        file.write("\n".join(lines))

def skip_comments(lines):
    return [line for line in lines if not line.startswith("#")]

def group_mtls(path, out_materials):
    lines = skip_comments(read_lines(path))

    name_to_hash = {}

    # find material instances
    newmtl_indices = [i for i, x in enumerate(lines) if x.startswith("newmtl")]
    newmtl_indices.append(len(lines))

    for start, end in zip(newmtl_indices, newmtl_indices[1:]):
        name = lines[start].split(" ")[1]
        material_payload = "\n".join(lines[start+1:end]).replace("\\", "/")
        
        # Names are not unique across obj files
        material_hash = hashlib.sha1(material_payload.encode('utf-16')).hexdigest()
        out_materials[material_hash] = material_payload
        name_to_hash[name] = material_hash

    return name_to_hash

def group_obj_per_mtl(path, out_objs, out_materials, obj_mat_map):
    lines = skip_comments(read_lines(path))

    # Open mtl file used by this obj and gather material info
    mtllib_name = next(line.split(" ")[1] for line in lines if line.split(" ")[0] == "mtllib")
    obj_dir = os.path.dirname(path)
    mtl_path = os.path.join(obj_dir, mtllib_name)

    name_to_hash = group_mtls(mtl_path, out_materials)

    # find material references and group by hash
    mat_refs = [line.split()[1] for line in lines if line.startswith("usemtl")]

    # Store mapping information from global hash to local material name
    mat_hash_to_name = {}

    for mat in mat_refs:
        name_hash = name_to_hash[mat]
        parsed_material = out_materials[name_hash]
        payload = parsed_material[1]

        mat_hash_to_name[name_hash] = mat

        if name_hash not in out_objs:
            out_objs[name_hash] = set()
        out_objs[name_hash].add(path)

    obj_mat_map[path] = mat_hash_to_name

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


def merge_objs(mat_name, objs, obj_mat_map):

    newPositions = []
    newNormals = []
    newUvs = []
    newFaces = []

    for obj in objs:
        lines = skip_comments(read_lines(obj))

        # Get hash -> mat_name mapping information for this object
        mapping = obj_mat_map[obj]
        export_mat_name = mapping[mat_name]

        # Parse vertex data
        readComponents = lambda src, prefix : [line for line in src if line.startswith(prefix)]

        positions = readComponents(lines, "v")
        normals = readComponents(lines, "vn")
        uvs = readComponents(lines, "vt")

        # find indices of faces per material
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

        # extract faces for the selected material
        for start, end in zip(usemtl_indices, usemtl_indices[1:]):
            # Skip all but the wanted material
            if not lines[start].endswith(export_mat_name):
                continue

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
        file.write("newmtl %s\n" % matName)
        file.writelines(contents)

def save_obj(filePath, matName, positions, uvs, normals, faces):
    with open(filePath, "w") as file:
        file.write("mtllib %s.mtl\n" % matName)
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

def matrix_translate(x, y, z):
    return numpy.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [x, y, z, 1]
    ]).astype(float)

def matrix_rotate(rot):
    return numpy.array([
        [rot[0], rot[1], rot[2], 0],
        [rot[3], rot[4], rot[5], 0],
        [rot[6], rot[7], rot[8], 0],
        [0, 0, 0, 1]
    ]).astype(float)

def matrix_scale(x, y, z):
    return numpy.array([
        [x, 0, 0, 0],
        [0, y, 0, 0],
        [0, 0, z, 0],
        [0, 0, 0, 1]
    ]).astype(float)

def parse_element_meta_file(path):
    lines = read_lines(path)

    # Gather models with their transformation matrices
    models = []

    # Read lines in a chunk of 5
    unpack = lambda line: tuple(line.split(","))

    for i in range(0, len(lines), 5):
        obj_lines = lines[i:i+5]
        x, y, z = unpack(obj_lines[1])
        rot = obj_lines[2].split(",")
        s, sx, sy, sz = unpack(obj_lines[3])
        obj_file, = unpack(obj_lines[4])

        # Construct transformation matrix. NOTE: using row vectors!
        translation = matrix_translate(x, y, z)
        rotation = matrix_rotate(rot)
        scale = matrix_scale(sx, sy, sz)

        matrix = numpy.matmul(numpy.matmul(scale, rotation), translation)
        models.append([obj_file, matrix])

    return models

def parse_object_meta_file(path):
    lines = read_lines(path)

    objects = []

    # Read lines in a group of 6
    unpack = lambda line: tuple(line.split(","))

    for i in range(0, len(lines), 6):
        obj_lines = lines[i:i+6]
        x, y, z = unpack(obj_lines[1])
        rot = obj_lines[2].split(",")
        s, sx, sy, sz = unpack(obj_lines[3])
        element_file, = unpack(obj_lines[4])

        # Construct transformation matrix. NOTE: using row vectors!
        translation = matrix_translate(x, y, z)
        rotation = matrix_rotate(rot)
        scale = matrix_scale(sx, sy, sz)

        matrix = numpy.matmul(numpy.matmul(scale, rotation), translation)
        objects.append([element_file, matrix])

    return objects

def copy_obj_mat(obj_path, dst_folder, obj_dst_name, transform):
    obj_lines = read_lines(obj_path)
    updated_lines = []
    # transform vertices
    for line in obj_lines:
        comps = line.split(" ")
        if comps[0] != "v":
            updated_lines.append(line)
            continue
        x = float(comps[1])
        y = float(comps[2])
        z = float(comps[3])
        vec = numpy.dot(numpy.array([x, y, z, 1]), transform)

        updated_lines.append("v %f %f %f" % (vec[0], vec[1], vec[2]))

    # save transformed obj file
    write_lines("%s/%s.obj" % (dst_folder, obj_dst_name), updated_lines)
    with open("%s/%s.obj" % (dst_folder, obj_dst_name), "w") as file:
        file.write("\n".join(updated_lines))

    # copy material lib and conserve relative paths to textures
    mtllib_name = next(line.split(" ")[1] for line in obj_lines if line.split(" ")[0] == "mtllib")

    obj_dir = os.path.dirname(obj_path)
    mtl_path = os.path.join(obj_dir, mtllib_name)
    mtl_lines = read_lines(mtl_path)
    updated_lines = []

    for line in mtl_lines:
        comps = line.split(" ")
        if not comps[0].startswith("map"):
            updated_lines.append(line)
            continue
        # Get relative path from output folder to source folder
        texture_abs_path = os.path.join(obj_dir, comps[1].replace("\\", "/"))
        texture_rel_path = os.path.relpath(texture_abs_path, dst_folder)

        print("src: %s, dst: %s => rel: %s" % (texture_abs_path, dst_folder, texture_rel_path))

        updated_lines.append("%s %s" % (comps[0], texture_rel_path))

    # save the updated mtl file
    write_lines("%s/%s" % (dst_folder, mtllib_name), updated_lines)

def create_texture_groups():
    pass

def main():
    unique_materials = {}
    objs_per_material = {}

    INTERM_DIR = os.path.abspath("interm")
    OUTPUT_DIR = os.path.abspath("out")

    # Create folder structure
    if not os.path.exists(INTERM_DIR):
        os.mkdir(INTERM_DIR)

    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    # Parse the object meta file
    element_objects = parse_object_meta_file("Building.data")

    for elem_obj in element_objects:
        elem_path = elem_obj[0]
        elem_transform = elem_obj[1]

        # Go through element meta files
        objects = parse_element_meta_file(elem_path)

        for obj in objects:
            # Copy and transform meshes into an interm folder
            path = obj[0].replace("\\", "/")
            transform = obj[1]
            if not os.path.exists(path):
                continue

            # Compute parcel transform matrix
            parcel_matrix = numpy.matmul(transform, elem_transform)
            copy_obj_mat(path, INTERM_DIR, uuid.uuid4().hex, parcel_matrix)

    # Combine small textures into atlases


    # Work with intermediate objs now!

    # group obj files by materials
    unique_materials = { }
    obj_mat_map = { }

    for obj in get_files(".obj", INTERM_DIR):
        group_obj_per_mtl(obj, objs_per_material, unique_materials, obj_mat_map)

    # merge objs sharing same material
    for mat in objs_per_material.keys():
        matFilePath = "%s/%s.mtl" % (OUTPUT_DIR, mat)
        objFilePath = "%s/%s.obj" % (OUTPUT_DIR, mat)

        pos, norm, uvs, face = merge_objs(mat, list(objs_per_material[mat]), obj_mat_map)
        save_material(matFilePath, mat, unique_materials[mat])
        save_obj(objFilePath, mat, pos, uvs, norm, face)

    print("DONE!")

main()