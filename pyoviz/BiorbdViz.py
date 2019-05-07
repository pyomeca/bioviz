import numpy as np
import biorbd

from pyomeca import Markers3d
from pyoviz.vtk import VtkModel, VtkWindow, Mesh, MeshCollection, RotoTrans, RotoTransCollection
from PyQt5.QtWidgets import QWidget, QSlider, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor


class BiorbdViz():
    def __init__(self, loaded_model=None, model_path=None,
                 show_markers=True, show_rt=True, show_muscles=True, show_meshes=True,
                 add_sliders=True):
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
        if add_sliders:
            self.animated_Q = []
            self.double_factor = 10000
            self.sliders = list()
            self.movement_slider = []
            self.add_options_panel()

    def add_options_panel(self):
        # Prepare the sliders
        options_layout = QVBoxLayout()
        pal = QPalette()
        pal.setColor(QPalette.WindowText, QColor(Qt.black))
        pal.setColor(QPalette.ButtonText, QColor(Qt.black))
        pal_inactive = QPalette()
        pal_inactive.setColor(QPalette.WindowText, QColor(Qt.gray))
        options_layout.addStretch()  # Centralize the sliders
        max_label_width = -1
        for i in range(self.model.nbDof()):
            slider_layout = QHBoxLayout()

            # Add a name
            name_label = QLabel()
            name = f"{self.model.nameDof()[i]}"
            name_label.setText(name)
            name_label.setPalette(pal)
            label_width = name_label.fontMetrics().boundingRect(name_label.text()).width()
            if label_width > max_label_width:
                max_label_width = label_width
            slider_layout.addWidget(name_label)

            # Add the slider
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(-np.pi*self.double_factor)
            slider.setMaximum(np.pi*self.double_factor)
            slider.setValue(0)
            slider.valueChanged.connect(self.move_avatar_from_sliders)
            slider_layout.addWidget(slider)

            # Add the value
            value_label = QLabel()
            value_label.setText(f" {0:.2f}")
            value_label.setPalette(pal)
            slider_layout.addWidget(value_label)

            # Add to the main sliders
            self.sliders.append((name_label, slider, value_label))
            options_layout.addLayout(slider_layout)
        # Adjust the size of the names
        for name_label, _, _ in self.sliders:
            name_label.setFixedWidth(max_label_width+1)

        # Add reset button
        button_layout = QHBoxLayout()
        reset_push_button = QPushButton("Reset")
        reset_push_button.setPalette(pal)
        reset_push_button.released.connect(self.reset_q)
        button_layout.addWidget(reset_push_button)
        options_layout.addLayout(button_layout)

        # Finalize the options panel
        options_layout.addStretch()  # Centralize the sliders

        # Animation panel
        animation_layout = QVBoxLayout()
        animation_layout.addWidget(self.vtk_window.vtkWidget)

        # Add the animation slider
        animation_slider_layout = QHBoxLayout()
        load_push_button = QPushButton("Load movement")
        load_push_button.setPalette(pal)
        load_push_button.released.connect(self.load_movement)
        animation_slider_layout.addWidget(load_push_button)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(0)
        slider.setEnabled(False)
        slider.valueChanged.connect(self.animate_from_slider)
        animation_slider_layout.addWidget(slider)

        # Add the frame count
        frame_label = QLabel()
        frame_label.setText(f" {0}")
        frame_label.setPalette(pal_inactive)
        animation_slider_layout.addWidget(frame_label)

        self.movement_slider = (slider, frame_label)
        animation_layout.addLayout(animation_slider_layout)

        # Add the options part and the main window and make them 1:2 ratio
        self.vtk_window.main_QHBoxLayout.addLayout(options_layout, 33)
        self.vtk_window.main_QHBoxLayout.addLayout(animation_layout, 66)

        # Change the size of the window to account for the new sliders
        self.vtk_window.resize(self.vtk_window.size().width() * 2, self.vtk_window.size().height())

    def move_avatar_from_sliders(self):
        for i, slide in enumerate(self.sliders):
            self.Q[i] = slide[1].value()/self.double_factor
            slide[2].setText(f" {self.Q[i]:.2f}")
        self.set_q(self.Q, refresh_window=False)

    def animate_from_slider(self):
        # Move the avatar
        self.movement_slider[1].setText(f"{self.movement_slider[0].value()}")
        self.Q = self.animated_Q[self.movement_slider[0].value()-1]  # 1-based
        self.set_q(self.Q)

        # Update the slider
        for i, slide in enumerate(self.sliders):
            slide[1].blockSignals(True)
            slide[1].setValue(self.Q[i]*self.double_factor)
            slide[1].blockSignals(False)
            slide[2].setText(f" {self.Q[i]:.2f}")

    def load_movement(self):
        # Load the actual movement
        n_frames = 200
        self.animated_Q = np.ndarray((n_frames, self.nQ))
        self.animated_Q[:, 4] = np.linspace(0, np.pi / 2, n_frames)

        # Update the slider bar and frame count
        self.movement_slider[0].setEnabled(True)
        self.movement_slider[0].setMinimum(1)
        self.movement_slider[0].setMaximum(self.animated_Q.shape[0])
        pal = QPalette()
        pal.setColor(QPalette.WindowText, QColor(Qt.black))
        self.movement_slider[1].setPalette(pal)
        self.movement_slider[1].setText(f"{1}")

    def reset_q(self):
        self.Q = np.zeros(self.Q.shape)
        for slider in self.sliders:
            slider[1].setValue(0)
            slider[2].setText(f" {0:.2f}")
        self.set_q(self.Q)

    def set_q(self, Q, refresh_window=True):
        """
        Manually update
        Args:
            Q: np.array
                Generalized coordinate
            refresh_window: bool
                If the window should be refreshed now or not
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

    def exec(self):
        while self.vtk_window.is_active:
            self.refresh_window()

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
