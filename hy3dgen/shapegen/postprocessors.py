# Open Source Model Licensed under the Apache License Version 2.0
# and Other Licenses of the Third-Party Components therein:
# The below Model in this distribution may have been modified by THL A29 Limited
# ("Tencent Modifications"). All Tencent Modifications are Copyright (C) 2024 THL A29 Limited.

# Copyright (C) 2024 THL A29 Limited, a Tencent company.  All rights reserved.
# The below software and/or models in this distribution may have been
# modified by THL A29 Limited ("Tencent Modifications").
# All Tencent Modifications are Copyright (C) THL A29 Limited.

# Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
# except for the third-party components listed below.
# Hunyuan 3D does not impose any additional limitations beyond what is outlined
# in the repsective licenses of these third-party components.
# Users must comply with all terms and conditions of original licenses of these third-party
# components and must ensure that the usage of the third party components adheres to
# all relevant laws and regulations.

# For avoidance of doubts, Hunyuan 3D means the large language models and
# their software and algorithms, including trained model weights, parameters (including
# optimizer states), machine-learning model code, inference-enabling code, training-enabling code,
# fine-tuning enabling code and other elements of the foregoing made publicly available
# by Tencent in accordance with TENCENT HUNYUAN COMMUNITY LICENSE AGREEMENT.

import tempfile
import os
from typing import Union


from .models.vae import Latent2MeshOutput

import folder_paths


def load_mesh(path):
    import trimesh
    import pymeshlab
    if path.endswith(".glb"):
        mesh = trimesh.load(path)
    else:
        mesh = pymeshlab.MeshSet()
        mesh.load_new_mesh(path)
    return mesh


def reduce_face(mesh, max_facenum: int = 200000):
    mesh.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=max_facenum,
        qualitythr=1.0,
        preserveboundary=True,
        boundaryweight=3,
        preservenormal=True,
        preservetopology=True,
        autoclean=True
    )
    return mesh


def remove_floater(mesh):
    mesh.apply_filter("compute_selection_by_small_disconnected_components_per_face",
                      nbfaceratio=0.005)
    mesh.apply_filter("compute_selection_transfer_face_to_vertex", inclusive=False)
    mesh.apply_filter("meshing_remove_selected_vertices_and_faces")
    return mesh


def pymeshlab2trimesh(mesh):
    import trimesh
    # Create temp directory with explicit permissions
    temp_dir = folder_paths.temp_directory
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        temp_path = os.path.join(temp_dir, 'temp_mesh.ply')
        
        # Save and load mesh
        mesh.save_current_mesh(temp_path)
        loaded_mesh = trimesh.load(temp_path)
        
        # Check loaded object type
        if isinstance(loaded_mesh, trimesh.Scene):
            combined_mesh = trimesh.Trimesh()
            # If Scene, iterate through all geometries and combine
            for geom in loaded_mesh.geometry.values():
                combined_mesh = trimesh.util.concatenate([combined_mesh, geom])
            loaded_mesh = combined_mesh
            
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return loaded_mesh
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Error in pymeshlab2trimesh: {str(e)}")


def trimesh2pymeshlab(mesh):
    import trimesh
    import pymeshlab
    # Create temp directory with explicit permissions
    temp_dir = folder_paths.temp_directory
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        temp_path = os.path.join(temp_dir, 'temp_mesh.ply')
        
        # Handle scene with multiple geometries
        if isinstance(mesh, trimesh.scene.Scene):
            temp_mesh = None
            for idx, obj in enumerate(mesh.geometry.values()):
                if idx == 0:
                    temp_mesh = obj
                else:
                    temp_mesh = temp_mesh + obj
            mesh = temp_mesh
            
        # Export and load mesh
        mesh.export(temp_path)
        mesh_set = pymeshlab.MeshSet()
        mesh_set.load_new_mesh(temp_path)
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return mesh_set
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Error in trimesh2pymeshlab: {str(e)}")


def export_mesh(input, output):
    import pymeshlab
    if isinstance(input, pymeshlab.MeshSet):
        mesh = output
    elif isinstance(input, Latent2MeshOutput):
        output = Latent2MeshOutput()
        output.mesh_v = output.current_mesh().vertex_matrix()
        output.mesh_f = output.current_mesh().face_matrix()
        mesh = output
    else:
        mesh = pymeshlab2trimesh(output)
    return mesh


def import_mesh(mesh: Union[Latent2MeshOutput, str]):
    import trimesh
    import pymeshlab
    if isinstance(mesh, str):
        mesh = load_mesh(mesh)
    elif isinstance(mesh, Latent2MeshOutput):
        mesh = pymeshlab.MeshSet()
        mesh_pymeshlab = pymeshlab.Mesh(vertex_matrix=mesh.mesh_v, face_matrix=mesh.mesh_f)
        mesh.add_mesh(mesh_pymeshlab, "converted_mesh")

    if isinstance(mesh, (trimesh.Trimesh, trimesh.scene.Scene)):
        mesh = trimesh2pymeshlab(mesh)

    return mesh


class FaceReducer:
    def __call__(
        self,
        mesh: Union[Latent2MeshOutput, str],
        max_facenum: int = 40000
    ):
        ms = import_mesh(mesh)
        ms = reduce_face(ms, max_facenum=max_facenum)
        mesh = export_mesh(mesh, ms)
        return mesh


class FloaterRemover:
    def __call__(
        self,
        mesh: Union[Latent2MeshOutput, str],
    ) -> Union[Latent2MeshOutput]:
        ms = import_mesh(mesh)
        ms = remove_floater(ms)
        mesh = export_mesh(mesh, ms)
        return mesh


class DegenerateFaceRemover:
    def __call__(
        self,
        mesh: Union[Latent2MeshOutput, str],
    ) -> Union[Latent2MeshOutput]:
        import pymeshlab
        ms = import_mesh(mesh)

        # Create temp file with explicit closing
        temp_file = tempfile.NamedTemporaryFile(suffix='.ply', delete=False)
        temp_file_path = temp_file.name
        temp_file.close()

        try:
            ms.save_current_mesh(temp_file_path)
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(temp_file_path)
        finally:
            # Ensure temp file is removed
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass

        mesh = export_mesh(mesh, ms)
        return mesh
