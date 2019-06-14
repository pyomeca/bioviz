import os
import copy

import numpy as np
import biorbd

from pyomeca import Markers3d
from .biorbd_vtk import VtkModel, VtkWindow, Mesh, MeshCollection, RotoTrans, RotoTransCollection
from PyQt5.QtWidgets import QSlider, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, \
    QFileDialog, QScrollArea, QWidget, QMessageBox, QRadioButton, QGroupBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt


class BiorbdViz:
    def __init__(self, model_path=None, loaded_model=None,
                 show_global_ref_frame=True,
                 show_markers=True, show_global_center_of_mass=True, show_segments_center_of_mass=True,
                 show_rt=True, show_muscles=True, show_meshes=True,
                 show_options=True):
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
        self.vtk_model = VtkModel(self.vtk_window, markers_color=(0, 0, 1))
        self.is_executing = False
        self.animation_warning_already_shown = False

        # Set Z vertical
        cam = self.vtk_window.ren.GetActiveCamera()
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(5, 0, 0)
        cam.SetRoll(-90)

        # Get the options
        self.show_markers = show_markers
        self.show_global_ref_frame = show_global_ref_frame
        self.show_global_center_of_mass = show_global_center_of_mass
        self.show_segments_center_of_mass = show_segments_center_of_mass
        self.show_rt = show_rt
        if self.model.nbMuscleTotal() > 0:
            self.show_muscles = show_muscles
        else:
            self.show_muscles = False
        if sum([len(i) for i in self.model.meshPoints(np.zeros(self.model.nbQ()))]) > 0:
            self.show_meshes = show_meshes
        else:
            self.show_meshes = 0

        # Create all the reference to the things to plot
        self.nQ = self.model.nbQ()
        self.Q = np.zeros(self.nQ)
        self.markers = Markers3d(np.ndarray((3, self.model.nTags(), 1)))
        self.global_center_of_mass = Markers3d(np.ndarray((3, 1, 1)))
        self.segments_center_of_mass = Markers3d(np.ndarray((3, self.model.nbBone(), 1)))
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
                elif muscle_type == "HillSimple":
                    musc = biorbd.s2mMuscleHillTypeSimple(musc_tp)
                tp = np.ndarray((3, len(musc.position().musclesPointsInGlobal()), 1))
                for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                    tp[:, k, 0] = pts.get_array()
                self.muscles.append(Mesh(vertex=tp))
        self.rt = RotoTransCollection()
        for rt in self.model.globalJCS(self.Q):
            self.rt.append(RotoTrans(rt.get_array()))

        if self.show_global_ref_frame:
            self.vtk_model.create_global_ref_frame()

        self.show_options = show_options
        if self.show_options:
            self.palette_active = QPalette()
            self.palette_inactive = QPalette()
            self.set_viz_palette()
            self.animated_Q = []

            self.play_stop_push_button = []
            self.is_animating = False
            self.start_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/start.png"))
            self.stop_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/pause.png"))

            self.double_factor = 10000
            self.sliders = list()
            self.movement_slider = []

            self.active_analyses_widget = None
            self.analyses_layout = QHBoxLayout()
            self.analyses_muscle_widget = QWidget()
            self.add_options_panel()

        # Update everything at the position Q=0
        self.set_q(self.Q)

    def reset_q(self):
        self.Q = np.zeros(self.Q.shape)
        for slider in self.sliders:
            slider[1].setValue(0)
            slider[2].setText(f"{0:.2f}")
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
        if self.show_global_center_of_mass:
            self.__set_global_center_of_mass_from_q()
        if self.show_segments_center_of_mass:
            self.__set_segments_center_of_mass_from_q()
        if self.show_markers:
            self.__set_markers_from_q()

        # Update the sliders
        if self.show_options:
            for i, slide in enumerate(self.sliders):
                slide[1].blockSignals(True)
                slide[1].setValue(self.Q[i]*self.double_factor)
                slide[1].blockSignals(False)
                slide[2].setText(f"{self.Q[i]:.2f}")

        if refresh_window:
            self.refresh_window()

    def refresh_window(self):
        """
        Manually refresh the window. One should be aware when manually managing the window, that the plot won't even
        rotate if not refreshed

        """
        self.vtk_window.update_frame()

    def exec(self):
        self.is_executing = True
        while self.vtk_window.is_active:
            if self.show_options and self.is_animating:
                self.movement_slider[0].setValue(
                    (self.movement_slider[0].value() + 1) % self.movement_slider[0].maximum()
                )
            self.refresh_window()
        self.is_executing = False

    def set_viz_palette(self):
        self.palette_active.setColor(QPalette.WindowText, QColor(Qt.black))
        self.palette_active.setColor(QPalette.ButtonText, QColor(Qt.black))

        self.palette_inactive.setColor(QPalette.WindowText, QColor(Qt.gray))

    def add_options_panel(self):
        # Prepare the sliders
        options_layout = QVBoxLayout()

        options_layout.addStretch()  # Centralize the sliders
        sliders_layout = QVBoxLayout()
        max_label_width = -1
        for i in range(self.model.nbDof()):
            slider_layout = QHBoxLayout()

            # Add a name
            name_label = QLabel()
            name = f"{self.model.nameDof()[i]}"
            name_label.setText(name)
            name_label.setPalette(self.palette_active)
            label_width = name_label.fontMetrics().boundingRect(name_label.text()).width()
            if label_width > max_label_width:
                max_label_width = label_width
            slider_layout.addWidget(name_label)

            # Add the slider
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(-np.pi*self.double_factor)
            slider.setMaximum(np.pi*self.double_factor)
            slider.setPageStep(self.double_factor)
            slider.setValue(0)
            slider.valueChanged.connect(self.__move_avatar_from_sliders)
            slider_layout.addWidget(slider)

            # Add the value
            value_label = QLabel()
            value_label.setText(f"{0:.2f}")
            value_label.setPalette(self.palette_active)
            slider_layout.addWidget(value_label)

            # Add to the main sliders
            self.sliders.append((name_label, slider, value_label))
            sliders_layout.addLayout(slider_layout)
        # Adjust the size of the names
        for name_label, _, _ in self.sliders:
            name_label.setFixedWidth(max_label_width + 1)

        # Put the sliders in a scrollable area
        sliders_widget = QWidget()
        sliders_widget.setLayout(sliders_layout)
        sliders_scroll = QScrollArea()
        sliders_scroll.setFrameShape(0)
        sliders_scroll.setWidgetResizable(True)
        sliders_scroll.setWidget(sliders_widget)
        options_layout.addWidget(sliders_scroll)

        # Add reset button
        button_layout = QHBoxLayout()
        reset_push_button = QPushButton("Reset")
        reset_push_button.setPalette(self.palette_active)
        reset_push_button.released.connect(self.reset_q)
        button_layout.addWidget(reset_push_button)
        options_layout.addLayout(button_layout)

        # Add the radio button for analyses
        option_analyses_group = QGroupBox()
        option_analyses_layout = QVBoxLayout()
        # Add text
        analyse_text = QLabel()
        analyse_text.setPalette(self.palette_active)
        analyse_text.setText("Analyses")
        option_analyses_layout.addWidget(analyse_text)
        # Add the no analyses
        radio_none = QRadioButton()
        radio_none.setPalette(self.palette_active)
        radio_none.setChecked(True)
        radio_none.toggled.connect(lambda: self.__select_analyses_panel(radio_none, 0))
        radio_none.setText("None")
        option_analyses_layout.addWidget(radio_none)
        # Add the muscles analyses
        radio_muscle = QRadioButton()
        radio_muscle.setPalette(self.palette_active)
        radio_muscle.toggled.connect(lambda: self.__select_analyses_panel(radio_muscle, 1))
        radio_muscle.setText("Muscles")
        option_analyses_layout.addWidget(radio_muscle)
        # Add the layout to the interface
        option_analyses_group.setLayout(option_analyses_layout)
        options_layout.addWidget(option_analyses_group)

        # Finalize the options panel
        options_layout.addStretch()  # Centralize the sliders

        # Animation panel
        animation_layout = QVBoxLayout()
        animation_layout.addWidget(self.vtk_window.avatar_widget)

        # Add the animation slider
        animation_slider_layout = QHBoxLayout()
        load_push_button = QPushButton("Load movement")
        load_push_button.setPalette(self.palette_active)
        load_push_button.released.connect(self.__load_movement_from_button)
        animation_slider_layout.addWidget(load_push_button)

        # Controllers
        self.play_stop_push_button = QPushButton()
        self.play_stop_push_button.setIcon(self.start_icon)
        self.play_stop_push_button.setPalette(self.palette_active)
        self.play_stop_push_button.setEnabled(False)
        self.play_stop_push_button.released.connect(self.__start_stop_animation)
        animation_slider_layout.addWidget(self.play_stop_push_button)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(0)
        slider.setEnabled(False)
        slider.valueChanged.connect(self.__animate_from_slider)
        animation_slider_layout.addWidget(slider)

        # Add the frame count
        frame_label = QLabel()
        frame_label.setText(f"{0}")
        frame_label.setPalette(self.palette_inactive)
        animation_slider_layout.addWidget(frame_label)

        self.movement_slider = (slider, frame_label)
        animation_layout.addLayout(animation_slider_layout)

        self.vtk_window.main_layout.addLayout(options_layout, 0, 0)
        self.vtk_window.main_layout.addLayout(animation_layout, 0, 1)
        self.vtk_window.main_layout.setColumnStretch(0, 1)
        self.vtk_window.main_layout.setColumnStretch(1, 2)

        # Change the size of the window to account for the new sliders
        self.vtk_window.resize(self.vtk_window.size().width() * 2, self.vtk_window.size().height())

        # Prepare all the analyses panel
        self.__prepare_muscle_analyses_panel()

    def __select_analyses_panel(self, radio_button, panel_to_activate):
        if not radio_button.isChecked():
            return

        # Hide previous analyses panel if necessary
        self.__hide_analyses_panel()

        size_factor_none = 1
        size_factor_muscle = 1.25

        # Find the size factor to get back to normal size
        if self.active_analyses_widget is None:
            reduction_factor = size_factor_none
        elif self.active_analyses_widget == self.analyses_muscle_widget:
            reduction_factor = size_factor_muscle
        else:
            raise RuntimeError("Non-existing panel asked... This should never happen, please report this issue!")

        # Prepare the analyses panel and new size of window
        if panel_to_activate == 0:
            self.active_analyses_widget = None
            enlargement_factor = size_factor_none
        elif panel_to_activate == 1:
            self.active_analyses_widget = self.analyses_muscle_widget
            enlargement_factor = size_factor_muscle
        else:
            raise RuntimeError("Non-existing panel asked... This should never happen, please report this issue!")

        # Activate the required panel
        self.__show_analyses_panel()

        # Enlarge the main window
        self.vtk_window.resize(int(self.vtk_window.size().width() * enlargement_factor / reduction_factor),
                               self.vtk_window.size().height())

    def __hide_analyses_panel(self):
        if self.active_analyses_widget is None:
            return
        # Remove from main window
        self.analyses_muscle_widget.setVisible(False)
        self.vtk_window.main_layout.removeWidget(self.active_analyses_widget)
        self.vtk_window.main_layout.setColumnStretch(2, 0)

    def __show_analyses_panel(self):
        # Give the parent as main window
        if self.active_analyses_widget is not None:
            self.vtk_window.main_layout.addWidget(self.active_analyses_widget, 0, 2)
            self.vtk_window.main_layout.setColumnStretch(2, 1)
            self.analyses_muscle_widget.setVisible(True)

    def __prepare_muscle_analyses_panel(self):
        # Centralize the materials
        analyses_muscle_layout = QVBoxLayout(self.analyses_muscle_widget)
        analyses_muscle_layout.addStretch()

        # Add plots
        tata = QVBoxLayout()
        analyses_layout = QGridLayout()
        canvas = FigureCanvasQTAgg(plt.figure())
        ax = canvas.figure.subplots()
        t = np.linspace(0, 10, 501)
        ax.plot(t, np.tan(t), ".")
        analyses_layout.addWidget(canvas, 0, 0)
        canvas = FigureCanvasQTAgg(plt.figure())
        ax = canvas.figure.subplots()
        t = np.linspace(0, 10, 501)
        ax.plot(t, np.tan(t), "-")
        analyses_layout.addWidget(canvas, 1, 0)
        canvas = FigureCanvasQTAgg(plt.figure())
        ax = canvas.figure.subplots()
        t = np.linspace(0, 10, 501)
        ax.plot(t, np.tan(t), "--")
        analyses_layout.addWidget(canvas, 0, 1)
        canvas = FigureCanvasQTAgg(plt.figure())
        ax = canvas.figure.subplots()
        t = np.linspace(0, 10, 501)
        ax.plot(t, np.tan(t), "-.")
        analyses_layout.addWidget(canvas, 1, 1)
        tata.addLayout(analyses_layout)
        push = QPushButton()
        tata.addWidget(push)
        analyses_muscle_layout.addLayout(tata)

        # Centralize the materials
        analyses_muscle_layout.addStretch()

    def __move_avatar_from_sliders(self):
        for i, slide in enumerate(self.sliders):
            self.Q[i] = slide[1].value()/self.double_factor
            slide[2].setText(f" {self.Q[i]:.2f}")
        self.set_q(self.Q)

    def __animate_from_slider(self):
        # Move the avatar
        self.movement_slider[1].setText(f"{self.movement_slider[0].value()}")
        self.Q = copy.copy(self.animated_Q[self.movement_slider[0].value()-1])  # 1-based
        self.set_q(self.Q)

    def __start_stop_animation(self):
        if not self.is_executing and not self.animation_warning_already_shown:
            QMessageBox.warning(self.vtk_window, 'Not executing',
                                "BiorbdViz has detected that it is not actually executing.\n\n"
                                "Unless you know what you are doing, the automatic play of the animation will "
                                "therefore not work. Please call the BiorbdViz.exec() method to be able to play "
                                "the animation.\n\nPlease note that the animation slider will work in any case.")
            self.animation_warning_already_shown = True
        if self.is_animating:
            self.is_animating = False
            self.play_stop_push_button.setIcon(self.start_icon)
        else:
            self.is_animating = True
            self.play_stop_push_button.setIcon(self.stop_icon)

    def __load_movement_from_button(self):
        # Load the actual movement
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name = QFileDialog.getOpenFileName(self.vtk_window,
                                                "Movement to load", "", "All Files (*)", options=options)
        if not file_name[0]:
            return
        self.animated_Q = np.load(file_name[0])
        self.__load_movement()

    def load_movement(self, all_q, auto_start=True, ignore_animation_warning=True):
        self.animated_Q = all_q
        self.__load_movement()
        if ignore_animation_warning:
            self.animation_warning_already_shown = True
        if auto_start:
            self.__start_stop_animation()

    def __load_movement(self):
        # Activate the start button
        self.is_animating = False
        self.play_stop_push_button.setEnabled(True)
        self.play_stop_push_button.setIcon(self.start_icon)

        # Update the slider bar and frame count
        self.movement_slider[0].setEnabled(True)
        self.movement_slider[0].setMinimum(1)
        self.movement_slider[0].setMaximum(self.animated_Q.shape[0])
        pal = QPalette()
        pal.setColor(QPalette.WindowText, QColor(Qt.black))
        self.movement_slider[1].setPalette(pal)

        # Put back to first frame
        self.movement_slider[0].setValue(1)

    def __set_markers_from_q(self):
        markers = self.model.Tags(self.model, self.Q)
        for k, mark in enumerate(markers):
            self.markers[0:3, k, 0] = mark.get_array()
        self.vtk_model.update_markers(self.markers.get_frame(0))

    def __set_global_center_of_mass_from_q(self):
        com = self.model.CoM(self.Q)
        self.global_center_of_mass[0:3, 0, 0] = com.get_array()
        self.vtk_model.update_global_center_of_mass(self.global_center_of_mass.get_frame(0))

    def __set_segments_center_of_mass_from_q(self):
        coms = self.model.CoMbySegment(self.Q)
        for k, com in enumerate(coms):
            self.segments_center_of_mass[0:3, k, 0] = com.get_array()
        self.vtk_model.update_segments_center_of_mass(self.segments_center_of_mass.get_frame(0))

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
                elif muscle_type == "HillSimple":
                    musc = biorbd.s2mMuscleHillTypeSimple(musc_tp)
                for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                    self.muscles.get_frame(0)[idx][0:3, k] = pts.get_array()
                idx += 1
        self.vtk_model.update_muscle(self.muscles)

    def __set_rt_from_q(self):
        for k, rt in enumerate(self.model.globalJCS(self.Q, True)):
            self.rt[k] = RotoTrans(rt.get_array())
        self.vtk_model.update_rt(self.rt)
