import os
import copy
from functools import partial

from packaging.version import parse as parse_version
import numpy as np
import scipy
import biorbd

if biorbd.currentLinearAlgebraBackend() == 1:
    import casadi

import pyomeca
from .biorbd_vtk import VtkModel, VtkWindow, Mesh, Rototrans
from PyQt5.QtWidgets import (
    QSlider,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QScrollArea,
    QWidget,
    QMessageBox,
    QRadioButton,
    QGroupBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor, QPixmap, QIcon

from .analyses import MuscleAnalyses
from ._version import __version__


def check_version(tool_to_compare, min_version, max_version):
    name = tool_to_compare.__name__
    try:
        ver = parse_version(tool_to_compare.__version__)
    except AttributeError:
        print(f"Version for {name} could not be compared...")
        return

    if ver < parse_version(min_version):
        raise ImportError(f"{name} should be at least version {min_version}")
    elif ver > parse_version(max_version):
        raise ImportError(f"{name} should be lesser than version {max_version}")


check_version(biorbd, "1.3.1", "2.0.0")
check_version(pyomeca, "2020.0.1", "2020.1.0")
from pyomeca import Markers


class InterfacesCollections:
    class BiorbdFunc:
        def __init__(self, model):
            self.m = model
            self.data = None
            if biorbd.currentLinearAlgebraBackend() == 0:
                self._prepare_function_for_eigen()
                self.get_data_func = self._get_data_from_eigen
            elif biorbd.currentLinearAlgebraBackend() == 1:
                self._prepare_function_for_casadi()
                self.get_data_func = self._get_data_from_casadi
            else:
                raise RuntimeError("Unrecognized currentLinearAlgebraBackend")

        def _prepare_function_for_eigen(self):
            pass

        def _prepare_function_for_casadi(self):
            pass

        def _get_data_from_eigen(self, **kwargs):
            raise RuntimeError("BiorbdFunc is an abstract class and _get_data_from_eigen can't be directly called")

        def _get_data_from_casadi(self, **kwargs):
            raise RuntimeError("BiorbdFunc is an abstract class and _get_data_from_casadi can't be directly called")

        def get_data(self, **kwargs):
            self.get_data_func(**kwargs)
            return self.data

    class Markers(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, self.m.nbMarkers(), 1))

        def _prepare_function_for_casadi(self):
            q_sym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.markers = casadi.Function("Markers", [q_sym], [self.m.markers(q_sym)]).expand()

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                markers = self.m.markers(Q, True, True)
            else:
                markers = self.m.markers(Q, True, False)
            for i in range(self.m.nbMarkers()):
                self.data[:, i, 0] = markers[i].to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data[:, :, 0] = np.array(self.markers(Q))

    class CoM(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ones((4, 1, 1))

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.CoM = casadi.Function("CoM", [Qsym], [self.m.CoM(Qsym).to_mx()]).expand()

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                CoM = self.m.CoM(Q)
            else:
                CoM = self.m.CoM(Q, False)
            for i in range(self.m.nbSegment()):
                self.data[:3, 0, 0] = CoM.to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data[:3, :, 0] = self.CoM(Q)

    class CoMbySegment(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, 1, 1))

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.CoMs = casadi.Function("CoMbySegment", [Qsym], [self.m.CoMbySegmentInMatrix(Qsym).to_mx()]).expand()

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                allCoM = self.m.CoMbySegment(Q)
            else:
                allCoM = self.m.CoMbySegment(Q, False)
            for com in allCoM:
                self.data.append(np.append(com.to_array(), 1))

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                self.data.append(np.append(self.CoMs(Q)[:, i], 1))

    class MusclesPointsInGlobal(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.groups = []
            for group_idx in range(self.m.nbMuscleGroups()):
                muscles = []
                for muscle_idx in range(self.m.muscleGroup(group_idx).nbMuscles()):
                    musc = self.m.muscleGroup(group_idx).muscle(muscle_idx)
                    for via in range(len(musc.musclesPointsInGlobal())):
                        muscles.append(
                            casadi.Function(
                                "MusclesPointsInGlobal", [Qsym], [musc.musclesPointsInGlobal(self.m, Qsym)[via].to_mx()]
                            ).expand()
                        )
                self.groups.append(muscles)

        def _get_data_from_eigen(self, Q=None):
            self.data = []
            self.m.updateMuscles(Q, True)
            idx = 0
            for group_idx in range(self.m.nbMuscleGroups()):
                for muscle_idx in range(self.m.muscleGroup(group_idx).nbMuscles()):
                    musc = self.m.muscleGroup(group_idx).muscle(muscle_idx)
                    for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                        self.data.append(pts.to_array()[:, np.newaxis])
                    idx += 1

        def _get_data_from_casadi(self, Q=None):
            self.data = []
            for g in self.groups:
                for m in g:
                    self.data.append(np.array(m(Q)))

    class MeshPointsInMatrix(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.segments = []
            for i in range(self.m.nbSegment()):
                self.segments.append(
                    casadi.Function("MeshPointsInMatrix", [Qsym], [self.m.meshPointsInMatrix(Qsym)[i].to_mx()]).expand()
                )

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                meshPointsInMatrix = self.m.meshPointsInMatrix(Q)
            else:
                meshPointsInMatrix = self.m.meshPointsInMatrix(Q, False)
            for i in range(self.m.nbSegment()):
                self.data.append(meshPointsInMatrix[i].to_array()[:, :, np.newaxis])

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                nb_vertex = self.m.segment(i).characteristics().mesh().nbVertex()
                vertices = np.ndarray((3, nb_vertex, 1))
                vertices[:, :, 0] = self.segments[i](Q)
                self.data.append(vertices)

    class AllGlobalJCS(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.jcs = []
            for i in range(self.m.nbSegment()):
                self.jcs.append(casadi.Function("allGlobalJCS", [Qsym], [self.m.allGlobalJCS(Qsym)[i].to_mx()]))

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                allJCS = self.m.allGlobalJCS(Q)
            else:
                allJCS = self.m.allGlobalJCS()
            for jcs in allJCS:
                self.data.append(jcs.to_array())

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                self.data.append(np.array(self.jcs[i](Q)))


class BiorbdViz:
    def __init__(
        self,
        model_path=None,
        loaded_model=None,
        show_meshes=True,
        show_global_center_of_mass=True,
        show_segments_center_of_mass=True,
        show_global_ref_frame=True,
        show_local_ref_frame=True,
        show_markers=True,
        markers_size=0.010,
        show_muscles=True,
        show_analyses_panel=True,
        **kwargs,
    ):
        """
        Class that easily shows a biorbd model
        Args:
            loaded_model: reference to a biorbd loaded model (if both loaded_model and model_path, load_model is selected
            model_path: path of the model to load
        """

        # Load and store the model
        if loaded_model is not None:
            if not isinstance(loaded_model, biorbd.Model):
                raise TypeError("loaded_model should be of a biorbd.Model type")
            self.model = loaded_model
        elif model_path is not None:
            self.model = biorbd.Model(model_path)
        else:
            raise ValueError("loaded_model or model_path must be provided")

        # Create the plot
        self.vtk_window = VtkWindow(background_color=(0.5, 0.5, 0.5))
        self.vtk_model = VtkModel(self.vtk_window, markers_color=(0, 0, 1), markers_size=markers_size)
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
        self.show_local_ref_frame = show_local_ref_frame
        if self.model.nbMuscles() > 0:
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
        self.markers = Markers(np.ndarray((3, self.model.nbMarkers(), 1)))
        if self.show_markers:
            self.Markers = InterfacesCollections.Markers(self.model)
            self.global_center_of_mass = Markers(np.ndarray((3, 1, 1)))
        if self.show_global_center_of_mass:
            self.CoM = InterfacesCollections.CoM(self.model)
            self.segments_center_of_mass = Markers(np.ndarray((3, self.model.nbSegment(), 1)))
        if self.show_segments_center_of_mass:
            self.CoMbySegment = InterfacesCollections.CoMbySegment(self.model)
        if self.show_meshes:
            self.mesh = []
            self.meshPointsInMatrix = InterfacesCollections.MeshPointsInMatrix(self.model)
            for i, vertices in enumerate(self.meshPointsInMatrix.get_data(Q=self.Q, compute_kin=False)):
                triangles = np.ndarray((len(self.model.meshFaces()[i]), 3), dtype="int32")
                for k, patch in enumerate(self.model.meshFaces()[i]):
                    triangles[k, :] = patch.face()
                self.mesh.append(Mesh(vertex=vertices, triangles=triangles.T))
        self.model.updateMuscles(self.Q, True)
        self.muscles = []
        for group_idx in range(self.model.nbMuscleGroups()):
            for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                musc = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                tp = np.zeros((3, len(musc.position().musclesPointsInGlobal()), 1))
                self.muscles.append(Mesh(vertex=tp))
        self.musclesPointsInGlobal = InterfacesCollections.MusclesPointsInGlobal(self.model)
        self.rt = []
        self.allGlobalJCS = InterfacesCollections.AllGlobalJCS(self.model)
        for rt in self.allGlobalJCS.get_data(Q=self.Q, compute_kin=False):
            self.rt.append(Rototrans(rt))

        if self.show_global_ref_frame:
            self.vtk_model.create_global_ref_frame()

        self.show_analyses_panel = show_analyses_panel
        if self.show_analyses_panel:
            self.muscle_analyses = []
            self.palette_active = QPalette()
            self.palette_inactive = QPalette()
            self.set_viz_palette()
            self.animated_Q = []

            self.play_stop_push_button = []
            self.is_animating = False
            self.is_recording = False
            self.start_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/start.png"))
            self.pause_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/pause.png"))
            self.record_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/record.png"))
            self.add_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/add.png"))
            self.stop_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/stop.png"))

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

        # Reset also muscle analyses graphs
        self.__update_muscle_analyses_graphs(False, False, False, False)

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

        self.model.UpdateKinematicsCustom(self.Q)
        if self.show_muscles:
            self.__set_muscles_from_q()
        if self.show_local_ref_frame:
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
        if self.show_analyses_panel:
            for i, slide in enumerate(self.sliders):
                slide[1].blockSignals(True)
                slide[1].setValue(self.Q[i] * self.double_factor)
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

    def update(self):
        if self.show_analyses_panel and self.is_animating:
            self.movement_slider[0].setValue(
                (self.movement_slider[0].value() + 1) % (self.movement_slider[0].maximum() + 1)
            )

            if self.is_recording:
                self.__record()
                if self.movement_slider[0].value() + 1 == (self.movement_slider[0].maximum() + 1):
                    self.__start_stop_animation()
        self.refresh_window()

    def exec(self):
        self.is_executing = True
        while self.vtk_window.is_active:
            self.update()
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

        # Get min and max for all dof
        ranges = []
        for i in range(self.model.nbSegment()):
            seg = self.model.segment(i)
            for r in seg.QRanges():
                ranges.append([r.min(), r.max()])

        for i in range(self.model.nbQ()):
            slider_layout = QHBoxLayout()
            sliders_layout.addLayout(slider_layout)

            # Add a name
            name_label = QLabel()
            name = f"{self.model.nameDof()[i].to_string()}"
            name_label.setText(name)
            name_label.setPalette(self.palette_active)
            label_width = name_label.fontMetrics().boundingRect(name_label.text()).width()
            if label_width > max_label_width:
                max_label_width = label_width
            slider_layout.addWidget(name_label)

            # Add the slider
            slider = QSlider(Qt.Horizontal)
            slider.setMinimumSize(100, 0)
            slider.setMinimum(ranges[i][0] * self.double_factor)
            slider.setMaximum(ranges[i][1] * self.double_factor)
            slider.setPageStep(self.double_factor)
            slider.setValue(0)
            slider.valueChanged.connect(self.__move_avatar_from_sliders)
            slider.sliderReleased.connect(partial(self.__update_muscle_analyses_graphs, False, False, False, False))
            slider_layout.addWidget(slider)

            # Add the value
            value_label = QLabel()
            value_label.setText(f"{0:.2f}")
            value_label.setPalette(self.palette_active)
            slider_layout.addWidget(value_label)

            # Add to the main sliders
            self.sliders.append((name_label, slider, value_label))
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
        options_layout.addLayout(button_layout)
        reset_push_button = QPushButton("Reset")
        reset_push_button.setPalette(self.palette_active)
        reset_push_button.released.connect(self.reset_q)
        button_layout.addWidget(reset_push_button)

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
        animation_layout.addLayout(animation_slider_layout)
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

        self.record_push_button = QPushButton()
        self.record_push_button.setIcon(self.record_icon)
        self.record_push_button.setPalette(self.palette_active)
        self.record_push_button.setEnabled(True)
        self.record_push_button.released.connect(self.__record)
        animation_slider_layout.addWidget(self.record_push_button)

        self.stop_record_push_button = QPushButton()
        self.stop_record_push_button.setIcon(self.stop_icon)
        self.stop_record_push_button.setPalette(self.palette_active)
        self.stop_record_push_button.setEnabled(False)
        self.stop_record_push_button.released.connect(self.__stop_record, True)
        animation_slider_layout.addWidget(self.stop_record_push_button)

        # Add the frame count
        frame_label = QLabel()
        frame_label.setText(f"{0}")
        frame_label.setPalette(self.palette_inactive)
        animation_slider_layout.addWidget(frame_label)

        self.movement_slider = (slider, frame_label)

        # Global placement of the window
        self.vtk_window.main_layout.addLayout(options_layout, 0, 0)
        self.vtk_window.main_layout.addLayout(animation_layout, 0, 1)
        self.vtk_window.main_layout.setColumnStretch(0, 1)
        self.vtk_window.main_layout.setColumnStretch(1, 2)

        # Change the size of the window to account for the new sliders
        self.vtk_window.resize(self.vtk_window.size().width() * 2, self.vtk_window.size().height())

        # Prepare all the analyses panel
        self.muscle_analyses = MuscleAnalyses(self.analyses_muscle_widget, self)
        if biorbd.currentLinearAlgebraBackend() == 1:
            radio_muscle.setEnabled(False)
        else:
            if self.model.nbMuscles() == 0:
                radio_muscle.setEnabled(False)
        self.__select_analyses_panel(radio_muscle, 1)

    def __select_analyses_panel(self, radio_button, panel_to_activate):
        if not radio_button.isChecked():
            return

        # Hide previous analyses panel if necessary
        self.__hide_analyses_panel()

        size_factor_none = 1
        size_factor_muscle = 1.40

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
        self.__show_local_ref_frame()

        # Enlarge the main window
        self.vtk_window.resize(
            int(self.vtk_window.size().width() * enlargement_factor / reduction_factor), self.vtk_window.size().height()
        )

    def __hide_analyses_panel(self):
        if self.active_analyses_widget is None:
            return
        # Remove from main window
        self.active_analyses_widget.setVisible(False)
        self.vtk_window.main_layout.removeWidget(self.active_analyses_widget)
        self.vtk_window.main_layout.setColumnStretch(2, 0)

    def __show_local_ref_frame(self):
        # Give the parent as main window
        if self.active_analyses_widget is not None:
            self.vtk_window.main_layout.addWidget(self.active_analyses_widget, 0, 2)
            self.vtk_window.main_layout.setColumnStretch(2, 4)
            self.active_analyses_widget.setVisible(True)

        # Update graphs if needed
        self.__update_muscle_analyses_graphs(False, False, False, False)

    def __move_avatar_from_sliders(self):
        for i, slide in enumerate(self.sliders):
            self.Q[i] = slide[1].value() / self.double_factor
            slide[2].setText(f" {self.Q[i]:.2f}")
        self.set_q(self.Q)

    def __update_muscle_analyses_graphs(
        self, skip_muscle_length, skip_moment_arm, skip_passive_forces, skip_active_forces
    ):
        # Adjust muscle analyses if needed
        if self.active_analyses_widget == self.analyses_muscle_widget:
            self.muscle_analyses.update_all_graphs(
                skip_muscle_length, skip_moment_arm, skip_passive_forces, skip_active_forces
            )

    def __animate_from_slider(self):
        # Move the avatar
        self.movement_slider[1].setText(f"{self.movement_slider[0].value()}")
        self.Q = copy.copy(self.animated_Q[self.movement_slider[0].value() - 1])  # 1-based
        self.set_q(self.Q)

        # Update graph of muscle analyses
        self.__update_muscle_analyses_graphs(True, True, True, True)

    def __start_stop_animation(self):
        if not self.is_executing and not self.animation_warning_already_shown:
            QMessageBox.warning(
                self.vtk_window,
                "Not executing",
                "BiorbdViz has detected that it is not actually executing.\n\n"
                "Unless you know what you are doing, the automatic play of the animation will "
                "therefore not work. Please call the BiorbdViz.exec() method to be able to play "
                "the animation.\n\nPlease note that the animation slider will work in any case.",
            )
            self.animation_warning_already_shown = True
        if self.is_animating:
            self.is_animating = False
            self.play_stop_push_button.setIcon(self.start_icon)
            self.record_push_button.setEnabled(True)
            self.stop_record_push_button.setEnabled(self.is_recording)
        else:
            self.is_animating = True
            self.play_stop_push_button.setIcon(self.pause_icon)
            self.record_push_button.setEnabled(False)
            self.stop_record_push_button.setEnabled(False)

    def __stop_record(self):
        self.__record(finish=True)

    def __record(self, finish=False):
        file_name = None
        if not self.is_recording:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            file_name = QFileDialog.getSaveFileName(
                self.vtk_window, "Save the video", "", "OGV files (*.ogv)", options=options
            )
            file_name, file_extension = os.path.splitext(file_name[0])
            if file_name == "":
                return
            file_name += ".ogv"

            self.record_push_button.setIcon(self.add_icon)
            self.stop_record_push_button.setEnabled(True)
            self.is_recording = True

        self.vtk_window.record(
            button_to_block=[self.record_push_button, self.stop_record_push_button], finish=finish, file_name=file_name
        )

        if finish:
            self.is_recording = False
            self.record_push_button.setIcon(self.record_icon)
            self.stop_record_push_button.setEnabled(False)

    def __load_movement_from_button(self):
        # Load the actual movement
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name = QFileDialog.getOpenFileName(
            self.vtk_window, "Movement to load", "", "All Files (*)", options=options
        )
        if not file_name[0]:
            return
        if os.path.splitext(file_name[0])[1] == ".Q1":  # If it is from a Matlab reconstruction QLD
            self.animated_Q = scipy.io.loadmat(file_name[0])["Q1"].transpose()
        elif os.path.splitext(file_name[0])[1] == ".Q2":  # If it is from a Matlab reconstruction Kalman
            self.animated_Q = scipy.io.loadmat(file_name[0])["Q2"].transpose()
        else:  # Otherwise assume this is a numpy array
            self.animated_Q = np.load(file_name[0])
        self.__load_movement()

    def load_movement(self, all_q, auto_start=True, ignore_animation_warning=True):
        self.animated_Q = all_q.T
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

        # Add the combobox in muscle analyses
        self.muscle_analyses.add_movement_to_dof_choice()

    def __set_markers_from_q(self):
        self.markers[0:3, :, :] = self.Markers.get_data(Q=self.Q, compute_kin=False)
        self.vtk_model.update_markers(self.markers.isel(time=[0]))

    def __set_global_center_of_mass_from_q(self):
        com = self.CoM.get_data(Q=self.Q, compute_kin=False)
        self.global_center_of_mass.loc[{"channel": 0, "time": 0}] = com.squeeze()
        self.vtk_model.update_global_center_of_mass(self.global_center_of_mass.isel(time=[0]))

    def __set_segments_center_of_mass_from_q(self):
        coms = self.CoMbySegment.get_data(Q=self.Q, compute_kin=False)
        for k, com in enumerate(coms):
            self.segments_center_of_mass.loc[{"channel": k, "time": 0}] = com.squeeze()
        self.vtk_model.update_segments_center_of_mass(self.segments_center_of_mass.isel(time=[0]))

    def __set_meshes_from_q(self):
        for m, meshes in enumerate(self.meshPointsInMatrix.get_data(Q=self.Q, compute_kin=False)):
            self.mesh[m][0:3, :, :] = meshes
        self.vtk_model.update_mesh(self.mesh)

    def __set_muscles_from_q(self):
        muscles = self.musclesPointsInGlobal.get_data(Q=self.Q)

        idx = 0
        cmp = 0
        for group_idx in range(self.model.nbMuscleGroups()):
            for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                musc = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                    self.muscles[idx].loc[{"channel": k, "time": 0}] = np.append(muscles[cmp], 1)
                    cmp += 1
                idx += 1
        self.vtk_model.update_muscle(self.muscles)

    def __set_rt_from_q(self):
        for k, rt in enumerate(self.allGlobalJCS.get_data(Q=self.Q, compute_kin=False)):
            self.rt[k] = Rototrans(rt)
        self.vtk_model.update_rt(self.rt)
