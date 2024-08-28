from typing import Union, Protocol
import os
import copy
from functools import partial

import numpy as np
import scipy
import xarray as xr
import pandas

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd
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

from .analyses import MuscleAnalyses, C3dEditorAnalyses, LigamentAnalyses
from .interfaces_collection import InterfacesCollections
from .qt_ui.rectangle_on_slider import RectangleOnSlider
from ._version import __version__, check_version

check_version(biorbd, "1.11.1", "2.0.0")
check_version(pyomeca, "2024.0.0", "2024.1.0")


from pyomeca import Markers


class AnalysePanel(Protocol):
    @property
    def widget(self) -> QWidget:
        """
        Return the parent widget in which all was added
        """
        return QWidget()

    def on_activate(self):
        """
        Callback to call when the panel is activated
        """


class Viz:
    def __init__(
        self,
        model_path=None,
        loaded_model=None,
        show_meshes=True,
        mesh_opacity=0.8,
        show_global_center_of_mass=True,
        show_gravity_vector=True,
        show_floor=False,
        show_segments_center_of_mass=True,
        segments_center_of_mass_size=0.005,
        show_global_ref_frame=True,
        show_local_ref_frame=True,
        show_markers=True,
        experimental_markers_color=(1, 1, 1),
        markers_size=0.010,
        show_contacts=True,
        contacts_size=0.010,
        show_soft_contacts=True,
        soft_contacts_color=(0.11, 0.63, 0.95),
        show_muscles=True,
        show_ligaments=True,
        show_wrappings=True,
        show_analyses_panel=True,
        background_color=(0.5, 0.5, 0.5),
        force_wireframe=False,
        experimental_forces_color=(85, 78, 0),
        floor_origin=None,
        floor_normal=None,
        floor_color=(0.7, 0.7, 0.7),
        floor_scale=5,
        **kwargs,
    ):
        """
        Class that easily shows a biorbd model
        Args:
            loaded_model: reference to a biorbd loaded model (if both loaded_model and model_path, load_model is selected
            model_path: path of the model to load
        """

        # Load and store the model
        self.has_model = False
        if loaded_model is not None:
            if not isinstance(loaded_model, biorbd.Model):
                raise TypeError("loaded_model should be of a biorbd.Model type")
            self.model = loaded_model
            self.has_model = True
        elif model_path is not None:
            self.model = biorbd.Model(model_path)
            self.has_model = True
        else:
            self.model = biorbd.Model()
            show_meshes = False
            show_global_center_of_mass = False
            show_segments_center_of_mass = False
            show_local_ref_frame = False
            show_markers = False
            show_contacts = False
            show_muscles = False
            show_ligaments = False
            show_wrappings = False
            show_soft_contacts = False

        # Create the plot
        self.vtk_window = VtkWindow(background_color=background_color)
        self.vtk_markers_size = markers_size

        # soft_contact sphere sizes
        radius = []
        for i in range(self.model.nbSoftContacts()):
            c = self.model.softContact(i)
            if c.typeOfNode() == biorbd.SOFT_CONTACT_SPHERE:
                radius.append(biorbd.SoftContactSphere(self.model.softContact(i)).radius())
        soft_contacts_size = radius

        self.vtk_model = VtkModel(
            self.vtk_window,
            markers_color=(0, 0, 1),
            patch_color=InterfacesCollections.MeshColor.get_color(self.model),
            mesh_opacity=mesh_opacity,
            markers_size=self.vtk_markers_size,
            contacts_size=contacts_size,
            segments_center_of_mass_size=segments_center_of_mass_size,
            force_wireframe=force_wireframe,
            force_color=experimental_forces_color,
            soft_contacts_size=soft_contacts_size,
            soft_contacts_color=soft_contacts_color,
        )
        self.is_executing = False
        self.animation_warning_already_shown = False

        # Set Z vertical
        cam = self.vtk_window.ren.GetActiveCamera()
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(5, 0, 0)
        cam.SetRoll(-90)

        # Get the options
        self.show_markers = show_markers
        self.show_experimental_markers = False
        self.experimental_markers = None
        self.experimental_markers_color = experimental_markers_color
        self.virtual_to_experimental_markers_indices = None
        self.show_experimental_forces = False
        self.experimental_forces = None
        self.segment_forces = []
        self.experimental_forces_color = experimental_forces_color
        self.force_normalization_ratio = None

        self.show_contacts = show_contacts
        self.show_soft_contacts = show_soft_contacts
        self.soft_contacts_color = soft_contacts_color
        self.show_global_ref_frame = show_global_ref_frame
        self.show_floor = show_floor
        self.floor_origin, self.floor_normal = floor_origin, floor_normal
        self.floor_scale = floor_scale
        self.floor_color = floor_color
        self.show_global_center_of_mass = show_global_center_of_mass
        self.show_gravity_vector = show_gravity_vector
        self.show_segments_center_of_mass = show_segments_center_of_mass
        self.show_local_ref_frame = show_local_ref_frame
        self.biorbd_compiled_with_muscles = hasattr(biorbd.Model, "nbMuscles")
        self.biorbd_compiled_with_ligaments = hasattr(biorbd.Model, "nbLigaments")

        if self.biorbd_compiled_with_muscles and self.model.nbMuscles() > 0:
            self.show_muscles = show_muscles
        else:
            self.show_muscles = False
            show_wrappings = False
        if self.biorbd_compiled_with_ligaments and self.model.nbLigaments() > 0:
            self.show_ligaments = show_ligaments
        else:
            self.show_ligaments = False
            show_wrappings = False
        self.show_wrappings = show_wrappings

        if sum([len(i) for i in self.model.meshPoints(np.zeros(self.model.nbQ()))]) > 0:
            self.show_meshes = show_meshes
        else:
            self.show_meshes = 0

        # Create all the reference to the things to plot
        self.nQ = self.model.nbQ()
        self.Q = np.zeros(self.nQ)
        self.idx_markers_to_remove = []
        self.show_segment_is_on = [False] * self.model.nbSegment()
        if self.show_markers:
            self.Markers = InterfacesCollections.Markers(self.model)
            self.markers = Markers(np.ndarray((3, self.model.nbMarkers(), 1)))
        if show_gravity_vector:
            self.Gravity = InterfacesCollections.Gravity(self.model)
        if self.show_contacts:
            self.Contacts = InterfacesCollections.Contact(self.model)
            self.contacts = Markers(np.ndarray((3, self.model.nbContacts(), 1)))
        if self.show_soft_contacts:
            self.SoftContacts = InterfacesCollections.SoftContacts(self.model)
            self.soft_contacts = Markers(np.ndarray((3, self.model.nbSoftContacts(), 1)))
        if self.show_global_center_of_mass:
            self.CoM = InterfacesCollections.CoM(self.model)
            self.global_center_of_mass = Markers(np.ndarray((3, 1, 1)))
        if self.show_segments_center_of_mass:
            self.CoMbySegment = InterfacesCollections.CoMbySegment(self.model)
            self.segments_center_of_mass = Markers(np.ndarray((3, self.model.nbSegment(), 1)))
        if self.show_meshes:
            self.mesh = []
            self.meshPointsInMatrix = InterfacesCollections.MeshPointsInMatrix(self.model)
            for i, vertices in enumerate(self.meshPointsInMatrix.get_data(Q=self.Q, compute_kin=False)):
                triangles = (
                    np.array([p.face() for p in self.model.meshFaces()[i]], dtype="int32")
                    if len(self.model.meshFaces()[i])
                    else np.ndarray((0, 3), dtype="int32")
                )
                self.mesh.append(Mesh(vertex=vertices, triangles=triangles.T))
                self.show_segment_is_on[i] = True
        if self.show_muscles:
            self.model.updateMuscles(self.Q, True)
            self.muscles = []
            for group_idx in range(self.model.nbMuscleGroups()):
                for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                    musc = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                    tp = np.zeros((3, len(musc.position().pointsInGlobal()), 1))
                    self.muscles.append(Mesh(vertex=tp))
            self.musclesPointsInGlobal = InterfacesCollections.MusclesPointsInGlobal(self.model)
        if self.show_ligaments:
            self.model.updateLigaments(self.Q, True)
            self.ligaments = []
            for ligament_idx in range(self.model.nbLigaments()):
                ligament = self.model.ligament(ligament_idx)
                tp = np.zeros((3, len(ligament.position().pointsInGlobal()), 1))
                self.ligaments.append(Mesh(vertex=tp))
            self.ligamentsPointsInGlobal = InterfacesCollections.LigamentsPointsInGlobal(self.model)
        if self.show_local_ref_frame or self.show_global_ref_frame:
            self.rt = []
            self.allGlobalJCS = InterfacesCollections.AllGlobalJCS(self.model)
            for i, rt in enumerate(self.allGlobalJCS.get_data(Q=self.Q, compute_kin=False)):
                self.rt.append(Rototrans(rt))
                self.show_segment_is_on[i] = True

            if self.show_global_ref_frame:
                self.vtk_model.create_global_ref_frame()
        if self.show_wrappings:
            self.wraps_base = []
            self.wraps_current = []
            for m in range(self.model.nbMuscles() + self.model.nbLigaments()):
                if m < self.model.nbMuscles():
                    path_modifier = self.model.muscle(m).pathModifier()
                else:
                    path_modifier = self.model.ligament(m - self.model.nbMuscles()).pathModifier()
                wraps = []
                wraps_current = []
                for w in range(path_modifier.nbWraps()):
                    wrap = path_modifier.object(w)
                    if wrap.typeOfNode() == biorbd.VIA_POINT:
                        continue  # Do not show via points
                    elif wrap.typeOfNode() == biorbd.WRAPPING_HALF_CYLINDER:
                        wrap_cylinder = biorbd.WrappingHalfCylinder(wrap)
                        res = 11  # resolution
                        x = np.sin(np.linspace(0, np.pi, res)) * wrap_cylinder.radius()
                        y = np.cos(np.linspace(0, np.pi, res)) * wrap_cylinder.radius()
                        z = np.ones((res,)) * wrap_cylinder.length()
                        vertices = np.concatenate(
                            [
                                np.array([0, 0, z[0]])[:, np.newaxis],
                                [x, y, z],
                                np.array([0, 0, -z[0]])[:, np.newaxis],
                                [x, y, -z],
                            ],
                            axis=1,
                        )

                        tri_0_0 = np.zeros((res - 1, 1))
                        tri_1_0 = np.arange(1, res)[:, np.newaxis]
                        tri_2_0 = np.arange(2, res + 1)[:, np.newaxis]
                        tri_0 = np.concatenate([tri_0_0, tri_1_0, tri_2_0], axis=1)
                        tri_1 = tri_0 + res + 1
                        tri_2 = np.concatenate([tri_1_0, tri_2_0, tri_1_0 + res + 1], axis=1)
                        tri_3 = np.concatenate([tri_1_0 + res + 1, tri_1_0 + res + 2, tri_2_0], axis=1)
                        tri_4 = np.array([[1, res, res + 2], [res, res + 2, res + res + 1]])
                        triangles = np.array(np.concatenate((tri_0, tri_1, tri_2, tri_3, tri_4)), dtype="int32").T
                    else:
                        raise NotImplementedError("The wrapping object is not implemented in bioviz")
                    wraps.append(Mesh(vertex=vertices[:, :, np.newaxis], triangles=triangles))
                    wraps_current.append(Mesh(vertex=vertices[:, :, np.newaxis], triangles=triangles))
                self.wraps_base.append(wraps)
                self.wraps_current.append(wraps_current)

        self.show_analyses_panel = show_analyses_panel
        if self.show_analyses_panel:
            self.palette_active = QPalette()
            self.palette_inactive = QPalette()
            self.set_viz_palette()
            self.animated_Q = None

            self.play_stop_push_button: QPushButton | None = None
            self.is_animating = False
            self.is_recording = False
            self.start_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/start.png"))
            self.pause_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/pause.png"))
            self.record_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/record.png"))
            self.add_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/add.png"))
            self.stop_icon = QIcon(QPixmap(f"{os.path.dirname(__file__)}/ressources/stop.png"))
            self.record_push_button = None

            self.double_factor = 10000
            self.sliders = list()
            self.movement_slider = []
            self.movement_first_frame = 0
            self.movement_last_frame = -1
            self.movement_slider_starting_shade = None
            self.movement_slider_ending_shade = None

            self.n_max_events = 100
            self.last_event_index = -1
            self.events: list[dict[str:RectangleOnSlider, str:int, str:str]] = []  # events [marker/frame/event_name]

            self.active_analyses: AnalysePanel | None = None
            self.column_stretch = 0
            self.analyses_layout = QHBoxLayout()
            self.analyses_c3d_editor: AnalysePanel | None = None
            self.analyses_muscle: AnalysePanel | None = None
            self.analyses_ligament: AnalysePanel | None = None

            self.c3d_file_name = None
            self.radio_c3d_editor_model: QRadioButton | None = None
            self.add_options_panel()

        # Update everything at the position Q=0
        self.set_q(self.Q)
        if self.show_floor:
            self._set_floor()
        if self.show_gravity_vector:
            self._set_gravity_vector()

    def reset_q(self):
        self.Q = np.zeros(self.Q.shape)
        for slider in self.sliders:
            slider[1].setValue(0)
            slider[2].setText(f"{0:.2f}")
        self.set_q(self.Q)

        # Reset also muscle analyses graphs
        self._update_muscle_analyses_graphs(False, False, False, False)
        # Reset also ligament analyses graphs
        self._update_ligament_analyses_graphs(False, False, False)

    def copy_q_to_clipboard(self):
        pandas.DataFrame(self.Q[np.newaxis, :]).to_clipboard(sep=",", index=False, header=False)

    def set_q(self, Q, refresh_window=True):
        """
        Manually update
        Args:
            Q: np.array
                Generalized coordinate
            refresh_window: bool
                If the window should be refreshed now or not
        """
        if isinstance(Q, (tuple, list)):
            Q = np.array(Q)

        if not isinstance(Q, np.ndarray) and len(Q.shape) > 1 and Q.shape[0] != self.nQ:
            raise TypeError(f"Q should be a {self.nQ} column vector")
        self.Q = Q

        self.model.UpdateKinematicsCustom(self.Q)
        self._set_muscles_from_q()
        self._set_ligaments_from_q()
        self._set_rt_from_q()
        self._set_meshes_from_q()
        self._set_global_center_of_mass_from_q()
        self._set_segments_center_of_mass_from_q()
        self._set_markers_from_q()
        self._set_contacts_from_q()
        self._set_soft_contacts_from_q()
        self._set_wrapping_from_q()

        # Update the sliders
        if self.show_analyses_panel:
            for i, slide in enumerate(self.sliders):
                slide[1].blockSignals(True)
                slide[1].setValue(int(self.Q[i] * self.double_factor))
                slide[1].blockSignals(False)
                slide[2].setText(f"{self.Q[i]:.2f}")

        if refresh_window:
            self.refresh_window()

    def get_camera_position(self) -> tuple:
        return self.vtk_window.get_camera_position()

    def set_camera_position(self, x: float, y: float, z: float):
        self.vtk_window.set_camera_position(x, y, z)
        self.refresh_window()

    def get_camera_roll(self) -> float:
        return self.vtk_window.get_camera_roll()

    def set_camera_roll(self, roll: float):
        self.vtk_window.set_camera_roll(roll)
        self.refresh_window()

    def get_camera_zoom(self) -> float:
        return self.vtk_window.get_camera_zoom()

    def set_camera_zoom(self, zoom: float):
        self.vtk_window.set_camera_zoom(zoom)
        self.refresh_window()

    def get_camera_focus_point(self) -> tuple:
        return self.vtk_window.get_camera_focus_point()

    def set_camera_focus_point(self, x: float, y: float, z: float):
        self.vtk_window.set_camera_focus_point(x, y, z)
        self.refresh_window()

    def toggle_segments(self, idx: Union[int, tuple]):
        # Todo add graphical usage
        if isinstance(idx, int):
            idx = (idx,)
        for i in idx:
            self.show_segment_is_on[i] = not self.show_segment_is_on[i]
        self._set_meshes_from_q()

        # Compute which marker index to remove
        offset_marker = 0
        self.idx_markers_to_remove = []
        for s in range(self.model.nbSegment()):
            nb_markers = self.model.nbMarkers(s)
            if not self.show_segment_is_on[s]:
                self.idx_markers_to_remove += list(range(offset_marker, offset_marker + nb_markers))
            offset_marker += nb_markers
        self._set_markers_from_q()
        self._set_rt_from_q()

    def refresh_window(self):
        """
        Manually refresh the window. One should be aware when manually managing the window, that the plot won't even
        rotate if not refreshed

        """

        self.vtk_window.update_frame()

    def update(self):
        if self.show_analyses_panel and self.is_animating:
            self.movement_slider[0].setValue(self.movement_slider[0].value() + 1)

            if self.movement_slider[0].value() >= self.movement_last_frame:
                self.movement_slider[0].setValue(self.movement_first_frame + 1)

            if self.is_recording:
                self.add_frame()
                if self.movement_slider[0].value() == self.movement_last_frame:
                    self._start_stop_animation()
        self.refresh_window()

    def resize(self, width: int, height: int):
        self.vtk_window.setFixedSize(width, height)

    def exec(self):
        self.is_executing = True
        while self.vtk_window.is_active:
            self.update()
        self.is_executing = False

    def quit(self):
        self.vtk_window.close()

    def maximize(self):
        self.vtk_window.showMaximized()

    def set_viz_palette(self):
        self.palette_active.setColor(QPalette.WindowText, QColor(Qt.black))
        self.palette_active.setColor(QPalette.ButtonText, QColor(Qt.black))

        self.palette_inactive.setColor(QPalette.WindowText, QColor(Qt.gray))

    def add_options_panel(self):
        # Prepare the sliders
        options_layout = QVBoxLayout()
        radio_muscle = None
        radio_ligament = None

        if self.has_model:
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
                slider.setMinimum(int(ranges[i][0] * self.double_factor))
                slider.setMaximum(int(ranges[i][1] * self.double_factor))
                slider.setPageStep(self.double_factor)
                slider.setValue(0)
                slider.valueChanged.connect(self._move_avatar_from_sliders)
                slider.sliderReleased.connect(partial(self._update_ligament_analyses_graphs, False, False, False))
                slider.sliderReleased.connect(partial(self._update_muscle_analyses_graphs, False, False, False, False))
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
            copyq_push_button = QPushButton("Copy Q to clipboard")
            copyq_push_button.setPalette(self.palette_active)
            copyq_push_button.released.connect(self.copy_q_to_clipboard)
            button_layout.addWidget(copyq_push_button)

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
            radio_none.toggled.connect(lambda: self._select_analyses_panel(radio_none, 0))
            radio_none.setText("None")
            option_analyses_layout.addWidget(radio_none)
            # Add the no analyses
            self.radio_c3d_editor_model = QRadioButton()
            self.radio_c3d_editor_model.setPalette(self.palette_active)
            self.radio_c3d_editor_model.setChecked(False)
            self.radio_c3d_editor_model.toggled.connect(
                lambda: self._select_analyses_panel(self.radio_c3d_editor_model, 1)
            )
            self.radio_c3d_editor_model.setText("C3D event editor")
            self.radio_c3d_editor_model.setEnabled(False)
            option_analyses_layout.addWidget(self.radio_c3d_editor_model)
            # Add the muscles analyses
            radio_muscle = QRadioButton()
            radio_muscle.setPalette(self.palette_active)
            radio_muscle.toggled.connect(lambda: self._select_analyses_panel(radio_muscle, 2))
            radio_muscle.setText("Muscles")
            option_analyses_layout.addWidget(radio_muscle)
            # Add the ligaments analyses
            radio_ligament = QRadioButton()
            radio_ligament.setPalette(self.palette_active)
            radio_ligament.toggled.connect(lambda: self._select_analyses_panel(radio_ligament, 3))
            radio_ligament.setText("Ligaments")
            option_analyses_layout.addWidget(radio_ligament)
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

        load_buttons_layout = QVBoxLayout()
        if self.has_model:
            load_push_button = QPushButton("Load movement")
            load_push_button.setPalette(self.palette_active)
            load_push_button.released.connect(self._load_movement_from_button)
            load_buttons_layout.addWidget(load_push_button)

        load_c3d_push_button = QPushButton("Load C3D")
        load_c3d_push_button.setPalette(self.palette_active)
        load_c3d_push_button.released.connect(self._load_experimental_data_from_button)
        load_buttons_layout.addWidget(load_c3d_push_button)

        animation_slider_layout.addLayout(load_buttons_layout)

        # Controllers
        self.play_stop_push_button = QPushButton()
        self.play_stop_push_button.setIcon(self.start_icon)
        self.play_stop_push_button.setPalette(self.palette_active)
        self.play_stop_push_button.setEnabled(False)
        self.play_stop_push_button.released.connect(self._start_stop_animation)
        animation_slider_layout.addWidget(self.play_stop_push_button)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(0)
        slider.setEnabled(False)
        slider.valueChanged.connect(self._animate_from_slider)
        animation_slider_layout.addWidget(slider)

        self.record_push_button = QPushButton()
        self.record_push_button.setIcon(self.record_icon)
        self.record_push_button.setPalette(self.palette_active)
        self.record_push_button.setEnabled(True)
        self.record_push_button.released.connect(self.start_recording)
        animation_slider_layout.addWidget(self.record_push_button)

        self.stop_record_push_button = QPushButton()
        self.stop_record_push_button.setIcon(self.stop_icon)
        self.stop_record_push_button.setPalette(self.palette_active)
        self.stop_record_push_button.setEnabled(False)
        self.stop_record_push_button.released.connect(self.stop_recording)
        animation_slider_layout.addWidget(self.stop_record_push_button)

        # Add the frame count
        frame_label = QLabel()
        frame_label.setText(f"{0}")
        frame_label.setPalette(self.palette_inactive)
        animation_slider_layout.addWidget(frame_label)

        self.movement_slider = (slider, frame_label)
        self.movement_slider_starting_shade = RectangleOnSlider(
            self.movement_slider[0], expand=RectangleOnSlider.Expand.ExpandLeft
        )
        self.movement_slider_ending_shade = RectangleOnSlider(
            self.movement_slider[0], expand=RectangleOnSlider.Expand.ExpandRight
        )

        # We must add all the event markers here because for some reason they are ignored once processEvents is called
        for i in range(self.n_max_events):
            event_marker = RectangleOnSlider(self.movement_slider[0], color=Qt.blue)
            event_marker.value = -1
            event_marker.update()
            self.events.append({"marker": event_marker, "frame": -1, "name": ""})

        # Global placement of the window
        if self.has_model:
            self.vtk_window.main_layout.addLayout(options_layout, 0, 0)
            self.vtk_window.main_layout.addLayout(animation_layout, 0, 1)
            self.vtk_window.main_layout.setColumnStretch(0, 1)
            self.vtk_window.main_layout.setColumnStretch(1, 2)
        else:
            self.vtk_window.main_layout.addLayout(animation_layout, 0, 0)

        # Change the size of the window to account for the new sliders
        self.vtk_window.resize(self.vtk_window.size().width() * 2, self.vtk_window.size().height())

        # Prepare all the analyses panel
        if self.has_model:
            self.analyses_c3d_editor = C3dEditorAnalyses(main_window=self)
            if self.show_muscles:
                self.analyses_muscle = MuscleAnalyses(main_window=self)
            if self.show_ligaments:
                self.analyses_ligament = LigamentAnalyses(main_window=self)
            if biorbd.currentLinearAlgebraBackend() == 1:
                radio_ligament.setEnabled(False)
                radio_muscle.setEnabled(False)
            else:
                radio_ligament.setEnabled(self.biorbd_compiled_with_ligaments and self.model.nbLigaments() > 0)
                radio_muscle.setEnabled(self.biorbd_compiled_with_muscles and self.model.nbMuscles() > 0)
            self._select_analyses_panel(radio_muscle, 0)
            self._select_analyses_panel(radio_ligament, 0)

    def _select_analyses_panel(self, radio_button, panel_to_activate):
        if not radio_button.isChecked():
            return

        # Hide previous analyses panel if necessary
        self._hide_analyses_panel()

        # The bigger the factor is, the bigger the main screen remains
        size_factor_none = 1
        size_c3d_editor_creation = 1.5
        size_factor_muscle = 1.40
        size_factor_ligament = 1.40

        # Find the size factor to get back to normal size
        if self.active_analyses is None:
            reduction_factor = size_factor_none
        elif self.active_analyses == self.analyses_c3d_editor:
            reduction_factor = size_c3d_editor_creation
        elif self.active_analyses == self.analyses_muscle:
            reduction_factor = size_factor_muscle
        elif self.active_analyses == self.analyses_ligament:
            reduction_factor = size_factor_ligament
        else:
            raise RuntimeError("Non-existing panel asked... This should never happen, please report this issue!")

        # Prepare the analyses panel and new size of window
        if panel_to_activate == 0:
            self.active_analyses = None
            enlargement_factor = size_factor_none
            self.column_stretch = 0
        elif panel_to_activate == 1:
            self.active_analyses = self.analyses_c3d_editor
            enlargement_factor = size_c3d_editor_creation
            self.column_stretch = 1
        elif panel_to_activate == 2:
            self.active_analyses = self.analyses_muscle
            self.column_stretch = 4
            enlargement_factor = size_factor_muscle
        elif panel_to_activate == 3:
            self.active_analyses = self.analyses_ligament
            self.column_stretch = 4
            enlargement_factor = size_factor_ligament
        else:
            raise RuntimeError("Non-existing panel asked... This should never happen, please report this issue!")

        # Activate the required panel
        self._show_local_ref_frame()

        # Enlarge the main window
        self.vtk_window.resize(
            int(self.vtk_window.size().width() * enlargement_factor / reduction_factor), self.vtk_window.size().height()
        )

    def _hide_analyses_panel(self):
        if self.active_analyses is None:
            return
        # Remove from main window
        self.active_analyses.widget.setVisible(False)
        self.vtk_window.main_layout.removeWidget(self.active_analyses.widget)
        self.vtk_window.main_layout.setColumnStretch(2, 0)

    def _show_local_ref_frame(self):
        # Give the parent as main window
        if self.active_analyses is not None:
            self.active_analyses.on_activate()
            self.vtk_window.main_layout.addWidget(self.active_analyses.widget, 0, 2)
            self.vtk_window.main_layout.setColumnStretch(2, self.column_stretch)
            self.active_analyses.widget.setVisible(True)

        # Update graphs if needed
        self._update_muscle_analyses_graphs(False, False, False, False)
        self._update_ligament_analyses_graphs(False, False, False)

    def _move_avatar_from_sliders(self):
        for i, slide in enumerate(self.sliders):
            self.Q[i] = slide[1].value() / self.double_factor
            slide[2].setText(f" {self.Q[i]:.2f}")
        self.set_q(self.Q)

    @property
    def n_events(self) -> int:
        return sum([event["frame"] >= 0 for event in self.events])

    def clear_events(self):
        for event in self.events:
            event["frame"] = -1
            event["name"] = ""
            event["marker"].value = -1
            event["marker"].update()
        self.last_event_index = -1

    def select_event(self, index):
        if index is None or index > self.last_event_index:
            index = -1

        for i, event in enumerate(self.events):
            event["marker"].is_selected = i == index
            event["marker"].update()

        self.movement_slider[0].setValue(self.events[index]["frame"] + 1)
        return self.events[index]

    def set_event(self, frame: int, name: str, index: int = None, color: str = None):
        if index is None:
            self.last_event_index += 1
            index = self.last_event_index

        if index > self.last_event_index:
            raise IndexError("list index out of range")

        event = self.events[index]
        event["frame"] = frame
        event["name"] = name
        event["marker"].value = frame
        if color is not None:
            event["marker"].color = color
        event["marker"].update()

    def set_movement_first_frame(self, frame):
        if frame >= self.movement_last_frame:
            frame = self.movement_last_frame

        self.movement_first_frame = frame
        self.movement_slider_starting_shade.value = frame
        self.movement_slider_starting_shade.update()

    def set_movement_last_frame(self, frame):
        if frame <= self.movement_first_frame:
            frame = self.movement_first_frame

        self.movement_last_frame = frame
        self.movement_slider_ending_shade.value = frame
        self.movement_slider_ending_shade.update()

    def _update_muscle_analyses_graphs(
        self, skip_muscle_length, skip_moment_arm, skip_passive_forces, skip_active_forces
    ):
        # Adjust muscle analyses if needed
        if self.active_analyses == self.analyses_muscle:
            if self.analyses_muscle is not None:
                self.analyses_muscle.update_all_graphs(
                    skip_muscle_length, skip_moment_arm, skip_passive_forces, skip_active_forces
                )

    def _update_ligament_analyses_graphs(self, skip_ligament_length, skip_moment_arm, skip_passive_forces):
        # Adjust ligament analyses if needed
        if self.active_analyses == self.analyses_ligament:
            if self.analyses_ligament is not None:
                self.analyses_ligament.update_all_graphs(skip_ligament_length, skip_moment_arm, skip_passive_forces)

    def _animate_from_slider(self):
        # Move the avatar
        self.movement_slider[1].setText(f"{self.movement_slider[0].value()}")
        if self.animated_Q is not None:
            t_slider = self.movement_slider[0].value() - 1
            t = t_slider if t_slider < self.animated_Q.shape[0] else self.animated_Q.shape[0] - 1
            self.Q = copy.copy(self.animated_Q[t, :])  # 1-based
            self.set_q(self.Q, refresh_window=False)

        self._set_experimental_markers_from_frame()
        self._set_experimental_forces_from_frame()

        # Update graph of muscle analyses
        self._update_muscle_analyses_graphs(True, True, True, True)
        # Update graph of ligament analyses
        self._update_ligament_analyses_graphs(True, True, True)

        # Refresh the window
        self.refresh_window()

    def _start_stop_animation(self):
        if not self.is_executing and not self.animation_warning_already_shown:
            QMessageBox.warning(
                self.vtk_window,
                "Not executing",
                "bioviz has detected that it is not actually executing.\n\n"
                "Unless you know what you are doing, the automatic play of the animation will "
                "therefore not work. Please call the bioviz.exec() method to be able to play "
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

    def snapshot(self, save_path: str):
        # Todo Add a button
        file_name, extension = os.path.splitext(save_path)
        if not extension:
            extension = ".png"
        if extension != ".png":
            raise NotImplementedError("The only snapshot format implemented is PNG")
        self.vtk_window.snapshot(file_name + extension)

    def stop_recording(self):
        self._record(finish=True)

    def start_recording(self, save_path: str = None):
        self._record(finish=False, file_name=save_path)

    def add_frame(self):
        if not self.is_recording:
            raise ValueError("add_frame must be called after 'start_recording'")

        self._record(finish=False)

    def _record(self, finish, file_name: str = None):
        if not self.is_recording:
            if file_name is None:
                options = QFileDialog.Options()
                options |= QFileDialog.DontUseNativeDialog
                file_name = QFileDialog.getSaveFileName(
                    self.vtk_window, "Save the video", "", "OGV files (*.ogv)", options=options
                )[0]

            file_name, file_extension = os.path.splitext(file_name)
            if file_name == "":
                return
            if file_extension and file_extension != ".ogv":
                raise ValueError("The only supported format for video is .ogv")
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

    def _load_movement_from_button(self):
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
            self.animated_Q = np.load(file_name[0]).T
        self._load_movement()

    def load_movement(self, all_q, auto_start=True, ignore_animation_warning=True):
        self.animated_Q = all_q.T
        self._load_movement()
        if ignore_animation_warning:
            self.animation_warning_already_shown = True
        if auto_start:
            self._start_stop_animation()

    def _load_movement(self):
        self._set_movement_slider()

        # Add the combobox in muscle analyses
        if self.show_muscles:
            self.analyses_muscle.add_movement_to_dof_choice()
        # Add the combobox in ligament analyses
        if self.show_ligaments:
            self.analyses_ligament.add_movement_to_dof_choice()

    def _set_movement_slider(self):
        # Activate the start button
        self.is_animating = False
        self.play_stop_push_button.setEnabled(True)
        self.play_stop_push_button.setIcon(self.start_icon)

        # Update the slider bar and frame count
        self.movement_slider[0].setEnabled(True)
        experiment_shape = 0
        if self.experimental_forces is not None:
            experiment_shape = self.experimental_forces.shape[2]
        if self.experimental_markers is not None:
            experiment_shape = max(self.experimental_markers.shape[2], experiment_shape)

        q_shape = 0 if self.animated_Q is None else self.animated_Q.shape[0]
        self.movement_first_frame = 0
        self.movement_last_frame = max(q_shape, experiment_shape)
        self.movement_slider[0].setMinimum(1)
        self.movement_slider[0].setMaximum(self.movement_last_frame)
        pal = QPalette()
        pal.setColor(QPalette.WindowText, QColor(Qt.black))
        self.movement_slider[1].setPalette(pal)

        # Put back to first frame
        self.movement_slider[0].setValue(1)

    def _load_experimental_data_from_button(self):
        # Load the actual movement
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name = QFileDialog.getOpenFileName(self.vtk_window, "Data to load", "", "C3D (*.c3d)", options=options)
        if not file_name[0]:
            return
        self.load_experimental_markers(file_name[0])

    def load_c3d(self, data, auto_start=True, ignore_animation_warning=True):
        self.load_experimental_markers(data, auto_start, ignore_animation_warning)

    def load_experimental_markers(
        self,
        data,
        auto_start=True,
        ignore_animation_warning=True,
        experimental_markers_mapping_to_virtual: list[int] = None,
    ):
        if isinstance(data, str):
            self.experimental_markers = Markers.from_c3d(data)
            if self.experimental_markers.units == "mm":
                self.experimental_markers = self.experimental_markers * 0.001

            # Try to find a correspondence between the loaded experimental markers and the model
            self.virtual_to_experimental_markers_indices = experimental_markers_mapping_to_virtual
            if self.virtual_to_experimental_markers_indices is None:
                try:
                    virtual_marker_names = [n.to_string() for n in self.model.markerNames()]
                    exp_marker_names = list(self.experimental_markers.channel.data)
                    self.virtual_to_experimental_markers_indices = [
                        virtual_marker_names.index(name) if name in virtual_marker_names else None
                        for name in exp_marker_names
                    ]
                except ValueError:
                    # Did not find direct correspondence
                    pass

            self.c3d_file_name = data
            self.radio_c3d_editor_model.setEnabled(True)

        elif isinstance(data, (np.ndarray, xr.DataArray)):
            self.experimental_markers = Markers(data)

        else:
            raise RuntimeError(
                f"Wrong type of experimental markers data ({type(data)}). "
                f"Allowed type are numpy array (3xNxT), data array (3xNxT) or .c3d file (str)."
            )

        self._set_movement_slider()
        self.show_experimental_markers = True

        if ignore_animation_warning:
            self.animation_warning_already_shown = True
        if auto_start:
            self._start_stop_animation()

    def load_experimental_forces(
        self, data, segments=None, normalization_ratio=0.2, auto_start=True, ignore_animation_warning=True
    ):
        if isinstance(data, (np.ndarray, xr.DataArray)):
            self.experimental_forces = data if isinstance(data, xr.DataArray) else xr.DataArray(data)
        else:
            raise RuntimeError(
                f"Wrong type of experimental force data ({type(data)}). "
                f"Allowed type are numpy array (SxNxT), data array (SxNxT)."
            )

        if segments:
            self.segment_forces = segments if isinstance(segments, (list, np.ndarray)) else [segments]
        else:
            self.segment_forces = ["ground"] * self.experimental_forces.shape[0]

        if len(self.segment_forces) != self.experimental_forces.shape[0]:
            raise RuntimeError(
                "Number of segment must match number of experimental  forces. "
                f"You have {len(segments)} and {self.experimental_forces.shape[0]}."
            )

        self.force_normalization_ratio = normalization_ratio

        self.show_experimental_forces = True
        self._set_movement_slider()

        if ignore_animation_warning:
            self.animation_warning_already_shown = True
        if auto_start:
            self._start_stop_animation()

    def _set_markers_from_q(self):
        if not self.show_markers:
            return

        self.markers[0:3, :, :] = self.Markers.get_data(Q=self.Q, compute_kin=False)
        if self.idx_markers_to_remove:
            self.markers[0:3, self.idx_markers_to_remove, :] = np.nan
        self.vtk_model.update_markers(self.markers.isel(time=[0]))

    def _set_experimental_markers_from_frame(self):
        if not self.show_experimental_markers:
            return

        t_slider = self.movement_slider[0].value() - 1
        t = t_slider if t_slider < self.experimental_markers.shape[2] else self.experimental_markers.shape[2] - 1
        self.vtk_model.update_experimental_markers(
            self.experimental_markers[:, :, t : t + 1].isel(time=[0]),
            with_link=True,
            virtual_to_experimental_markers_indices=self.virtual_to_experimental_markers_indices,
        )

    def _set_experimental_forces_from_frame(self):
        if not self.show_experimental_forces:
            return

        segment_names = []
        for i in range(self.model.nbSegment()):
            segment_names.append(self.model.segment(i).name().to_string())
        global_jcs = self.allGlobalJCS.get_data(Q=self.Q, compute_kin=False)
        segment_jcs = []

        for segment in self.segment_forces:
            if isinstance(segment, str):
                if segment == "ground":
                    segment_jcs.append(np.identity(4))
                else:
                    segment_jcs.append(global_jcs[segment_names.index(segment)])
            elif isinstance(segment, (float, int)):
                segment_jcs.append(global_jcs[segment])
            else:
                raise RuntimeError("Wrong type of segment.")

        max_forces = []
        for i, forces in enumerate(self.experimental_forces):
            max_forces.append(
                max(
                    np.sqrt(
                        (forces[3, :] - forces[0, :]) ** 2
                        + (forces[4, :] - forces[1, :]) ** 2
                        + (forces[5, :] - forces[2, :]) ** 2
                    )
                )
            )

        t_slider = self.movement_slider[0].value() - 1
        t = t_slider if t_slider < self.experimental_forces.shape[2] else self.experimental_forces.shape[2] - 1
        self.vtk_model.update_force(
            segment_jcs, self.experimental_forces[:, :, t : t + 1], max_forces, self.force_normalization_ratio
        )

    def _set_contacts_from_q(self):
        if not self.show_contacts:
            return

        self.contacts[0:3, :, :] = self.Contacts.get_data(Q=self.Q, compute_kin=False)
        self.vtk_model.update_contacts(self.contacts.isel(time=[0]))

    def _set_soft_contacts_from_q(self):
        if not self.show_soft_contacts:
            return

        self.soft_contacts[0:3, :, :] = self.SoftContacts.get_data(Q=self.Q, compute_kin=False)
        self.vtk_model.update_soft_contacts(self.soft_contacts.isel(time=[0]))

    def _set_global_center_of_mass_from_q(self):
        if not self.show_global_center_of_mass:
            return

        com = self.CoM.get_data(Q=self.Q, compute_kin=False)
        self.global_center_of_mass.loc[{"channel": 0, "time": 0}] = com.squeeze()
        self.vtk_model.update_global_center_of_mass(self.global_center_of_mass.isel(time=[0]))

    def _set_gravity_vector(self):
        if not self.show_gravity_vector:
            return

        start = [0, 0, 0]
        magnitude = self.Gravity.get_data()
        gravity = np.concatenate((start, magnitude))
        length = np.linalg.norm(gravity)
        id_matrix = np.identity(4)
        self.vtk_model.new_gravity_vector(id_matrix, gravity, length, normalization_ratio=0.3, vector_color=(0, 0, 0))

    def _set_floor(self):
        if not self.show_floor:
            return

        origin = self.floor_origin if self.floor_origin else (0, 0, 0)
        normal = self.floor_normal if self.floor_normal else self.Gravity.get_data()
        scale = self.floor_scale
        scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
        self.vtk_model.new_floor(origin=origin, normal=normal, color=self.floor_color, scale=scale)

    def _set_segments_center_of_mass_from_q(self):
        if not self.show_segments_center_of_mass:
            return

        coms = self.CoMbySegment.get_data(Q=self.Q, compute_kin=False)
        for k, com in enumerate(coms):
            self.segments_center_of_mass.loc[{"channel": k, "time": 0}] = com.squeeze()
        self.vtk_model.update_segments_center_of_mass(self.segments_center_of_mass.isel(time=[0]))

    def _set_meshes_from_q(self):
        if not self.show_meshes:
            return

        for m, meshes in enumerate(self.meshPointsInMatrix.get_data(Q=self.Q, compute_kin=False)):
            if self.show_segment_is_on[m]:
                self.mesh[m][0:3, :, :] = meshes
            else:
                self.mesh[m][0:3, :, :] = np.nan
        self.vtk_model.update_mesh(self.mesh)

    def _set_muscles_from_q(self):
        if not self.show_muscles:
            return

        muscles = self.musclesPointsInGlobal.get_data(Q=self.Q)
        idx = 0
        cmp = 0
        for group_idx in range(self.model.nbMuscleGroups()):
            for muscle_idx in range(self.model.muscleGroup(group_idx).nbMuscles()):
                musc = self.model.muscleGroup(group_idx).muscle(muscle_idx)
                for k, pts in enumerate(musc.position().pointsInGlobal()):
                    self.muscles[idx].loc[{"channel": k, "time": 0}] = np.append(muscles[cmp], 1)
                    cmp += 1
                idx += 1
        self.vtk_model.update_muscle(self.muscles)

    def _set_ligaments_from_q(self):
        if not self.show_ligaments:
            return

        ligaments = self.ligamentsPointsInGlobal.get_data(Q=self.Q)
        cmp = 0
        for idx in range(self.model.nbLigaments()):
            for k, pts in enumerate(self.model.ligament(idx).position().pointsInGlobal()):
                self.ligaments[idx].loc[{"channel": k, "time": 0}] = np.append(ligaments[cmp], 1)
                cmp += 1

        self.vtk_model.update_ligament(self.ligaments)

    def _set_wrapping_from_q(self):
        if not self.show_wrappings:
            return

        for i, wraps in enumerate(self.wraps_base):
            for j, wrap in enumerate(wraps):
                if i < self.model.nbMuscles():
                    if self.model.muscle(i).pathModifier().object(j).typeOfNode() == biorbd.WRAPPING_HALF_CYLINDER:
                        rt = (
                            biorbd.WrappingHalfCylinder(self.model.muscle(i).pathModifier().object(j))
                            .RT(self.model, self.Q)
                            .to_array()
                        )
                        self.wraps_current[i][j][0:3, :, 0] = np.dot(rt, wrap[:, :, 0])[0:3, :]
                    else:
                        raise NotImplementedError("_set_wrapping_from_q is not ready for these wrapping object")

                else:
                    if self.model.ligaments(i).pathModifier().object(j).typeOfNode() == biorbd.WRAPPING_HALF_CYLINDER:
                        rt = (
                            biorbd.WrappingHalfCylinder(self.model.ligaments(i).pathModifier().object(j))
                            .RT(self.model, self.Q)
                            .to_array()
                        )
                        self.wraps_current[i][j][0:3, :, 0] = np.dot(rt, wrap[:, :, 0])[0:3, :]
                    else:
                        raise NotImplementedError("_set_wrapping_from_q is not ready for these wrapping object")
        self.vtk_model.update_wrapping(self.wraps_current)

    def _set_rt_from_q(self):
        if not self.show_local_ref_frame:
            return

        for k, rt in enumerate(self.allGlobalJCS.get_data(Q=self.Q, compute_kin=False)):
            if self.show_segment_is_on[k]:
                self.rt[k] = Rototrans(rt)
            else:
                self.rt[k] = Rototrans(np.eye(4)) * np.nan
        self.vtk_model.update_rt(self.rt)


class Kinogram(Viz):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        """
        Creates a kinogram of the movement loaded
        """
        super(Kinogram, self).__init__(*args, **kwargs)
        self.list_animated_Q = None

    def stop_recording(self):
        raise RuntimeError("To use start_recoding, please use bioviz.Viz")

    def start_recording(self, save_path: str = None):
        raise RuntimeError("To use stop_recoding, please use bioviz.Viz")

    def load_movement(self, all_q, auto_start=True, ignore_animation_warning=True):
        if type(all_q) == list:
            self.list_animated_Q = [q.T for q in all_q]
        else:
            self.list_animated_Q = [all_q.T]

    def exec(self, frame_step: int | tuple | list = 5, figsize: tuple | None = None, save_path: str = "kinogram"):
        """
        Creates the kinogram and save it
        """
        # Cannot import elsewhere because of VTK
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg

        if not save_path.endswith(".png") and not save_path.endswith(".svg"):
            save_path += ".svg"

        if figsize is None:
            figsize = (5 * len(self.list_animated_Q), 5)

        if type(frame_step) == int:
            frame_step = [frame_step for _ in range(len(self.list_animated_Q))]

        self.maximize()
        fig, ax = plt.subplots(1, len(self.list_animated_Q), figsize=figsize)
        fig.subplots_adjust(hspace=0, wspace=0)
        for i_phase in range(len(self.list_animated_Q)):
            self.animated_Q = self.list_animated_Q[i_phase]
            self._load_movement()

            # Taking snapshot
            Q_this_time = self.list_animated_Q[i_phase]
            n_shooting_this_time = Q_this_time.shape[0]
            snap_idx = list(range(0, n_shooting_this_time, frame_step[i_phase]))
            nb_images = len(snap_idx)
            for i_snap, snap in enumerate(snap_idx):
                self.movement_slider[0].setValue(snap)
                snap_save_path_this_time = f"{save_path[:-4]}_snapshot-{snap}.png"
                self.snapshot(snap_save_path_this_time)
                self.refresh_window()
                img = mpimg.imread(snap_save_path_this_time)
                img = np.concatenate((img, np.ones((img.shape[0], img.shape[1], 1))), axis=2)

                # Remove background to transparent
                for pixel_y in range(img.shape[0]):
                    for pixel_x in range(img.shape[1]):
                        if np.all(img[pixel_y, pixel_x, :3] == 1):
                            img[pixel_y, pixel_x, 3] = 0

                alpha = 1 / nb_images * (i_snap + 1)
                ax[i_phase].imshow(img, alpha=alpha)

            ax[i_phase].axis("off")
            ax[i_phase].set_frame_on(False)

        plt.savefig(save_path, bbox_inches="tight")
        plt.show()

        return
