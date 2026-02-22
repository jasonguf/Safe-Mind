# NeuroView

A web-based 3D brain MRI viewer that converts NIfTI brain scans into interactive 3D models with adjustable depth visualization.

![NeuroView Screenshot](https://img.shields.io/badge/Status-Active-brightgreen)

## Features

- **3D Brain Visualization** - Upload brain MRI scans and view them as interactive 3D models
- **Depth Control** - Adjust threshold to explore from outer cortex to deep internal structures
- **Transparency** - Control opacity to see through layers
- **MRI Slices** - View Axial, Sagittal, and Coronal slices with interactive sliders
- **Slice Plane Overlay** - Toggle slice images directly on the 3D model
- **Wireframe Mode** - Toggle mesh wireframe visualization with adjustable detail
- **Auto-Rotate** - Smooth automatic rotation for presentation
- **Color Themes** - Multiple professional color schemes
- **Desktop App** - Available as standalone application for Mac and Windows

## Requirements

### Backend
- Python 3.8+
- FastAPI
- nibabel
- numpy
- scipy
- scikit-image
- Pillow
- uvicorn

### Frontend
- Modern web browser with WebGL support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/neuroview.git
cd neuroview
```

2. Install Python dependencies:
```bash
pip install fastapi uvicorn nibabel numpy scipy scikit-image pillow
```

3. Start the backend server:
```bash
cd backend
python server.py
```

4. Open `brain_viewer.html` in your browser

## Usage

1. Start the server (runs on `http://localhost:8000`)
2. Open `brain_viewer.html` in your browser
3. Upload a NIfTI brain scan (`.nii` or `.nii.gz`)
4. Use the controls to explore:
   - **Depth (Threshold)**: Lower = outer surface, Higher = internal structures
   - **Opacity**: Make the brain transparent
   - **Wireframe**: See the mesh structure
   - **Slice sliders**: Navigate through MRI slices

## Supported File Formats

- NIfTI (`.nii`)
- Compressed NIfTI (`.nii.gz`)

## Getting Sample Brain Data

You can download skull-stripped brain MRI data using nilearn:

```python
from nilearn import datasets
import nibabel as nib

mni = datasets.fetch_icbm152_2009()
t1_img = nib.load(mni['t1'])
mask_img = nib.load(mni['mask'])

# Apply mask for brain-only data
brain_only = t1_img.get_fdata() * mask_img.get_fdata()
brain_img = nib.Nifti1Image(brain_only, t1_img.affine)
nib.save(brain_img, 'brain_only.nii.gz')
```

## Desktop Application

NeuroView can be built as a standalone desktop application for Mac and Windows.

### Build for macOS

```bash
./build_mac.sh
```

This creates `dist/NeuroView.app` - a native macOS application.

### Build for Windows

```batch
build_windows.bat
```

This creates `dist/NeuroView/NeuroView.exe` - a Windows executable.

### Build Requirements

- Python 3.8+
- pywebview
- pyinstaller

All build dependencies are included in `requirements.txt`.

## Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript, Three.js
- **Backend**: Python, FastAPI, scikit-image (marching cubes)
- **3D Rendering**: WebGL via Three.js
- **Desktop**: pywebview, PyInstaller

## License

MIT License
