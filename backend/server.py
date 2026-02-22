"""
NeuroView - Simple Brain MRI Viewer
Upload a NIfTI brain scan, get a 3D mesh + slices
With real-time collaboration support via WebSockets
"""

import os
import io
import base64
import tempfile
import secrets
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="NeuroView")

# GZip compression for responses > 500 bytes - reduces mesh JSON by ~80%
app.add_middleware(GZipMiddleware, minimum_size=500)

# Get the directory - works for both local and Render deployment
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Try to find brain_viewer.html
POSSIBLE_PATHS = [
    os.path.join(PROJECT_DIR, "brain_viewer.html"),
    os.path.join(os.getcwd(), "brain_viewer.html"),
    "/Users/kentucky/Desktop/neuroview/brain_viewer.html",  # Local fallback
]

HTML_FILE = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        HTML_FILE = path
        break

print(f"HTML file found at: {HTML_FILE}")
print(f"Project dir: {PROJECT_DIR}")
print(f"Current working dir: {os.getcwd()}")

# ============== Collaboration System ==============
# All users are editors - no view-only mode. Max 4 people per session.

MAX_EDITORS = 4


@dataclass
class Session:
    """A collaborative editing session."""
    session_id: str
    editors: List[WebSocket] = field(default_factory=list)
    state: Dict = field(default_factory=dict)


# In-memory session storage
sessions: Dict[str, Session] = {}


class SessionCreateResponse(BaseModel):
    session_id: str


@app.post("/session/create", response_model=SessionCreateResponse)
async def create_session():
    """Create a new collaborative session and return session ID."""
    session_id = secrets.token_urlsafe(8)  # e.g., "aB3dE5fG"
    sessions[session_id] = Session(session_id=session_id)
    print(f"Session created: {session_id}")
    return {"session_id": session_id}


@app.get("/session/{session_id}/exists")
async def session_exists(session_id: str):
    """Check if a session exists and has room."""
    if session_id not in sessions:
        return {"exists": False, "editorCount": 0, "canJoin": False}
    session = sessions[session_id]
    count = len(session.editors)
    return {"exists": True, "editorCount": count, "canJoin": count < MAX_EDITORS}


@app.post("/session/{session_id}/state")
async def save_session_state(session_id: str, request: dict):
    """Save session state."""
    if session_id not in sessions:
        # Create session if it doesn't exist
        sessions[session_id] = Session(session_id=session_id)
    sessions[session_id].state = request
    print(f"Session {session_id} state saved (keys: {list(request.keys())})")
    return {"status": "ok"}


@app.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Get session state."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].state


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time collaboration. All users are editors."""
    await websocket.accept()

    # Wait for init message
    try:
        init_data = await websocket.receive_json()
    except:
        await websocket.close()
        return

    # Create session if doesn't exist
    if session_id not in sessions:
        sessions[session_id] = Session(session_id=session_id)

    session = sessions[session_id]

    # Check if session is full
    if len(session.editors) >= MAX_EDITORS:
        await websocket.send_json({"type": "error", "message": "Session full (max 4 editors)"})
        await websocket.close()
        return

    # Add this user as an editor
    session.editors.append(websocket)
    editor_count = len(session.editors)
    print(f"Editor joined session {session_id} (total: {editor_count})")

    # Notify user they're connected
    await websocket.send_json({
        "type": "connected",
        "role": "editor",
        "editorCount": editor_count
    })

    # Notify all other editors
    for editor in session.editors:
        if editor != websocket:
            try:
                await editor.send_json({
                    "type": "editor_joined",
                    "editorCount": editor_count
                })
            except:
                pass

    # Main message loop - all editors can send updates
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "state_update":
                # Update stored state
                update_data = data.get("data", {})
                session.state.update(update_data)

                # Broadcast to all OTHER editors
                disconnected = []
                for editor in session.editors:
                    if editor != websocket:  # Don't send back to sender
                        try:
                            await editor.send_json(data)
                        except:
                            disconnected.append(editor)

                # Clean up disconnected editors
                for e in disconnected:
                    if e in session.editors:
                        session.editors.remove(e)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup on disconnect
        if websocket in session.editors:
            session.editors.remove(websocket)
        editor_count = len(session.editors)
        print(f"Editor left session {session_id} (remaining: {editor_count})")

        # Notify remaining editors
        for editor in session.editors:
            try:
                await editor.send_json({
                    "type": "editor_left",
                    "editorCount": editor_count
                })
            except:
                pass

        # Clean up empty session after delay
        if editor_count == 0:
            await asyncio.sleep(60)
            if session_id in sessions and len(sessions[session_id].editors) == 0:
                del sessions[session_id]
                print(f"Session {session_id} cleaned up")


# ============== Original MRI Processing ==============

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for keep-alive pings."""
    return {"status": "ok"}


@app.get("/")
async def root(session: str = None):
    """Serve landing page, or app if session parameter is present."""
    # If session parameter exists, go directly to app
    if session:
        if HTML_FILE and os.path.exists(HTML_FILE):
            return FileResponse(HTML_FILE, media_type="text/html")
    # Otherwise show landing page
    home_file = os.path.join(PROJECT_DIR, "home.html")
    if os.path.exists(home_file):
        return FileResponse(home_file, media_type="text/html")
    # Fallback to brain viewer if no home page
    if HTML_FILE and os.path.exists(HTML_FILE):
        return FileResponse(HTML_FILE, media_type="text/html")
    return {"status": "error", "message": "HTML file not found"}


@app.get("/app")
async def app_viewer():
    """Serve the brain viewer application."""
    if HTML_FILE and os.path.exists(HTML_FILE):
        return FileResponse(HTML_FILE, media_type="text/html")
    return {"status": "error", "message": "App not found"}


@app.get("/instructions")
async def instructions_page():
    """Serve the instructions page."""
    instructions_file = os.path.join(PROJECT_DIR, "instructions.html")
    if os.path.exists(instructions_file):
        return FileResponse(instructions_file, media_type="text/html")
    return {"status": "error", "message": "Instructions page not found"}


@app.get("/api/status")
async def api_status():
    return {"status": "ok", "message": "NeuroView API"}


@app.get("/api/demos")
async def list_demos():
    """List available demo files."""
    demos_dir = os.path.join(PROJECT_DIR, "demos")
    demos = []
    if os.path.exists(demos_dir):
        for f in os.listdir(demos_dir):
            if f.endswith(('.nii', '.nii.gz')):
                demos.append({"name": f, "url": f"/demos/{f}"})
    return {"demos": demos}


@app.get("/demos/processed/{filename}")
async def get_processed_demo(filename: str):
    """Serve a pre-processed demo JSON file for instant loading."""
    processed_dir = os.path.join(PROJECT_DIR, "demos", "processed")
    # Convert .nii.gz or .nii to .json
    json_name = filename.replace('.nii.gz', '.json').replace('.nii', '.json')
    file_path = os.path.join(processed_dir, json_name)
    print(
        f"Processed demo request: {filename} -> {json_name}, path: {file_path}, exists: {os.path.exists(file_path)}")
    if os.path.exists(file_path):
        # Cache demos for 1 day (they rarely change)
        return FileResponse(file_path, media_type="application/json", headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(status_code=404, detail="Processed demo not found")


@app.get("/demos/{filename}")
async def get_demo_file(filename: str):
    """Serve a demo file."""
    demos_dir = os.path.join(PROJECT_DIR, "demos")
    file_path = os.path.join(demos_dir, filename)
    if os.path.exists(file_path) and filename.endswith(('.nii', '.nii.gz')):
        return FileResponse(file_path, media_type="application/octet-stream", filename=filename)
    raise HTTPException(status_code=404, detail="Demo file not found")


@app.get("/images/{filename}")
async def get_image(filename: str):
    """Serve team photos and other images."""
    images_dir = os.path.join(PROJECT_DIR, "images")
    file_path = os.path.join(images_dir, filename)
    if os.path.exists(file_path):
        # Determine media type
        ext = filename.lower().split('.')[-1]
        media_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                       'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        media_type = media_types.get(ext, 'application/octet-stream')
        # Cache images for 1 week
        return FileResponse(file_path, media_type=media_type, headers={"Cache-Control": "public, max-age=604800"})
    raise HTTPException(status_code=404, detail="Image not found")


@app.post("/process")
async def process_mri(file: UploadFile = File(...)):
    """Process MRI file and return volume data + slices for client-side rendering."""
    import nibabel as nib
    from scipy import ndimage
    from PIL import Image

    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in ['.nii', '.nii.gz', '.gz']):
        raise HTTPException(
            status_code=400, detail="Please upload a NIfTI file (.nii or .nii.gz)")

    suffix = '.nii.gz' if '.gz' in filename else '.nii'

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        print(f"Processing: {file.filename}")

        img = nib.load(tmp_path)
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

        # Store volume for mesh extraction (moderate resolution)
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
            indices = np.linspace(
                0, num_slices - 1, min(50, num_slices), dtype=int)

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
                img_pil.save(buffer, format='PNG')
                b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                slice_images.append({
                    'index': int(idx),
                    'total': int(num_slices),
                    'data': b64
                })
            slices[name] = slice_images

        # Store volume data for mesh extraction
        volume_b64 = base64.b64encode(
            (small_data * 255).astype(np.uint8).tobytes()
        ).decode('utf-8')

        print("  Done!")

        return JSONResponse(content={
            "volume": {
                "data": volume_b64,
                "shape": [int(s) for s in small_data.shape],
                "voxelSize": [float(v) for v in small_voxels]
            },
            "slices": slices,
            "dimensions": [int(d) for d in data.shape],
            "voxelSize": voxel_dims,
            "filename": file.filename
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/extract-mesh")
async def extract_mesh(request: dict):
    """Extract mesh at a specific threshold from volume data."""
    from scipy import ndimage
    from skimage import measure

    try:
        volume_b64 = request.get('volume')
        shape = request.get('shape')
        voxel_size = request.get('voxelSize')
        threshold = request.get('threshold', 0.3)
        # 60-180, higher = more detail
        mesh_detail = request.get('resolution', 120)
        solid_mode = request.get('solid', False)  # Fill internal cavities

        print(
            f"Extract mesh - threshold: {threshold}, mesh_detail: {mesh_detail}, solid: {solid_mode}")

        # Decode volume
        volume_bytes = base64.b64decode(volume_b64)
        data = np.frombuffer(volume_bytes, dtype=np.uint8).reshape(shape)
        norm_data = data.astype(float) / 255.0

        # Calculate step_size from mesh_detail (inverse relationship)
        # mesh_detail 60 -> step_size 4 (very coarse)
        # mesh_detail 120 -> step_size 2 (medium)
        # mesh_detail 180 -> step_size 1 (fine)
        step_size = max(1, round(5 - (mesh_detail / 45)))
        print(f"  Using step_size: {step_size}")

        # Smooth - less smoothing for higher detail
        sigma = 0.8 if step_size >= 3 else (0.5 if step_size == 2 else 0.3)
        smooth_data = ndimage.gaussian_filter(norm_data, sigma=sigma)

        # For solid mode, fill internal cavities to get only outer surface
        if solid_mode:
            # Create binary mask at threshold
            binary_mask = smooth_data > threshold
            # Fill holes - this fills internal cavities
            filled = ndimage.binary_fill_holes(binary_mask)
            # Apply strong morphological closing to smooth and fill all gaps
            struct = ndimage.generate_binary_structure(3, 2)
            filled = ndimage.binary_closing(
                filled, structure=struct, iterations=5)
            # Dilate slightly then erode to close small holes
            filled = ndimage.binary_dilation(
                filled, structure=struct, iterations=2)
            filled = ndimage.binary_erosion(
                filled, structure=struct, iterations=2)
            # Final fill holes pass
            filled = ndimage.binary_fill_holes(filled)
            # Smooth the result slightly
            filled_smooth = ndimage.gaussian_filter(
                filled.astype(float), sigma=0.5)
            smooth_data = filled_smooth
            # Use a threshold of 0.5 for the smoothed binary data
            threshold = 0.5
            print(f"  Solid mode: filled internal cavities")

        # Extract mesh - step_size controls mesh density
        verts, faces, normals, values = measure.marching_cubes(
            smooth_data,
            level=threshold,
            spacing=voxel_size,
            step_size=step_size
        )
        print(f"  Generated mesh: {len(verts)} vertices, {len(faces)} faces")

        # Simple smoothing
        from collections import defaultdict
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

        # Center
        center = verts.mean(axis=0)
        verts = verts - center

        return JSONResponse(content={
            "vertices": verts.tolist(),
            "faces": faces.tolist(),
            "vertexCount": int(len(verts)),
            "faceCount": int(len(faces))
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"NeuroView Server starting on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
