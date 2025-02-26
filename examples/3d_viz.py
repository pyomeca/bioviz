"""
Example script for animating a model
"""

import os

from bioviz.biorbd_vtk import VtkModel, VtkWindow, Mesh
import numpy as np
from pyomeca import Markers, Rototrans, Angles


def main():
    # Path to the C3D file
    data_folder = f"{os.getcwd()}/../tests/data"
    markers_c3d_file = f"{data_folder}markers_analogs.c3d"

    # Load data
    d = Markers.from_c3d(markers_c3d_file, usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], prefix_delimiter=":")
    d2 = Markers.from_c3d(markers_c3d_file, usecols=["CLAV_post", "PSISl", "STERr", "CLAV_post"], prefix_delimiter=":")
    # mean of first 3 markers
    d3 = Markers.from_c3d(markers_c3d_file, usecols=[0, 1, 2], prefix_delimiter=":").mean("channel", keepdims=True)

    # Create a windows with a nice gray background
    vtk_window = VtkWindow(background_color=(0.5, 0.5, 0.5))

    # Add marker holders to the window
    vtk_model_real = VtkModel(vtk_window, markers_color=(1, 0, 0), markers_size=10.0, markers_opacity=1, rt_length=100)
    vtk_model_pred = VtkModel(
        vtk_window, markers_color=(0, 0, 0), markers_size=10.0, markers_opacity=0.5, rt_length=100
    )
    vtk_model_mid = VtkModel(vtk_window, markers_color=(0, 0, 1), markers_size=10.0, markers_opacity=0.5, rt_length=100)
    vtk_model_from_c3d = VtkModel(
        vtk_window, markers_color=(0, 1, 0), markers_size=10.0, markers_opacity=0.5, rt_length=100
    )

    # Create some RotoTrans attached to the first model
    all_rt_real = []
    all_rt_real.append(
        Rototrans.from_euler_angles(
            angles=Angles(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, [0], [0]]
        )
    )
    all_rt_real.append(
        Rototrans.from_euler_angles(
            angles=Angles(np.zeros((3, 1, 1))), angle_sequence="yxz", translations=d[:, [0], [0]]
        )
    )

    # Create some Rototrans attached to the second model
    one_rt = Rototrans.from_markers(
        origin=d[:, [3, 5], :].mean("channel", keepdims=True),
        axis_1=d[:, [4, 3], :],
        axis_2=d[:, [4, 5], :],
        axes_name="zx",
        axis_to_recalculate="z",
    )

    # Create some mesh (could be from any mesh source)
    meshes = []
    meshes.append(Mesh(vertex=d, triangles=[[0, 1], [5, 0], [1, 6]]))

    # Animate all this
    i = 0
    while vtk_window.is_active:
        # Update markers
        if i < 100:
            vtk_model_real.update_markers(d[:, :, i])
            vtk_model_pred.update_markers(d2[:, :, i])
            vtk_model_mid.update_markers(d3[:, :, i])
        else:
            # Dynamically change amount of markers for each Model
            vtk_model_from_c3d.update_markers(d[:, :, i])
            vtk_model_real.update_markers(d2[:, :, i])
            vtk_model_pred.update_markers(d3[:, :, i])

        # Funky online update of markers characteristics
        if i > 150:
            vtk_model_real.set_markers_color(((i % 255.0) / 255.0, (i % 255.0) / 255.0, (i % 255.0) / 255.0))
            vtk_model_from_c3d.set_markers_size((i % 150) / 20)

        # Rotate one system of axes
        all_rt_real[0] = Rototrans.from_euler_angles(
            angles=Angles(np.array([i / d.shape[2] * np.pi * 2, 0, 0])[:, np.newaxis, np.newaxis]),
            angle_sequence="yxz",
            translations=d[:, [0], [0]],
        )
        vtk_model_real.update_rt(all_rt_real)

        # Update another system of axes
        vtk_model_pred.update_rt([one_rt[:, :, [i]]])

        # Update the meshing
        vtk_model_real.update_mesh([m[:, :, [i]] for m in meshes])

        # Update window
        vtk_window.update_frame()
        i = (i + 1) % d.shape[2]

    vtk_window.close()


if __name__ == "__main__":
    main()
