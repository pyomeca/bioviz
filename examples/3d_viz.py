"""
Example script for animating a model
"""

from pathlib import Path

import numpy as np

from pyomeca import Markers, Rototrans, Angles
from BiorbdViz.biorbd_vtk import VtkModel, VtkWindow, Mesh

# Path to data
DATA_FOLDER = Path("/home/pariterre/Programmation/biorbd-viz") / "tests" / "data"
MARKERS_CSV = DATA_FOLDER / "markers.csv"
MARKERS_ANALOGS_C3D = DATA_FOLDER / "markers_analogs.c3d"

# Load data
d = Markers.from_c3d(MARKERS_ANALOGS_C3D, usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], prefix_delimiter=":")
d2 = Markers.from_c3d(MARKERS_ANALOGS_C3D, usecols=["CLAV_post", "PSISl", "STERr", "CLAV_post"], prefix_delimiter=":")
# mean of first 3 markers
d3 = Markers.from_c3d(MARKERS_ANALOGS_C3D, usecols=[0, 1, 2], prefix_delimiter=":").mean("channel", keepdims=True)

# Create a windows with a nice gray background
vtkWindow = VtkWindow(background_color=(0.5, 0.5, 0.5))

# Add marker holders to the window
vtkModelReal = VtkModel(vtkWindow, markers_color=(1, 0, 0), markers_size=10.0, markers_opacity=1, rt_length=100)
vtkModelPred = VtkModel(vtkWindow, markers_color=(0, 0, 0), markers_size=10.0, markers_opacity=0.5, rt_length=100)
vtkModelMid = VtkModel(vtkWindow, markers_color=(0, 0, 1), markers_size=10.0, markers_opacity=0.5, rt_length=100)
vtkModelFromC3d = VtkModel(vtkWindow, markers_color=(0, 1, 0), markers_size=10.0, markers_opacity=0.5, rt_length=100)

# Create some RotoTrans attached to the first model
all_rt_real = []
all_rt_real.append(
    Rototrans.from_euler_angles(angles=Angles(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, [0], [0]])
)
all_rt_real.append(
    Rototrans.from_euler_angles(angles=Angles(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, [0], [0]])
)

# Create some Rototrans attached to the second model
one_rt = Rototrans.from_markers(origin=d[:, [3, 5], :].mean("channel", keepdims=True),
                                axis_1=d[:, [4, 3], :], axis_2=d[:, [4, 5], :], axes_name="zx", axis_to_recalculate="z")

# Create some mesh (could be from any mesh source)
meshes = []
meshes.append(Mesh(vertex=d, triangles=[[0, 1], [5, 0], [1, 6]]))

# Animate all this
i = 0
while vtkWindow.is_active:
    # Update markers
    if i < 100:
        vtkModelReal.update_markers(d[:, :, i])
        vtkModelPred.update_markers(d2[:, :, i])
        vtkModelMid.update_markers(d3[:, :, i])
    else:
        # Dynamically change amount of markers for each Model
        vtkModelFromC3d.update_markers(d[:, :, i])
        vtkModelReal.update_markers(d2[:, :, i])
        vtkModelPred.update_markers(d3[:, :, i])

    # Funky online update of markers characteristics
    if i > 150:
        vtkModelReal.set_markers_color(((i % 255.0) / 255.0, (i % 255.0) / 255.0, (i % 255.0) / 255.0))
        vtkModelFromC3d.set_markers_size((i % 150) / 20)

    # Rotate one system of axes
    all_rt_real[0] = Rototrans.from_euler_angles(
        angles=Angles(np.array([i / d.shape[2] * np.pi * 2, 0, 0])[:, np.newaxis, np.newaxis]),
        angle_sequence="yxz",
        translations=d[:, [0], [0]],
    )
    vtkModelReal.update_rt(all_rt_real)

    # Update another system of axes
    vtkModelPred.update_rt([one_rt[:, :, [i]]])

    # Update the meshing
    vtkModelReal.update_mesh([m[:, :, [i]] for m in meshes])

    # Update window
    vtkWindow.update_frame()
    i = (i + 1) % d.shape[2]
