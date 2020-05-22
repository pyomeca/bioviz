"""
Example script for animating a model
"""

from pathlib import Path

import numpy as np

from pyomeca import FrameDependentNpArray, Markers3d, RotoTrans, RotoTransCollection
from BiorbdViz.biorbd_vtk import VtkModel, VtkWindow, Mesh, MeshCollection

# Path to data
DATA_FOLDER = Path("/home/pariterre/Programmation/biorbd-viz") / "tests" / "data"
MARKERS_CSV = DATA_FOLDER / "markers.csv"
MARKERS_ANALOGS_C3D = DATA_FOLDER / "markers_analogs.c3d"

# Load data
# all markers
d = Markers3d.from_c3d(MARKERS_ANALOGS_C3D, idx=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], prefix=":")
# mean of 1st and 4th
d2 = Markers3d.from_c3d(MARKERS_ANALOGS_C3D, idx=[[0, 1, 2], [0, 4, 2]], prefix=":")
# mean of first 3 markers
d3 = Markers3d.from_c3d(MARKERS_ANALOGS_C3D, idx=[[0], [1], [2]], prefix=":")

d4 = Markers3d.from_c3d(MARKERS_ANALOGS_C3D, names=["CLAV_post", "PSISl", "STERr", "CLAV_post"], prefix=":")

# mean of first 3 markers in c3d file
d5 = Markers3d.from_c3d(MARKERS_ANALOGS_C3D, idx=[[0], [1], [2]], prefix=":")

# Create a windows with a nice gray background
vtkWindow = VtkWindow(background_color=(0.5, 0.5, 0.5))

# Add marker holders to the window
vtkModelReal = VtkModel(vtkWindow, markers_color=(1, 0, 0), markers_size=10.0, markers_opacity=1)
vtkModelPred = VtkModel(vtkWindow, markers_color=(0, 0, 0), markers_size=10.0, markers_opacity=0.5)
vtkModelMid = VtkModel(vtkWindow, markers_color=(0, 0, 1), markers_size=10.0, markers_opacity=0.5)
vtkModelByNames = VtkModel(vtkWindow, markers_color=(0, 1, 1), markers_size=10.0, markers_opacity=0.5)
vtkModelFromC3d = VtkModel(vtkWindow, markers_color=(0, 1, 0), markers_size=10.0, markers_opacity=0.5)

# Create some RotoTrans attached to the first model
all_rt_real = RotoTransCollection()
all_rt_real.append(
    RotoTrans(angles=FrameDependentNpArray(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, 0, 0:1])
)
all_rt_real.append(
    RotoTrans(angles=FrameDependentNpArray(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, 0, 0:1])
)

# Create some RotoTrans attached to the second model
one_rt = RotoTrans.define_axes(d, [3, 5], [[4, 3], [4, 5]], "zx", "z", [3, 4, 5])

# Create some mesh (could be from any mesh source)
meshes = MeshCollection()
meshes.append(Mesh(vertex=d, triangles=[[0, 1], [5, 0], [1, 6]]))

# Animate all this
i = 0
while vtkWindow.is_active:
    # Update markers
    if i < 100:
        vtkModelReal.update_markers(d.get_frame(i))
        vtkModelPred.update_markers(d2.get_frame(i))
        vtkModelMid.update_markers(d3.get_frame(i))
        vtkModelByNames.update_markers(d4.get_frame(i))
        vtkModelFromC3d.update_markers(d5.get_frame(i))
    else:
        # Dynamically change amount of markers for each Model
        vtkModelReal.update_markers(d2.get_frame(i))
        vtkModelPred.update_markers(d3.get_frame(i))
        vtkModelMid.update_markers(d4.get_frame(i))
        vtkModelByNames.update_markers(d5.get_frame(i))
        vtkModelFromC3d.update_markers(d.get_frame(i))

    # Funky online update of markers characteristics
    if i > 150:
        vtkModelReal.set_markers_color(((i % 255.0) / 255.0, (i % 255.0) / 255.0, (i % 255.0) / 255.0))
        vtkModelPred.set_markers_size((i % 150) / 50 + 3)
        vtkModelMid.set_markers_opacity((i % 75) / 75 + 25)

    # Rotate one system of axes
    all_rt_real[0] = RotoTrans(
        angles=FrameDependentNpArray(np.array([i / d.get_num_frames() * np.pi * 2, 0, 0])),
        angle_sequence="yxz",
        translations=d[:, 0:1, 0:1],
    )
    vtkModelReal.update_rt(all_rt_real)

    # Update another system of axes
    vtkModelPred.update_rt(one_rt.get_frame(i))

    # Update the meshing
    vtkModelReal.update_mesh(meshes.get_frame(i))

    # Update window
    vtkWindow.update_frame()
    i = (i + 1) % d.get_num_frames()
