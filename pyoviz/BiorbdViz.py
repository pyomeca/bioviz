import numpy as np
import biorbd

from pyomeca import Markers3d
from pyoviz.vtk import VtkModel, VtkWindow, Mesh, MeshCollection, RotoTrans, RotoTransCollection


class BiorbdViz():
    def __init__(self, loaded_model=None, model_path=None,
                 show_markers=True, show_rt=True, show_muscles=True, show_meshes=True):
        """
        Class that easily shows a biorbd model
        Args:
            loaded_model: reference to a biorbd loaded model (if both loaded_model and model_path, load_model is selected
            model_path: path of the model to load
        """

        # Load and store the model
        if loaded_model is not None:
            if not isinstance(loaded_model, biorbd.s2mMusculoSkeletalModel):
                raise TypeError("loaded_model should be of a biorbd.s2mMusculoSkeletalModel type")
            self.model = loaded_model
        elif model_path is not None:
            self.model = biorbd.s2mMusculoSkeletalModel(model_path)
        else:
            raise ValueError("loaded_model or model_path must be provided")

        # Create the plot
        self.vtk_window = VtkWindow(background_color=(.5, .5, .5))
        self.vtk_model = VtkModel(self.vtk_window, markers_color=(0, 0, 1), markers_size=0.010, markers_opacity=1,
                                  mesh_color=(0, 0, 0))

        # Set Z vertical
        cam = self.vtk_window.ren.GetActiveCamera()
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(5, 0, 0)
        cam.SetRoll(-90)

        # Get the options
        self.show_markers = show_markers
        self.show_rt = show_rt
        self.show_muscles = show_muscles
        self.show_meshes = show_meshes

        # Create all the reference to the things to plot
        self.nQ = self.model.nbQ()
        self.Q = np.zeros(self.nQ)
        self.markers = Markers3d(np.ndarray((3, self.model.nTags(), 1)))
        self.mesh = MeshCollection()
        for l, meshes in enumerate(self.model.meshPoints(self.Q)):
            tp = np.ndarray((3, len(meshes), 1))
            for k, mesh in enumerate(meshes):
                tp[:, k, 0] = mesh.get_array()
            self.mesh.append(Mesh(vertex=tp))
        self.model.updateMuscles(self.model, self.Q, True)
        self.muscles = MeshCollection()
        for group_idx in range(self.model.nbMuscleGroups()):
            for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                musc_tp = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                muscle_type = biorbd.s2mMusculoSkeletalModel.getMuscleType(musc_tp)
                if muscle_type == "Hill":
                    musc = biorbd.s2mMuscleHillType(musc_tp)
                elif muscle_type == "HillThelen":
                    musc = biorbd.s2mMuscleHillTypeThelen(musc_tp)
                tp = np.ndarray((3, len(musc.position().musclesPointsInGlobal()), 1))
                for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                    tp[:, k, 0] = pts.get_array()
                self.muscles.append(Mesh(vertex=tp))
        self.rt = RotoTransCollection()
        for rt in self.model.globalJCS(self.Q):
            self.rt.append(RotoTrans(rt.get_array()))
        # Update everything at the position Q=0
        self.set_q(self.Q)

    def set_q(self, Q, refresh_window=True):
        """
        Manually update
        Args:
            Q: np.array
        """
        if not isinstance(Q, np.ndarray) and len(Q.shape) > 1 and Q.shape[0] != self.nQ:
            raise TypeError(f"Q should be a {self.nQ} column vector")
        self.Q = Q

        if self.show_muscles:
            self.__set_muscles_from_q()
        if self.show_rt:
            self.__set_rt_from_q()
        if self.show_meshes:
            self.__set_meshes_from_q()
        if self.show_markers:
            self.__set_markers_from_q()

        if refresh_window:
            self.refresh_window()

    def refresh_window(self):
        """
        Manually refresh the window. One should be aware when manually managing the window, that the plot won't even
        rotate if not refreshed

        """
        self.vtk_window.update_frame()

    def __set_markers_from_q(self):
        markers = self.model.Tags(self.model, self.Q)
        for k, mark in enumerate(markers):
            self.markers[0:3, k, 0] = mark.get_array()
        self.vtk_model.update_markers(self.markers.get_frame(0))

    def __set_meshes_from_q(self):
        for l, meshes in enumerate(self.model.meshPoints(self.Q, False)):
            for k, mesh in enumerate(meshes):
                self.mesh.get_frame(0)[l][0:3, k] = mesh.get_array()
        self.vtk_model.update_mesh(self.mesh)

    def __set_muscles_from_q(self):
        self.model.updateMuscles(self.model, self.Q, True)

        idx = 0
        for group_idx in range(self.model.nbMuscleGroups()):
            for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                musc_tp = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                muscle_type = biorbd.s2mMusculoSkeletalModel.getMuscleType(musc_tp)
                if muscle_type == "Hill":
                    musc = biorbd.s2mMuscleHillType(musc_tp)
                elif muscle_type == "HillThelen":
                    musc = biorbd.s2mMuscleHillTypeThelen(musc_tp)
                for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                    self.muscles.get_frame(0)[idx][0:3, k] = pts.get_array()
                idx += 1
        self.vtk_model.update_muscle(self.muscles)

    def __set_rt_from_q(self):
        for k, rt in enumerate(self.model.globalJCS(self.Q, True)):
            self.rt[k] = RotoTrans(rt.get_array())
        self.vtk_model.update_rt(self.rt)
