"""
Pre-process demo files to JSON for instant loading.
Run this once to generate the processed demo files.
"""

import os
import io
import json
import base64
import numpy as np
import nibabel as nib
from scipy import ndimage
from PIL import Image
from skimage import measure
from collections import defaultdict

DEMOS_DIR = os.path.join(os.path.dirname(__file__), "demos")
OUTPUT_DIR = os.path.join(DEMOS_DIR, "processed")

def process_demo(filepath):
    """Process a NIfTI file and return the full data structure."""
    print(f"Processing: {filepath}")

    img = nib.load(filepath)
    data = img.get_fdata()

    if len(data.shape) == 4:
        data = data[:, :, :, 0]

    voxel_dims = [float(v) for v in img.header.get_zooms()[:3]]
    print(f"  Shape: {data.shape}, Voxels: {voxel_dims}")

    # Normalize
    data_min, data_max = data.min(), data.max()
    if data_max > data_min:
        norm_data = (data - data_min) / (data_max - data_min)
    else:
        norm_data = np.zeros_like(data)

    # Downscale for volume/mesh
    max_dim = 140
    scale = min(1.0, max_dim / max(data.shape))
    if scale < 1.0:
        small_data = ndimage.zoom(norm_data, scale, order=1)
        small_voxels = [v / scale for v in voxel_dims]
    else:
        small_data = norm_data
        small_voxels = list(voxel_dims)

    # Generate slices
    print("  Generating slices...")
    slices = {}
    for axis, name in [(2, 'axial'), (0, 'sagittal'), (1, 'coronal')]:
        slice_images = []
        num_slices = data.shape[axis]
        indices = np.linspace(0, num_slices - 1, min(50, num_slices), dtype=int)

        for idx in indices:
            if axis == 2:
                slice_data = norm_data[:, :, idx].T
            elif axis == 0:
                slice_data = norm_data[idx, :, :].T
            else:
                slice_data = norm_data[:, idx, :].T

            slice_data = np.flipud(slice_data)
            slice_uint8 = (slice_data * 255).astype(np.uint8)

            img_pil = Image.fromarray(slice_uint8, mode='L')
            buffer = io.BytesIO()
            img_pil.save(buffer, format='PNG', optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            slice_images.append({
                'index': int(idx),
                'total': int(num_slices),
                'data': b64
            })
        slices[name] = slice_images

    # Volume data for mesh
    volume_b64 = base64.b64encode(
        (small_data * 255).astype(np.uint8).tobytes()
    ).decode('utf-8')

    # Pre-extract meshes at multiple thresholds for instant slider switching
    print("  Extracting meshes at multiple thresholds...")
    smooth_data = ndimage.gaussian_filter(small_data, sigma=0.5)
    thresholds = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    meshes = {}

    for threshold in thresholds:
        try:
            verts, faces, normals, values = measure.marching_cubes(
                smooth_data,
                level=threshold,
                spacing=small_voxels,
                step_size=2
            )

            # Simple smoothing
            adjacency = defaultdict(set)
            for face in faces:
                for i in range(3):
                    v1, v2 = face[i], face[(i + 1) % 3]
                    adjacency[v1].add(v2)
                    adjacency[v2].add(v1)

            for _ in range(2):
                new_verts = verts.copy()
                for i in range(len(verts)):
                    neighbors = list(adjacency[i])
                    if neighbors:
                        avg = verts[neighbors].mean(axis=0)
                        new_verts[i] = verts[i] + 0.3 * (avg - verts[i])
                verts = new_verts

            # Center the mesh and store the offset for slice alignment
            center = verts.mean(axis=0)
            verts = verts - center

            meshes[str(threshold)] = {
                "vertices": verts.tolist(),
                "faces": faces.tolist(),
                "vertexCount": int(len(verts)),
                "faceCount": int(len(faces)),
                "centerOffset": center.tolist()  # Store for slice alignment
            }
            print(f"    Threshold {threshold}: {len(verts)} vertices, {len(faces)} faces")
        except Exception as e:
            print(f"    Threshold {threshold} failed: {e}")

    # Default mesh at 0.3 for backwards compatibility
    mesh = meshes.get("0.3", None)

    # Compute physical volume size for slice alignment
    # This is the size of the downscaled volume used for mesh extraction
    volumePhysicalSize = [
        float(small_data.shape[0] * small_voxels[0]),
        float(small_data.shape[1] * small_voxels[1]),
        float(small_data.shape[2] * small_voxels[2])
    ]

    result = {
        "volume": {
            "data": volume_b64,
            "shape": [int(s) for s in small_data.shape],
            "voxelSize": [float(v) for v in small_voxels]
        },
        "slices": slices,
        "dimensions": [int(d) for d in data.shape],
        "voxelSize": voxel_dims,
        "volumePhysicalSize": volumePhysicalSize,  # Physical size for slice alignment
        "filename": os.path.basename(filepath),
        "mesh": mesh,
        "meshes": meshes  # All pre-computed meshes at different thresholds
    }

    print("  Done!")
    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    demo_files = [f for f in os.listdir(DEMOS_DIR) if f.endswith(('.nii', '.nii.gz'))]

    for demo_file in demo_files:
        filepath = os.path.join(DEMOS_DIR, demo_file)
        output_name = demo_file.replace('.nii.gz', '.json').replace('.nii', '.json')
        output_path = os.path.join(OUTPUT_DIR, output_name)

        result = process_demo(filepath)

        with open(output_path, 'w') as f:
            json.dump(result, f)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved: {output_path} ({size_mb:.1f} MB)\n")

    print("All demos processed!")


if __name__ == "__main__":
    main()
