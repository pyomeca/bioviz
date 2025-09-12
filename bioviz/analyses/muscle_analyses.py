from enum import Enum
from functools import partial
from copy import copy
from typing import Any

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QFrame,
    QScrollArea,
    QLabel,
    QWidget,
    QSlider,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd


class _AnalysesTypes(Enum):
    MUSCLE_LENGTH = 1
    MOMENT_ARM = 2
    PASSIVE_FORCES_COEFF = 3
    ACTIVE_FORCES_COEFF = 4
    FORCE = 5

    def name(self):
        if self == _AnalysesTypes.MUSCLE_LENGTH:
            return "Muscle length"
        elif self == _AnalysesTypes.MOMENT_ARM:
            return "Moment arm"
        elif self == _AnalysesTypes.PASSIVE_FORCES_COEFF:
            return "Passive forces coeff"
        elif self == _AnalysesTypes.ACTIVE_FORCES_COEFF:
            return "Active forces coeff"
        elif self == _AnalysesTypes.FORCE:
            return "Force"
        else:
            raise ValueError("Unknown analysis type")

    def y_label(self):
        if self == _AnalysesTypes.MUSCLE_LENGTH:
            return "Length (m)"
        elif self == _AnalysesTypes.MOMENT_ARM:
            return "Moment arm (m)"
        elif self == _AnalysesTypes.PASSIVE_FORCES_COEFF:
            return "Passive forces coeff"
        elif self == _AnalysesTypes.ACTIVE_FORCES_COEFF:
            return "Active forces coeff"
        elif self == _AnalysesTypes.FORCE:
            return "Force (N)"
        else:
            raise ValueError("Unknown analysis type")

    def y_lim(self):
        if self in (_AnalysesTypes.PASSIVE_FORCES_COEFF, _AnalysesTypes.ACTIVE_FORCES_COEFF):
            return (0, 1)
        else:
            return None


class MuscleAnalyses:
    def __init__(self, main_window, parent: QWidget = None, background_color=(0.5, 0.5, 0.5)):
        # Centralize the materials
        self.widget = parent if parent is not None else QWidget()
        analyses_muscle_layout = QHBoxLayout(self.widget)

        # Get some aliases
        self.main_window = main_window
        self._background_color = background_color
        self.model = self.main_window.model
        self.n_mus = self.model.nbMuscles()
        self.n_q = self.model.nbQ()

        # Add dof selector
        selector_layout = QVBoxLayout()
        analyses_muscle_layout.addLayout(selector_layout)
        text_dof = QLabel()
        text_dof.setText("DoF to run")
        text_dof.setPalette(self.main_window.palette_active)
        selector_layout.addWidget(text_dof)

        self.combobox_dof = QComboBox()
        selector_layout.addWidget(self.combobox_dof)
        self.combobox_dof.setPalette(self.main_window.palette_active)
        self.dof_mapping = dict()
        for cmp_dof, name in enumerate(self.model.nameDof()):
            self.combobox_dof.addItem(name.to_string())
            self.dof_mapping[name.to_string()] = cmp_dof
        self.combobox_dof.currentIndexChanged.connect(self.__set_current_dof)
        # Set default value
        self.current_dof = self.combobox_dof.currentText()

        # Add the possibility to select from movement
        self.animation_checkbox = QCheckBox()
        selector_layout.addWidget(self.animation_checkbox)
        self.animation_checkbox.setText("From animation")
        self.animation_checkbox.setPalette(self.main_window.palette_inactive)
        self.animation_checkbox.setEnabled(False)
        self.animation_checkbox.stateChanged.connect(partial(self.update_all_graphs, update_only=None))

        # Add plots
        analyses_layout = QGridLayout()
        analyses_muscle_layout.addLayout(analyses_layout)
        self.n_point_for_q = 50

        # Add muscle length plot
        self.plot_canvases: list[tuple[FigureCanvasQTAgg, Any, _AnalysesTypes]] = []
        for i in range(4):
            analyse_type = _AnalysesTypes(i + 1)

            v_box_layout = QVBoxLayout()
            analyses_layout.addLayout(v_box_layout, i // 2, i % 2)

            analyses_selector = QComboBox()
            analyses_selector.setPalette(self.main_window.palette_active)
            for e in _AnalysesTypes:
                analyses_selector.addItem(e.name())
            analyses_selector.setCurrentIndex(i)
            analyses_selector.currentIndexChanged.connect(partial(self._change_analysis_type, i, analyses_selector))
            v_box_layout.addWidget(analyses_selector, alignment=Qt.AlignmentFlag.AlignHCenter)

            h_box_layout = QHBoxLayout()
            v_box_layout.addLayout(h_box_layout)

            canvas = FigureCanvasQTAgg(plt.figure(facecolor=self._background_color))
            h_box_layout.addWidget(canvas)
            ax = canvas.figure.subplots()
            self._update_graph_type(ax, analyse_type)

            if i == 3:
                self.activation_slider = QSlider()
                h_box_layout.addWidget(self.activation_slider)
                self.activation_slider.setPalette(self.main_window.palette_active)
                self.activation_slider.setMinimum(0)
                self.activation_slider.setMaximum(100)
                self.activation_slider.valueChanged.connect(
                    partial(
                        self.update_all_graphs,
                        update_only=[_AnalysesTypes.ACTIVE_FORCES_COEFF, _AnalysesTypes.FORCE],
                    )
                )
                self.activation_slider.setVisible(True)

            self.plot_canvases.append((canvas, ax, analyse_type))

        # Add muscle selector
        radio_muscle_group = QGroupBox()
        muscle_layout = QVBoxLayout()
        self.muscle_mapping = dict()
        self.checkboxes_muscle = list()
        cmp_mus = 0
        for group in range(self.model.nbMuscleGroups()):
            for mus in range(self.model.muscleGroup(group).nbMuscles()):
                # Map the name to the right numbers
                name = self.model.muscleGroup(group).muscle(mus).name().to_string()
                self.muscle_mapping[name] = (group, mus, cmp_mus)

                # Add the CheckBox
                self.checkboxes_muscle.append(QCheckBox())
                self.checkboxes_muscle[cmp_mus].setPalette(self.main_window.palette_active)
                self.checkboxes_muscle[cmp_mus].setText(name)
                self.checkboxes_muscle[cmp_mus].toggled.connect(partial(self.update_all_graphs, update_only=None))
                muscle_layout.addWidget(self.checkboxes_muscle[cmp_mus])

                # Add the plot to the axes
                for _, ax, _ in self.plot_canvases:
                    ax.plot(np.nan, np.nan, "w")
                cmp_mus += 1

        # Add vertical bar for position of current dof
        for _, ax, _ in self.plot_canvases:
            ax.plot(np.nan, np.nan, "k")

        radio_muscle_group.setLayout(muscle_layout)
        muscles_scroll = QScrollArea()
        muscles_scroll.setFrameShape(QFrame.Shape.NoFrame)
        muscles_scroll.setWidgetResizable(True)
        muscles_scroll.setWidget(radio_muscle_group)
        selector_layout.addWidget(muscles_scroll)
        selector_layout.addStretch()

    def on_activate(self):
        pass

    def add_movement_to_dof_choice(self):
        self.animation_checkbox.setPalette(self.main_window.palette_active)
        self.animation_checkbox.setEnabled(True)
        self.n_point_for_q = self.main_window.animated_Q.shape[0]

    def __set_current_dof(self):
        self.current_dof = self.combobox_dof.currentText()
        self.update_all_graphs()

    def _change_analysis_type(self, index: int, combo_box: QComboBox):
        analyse_type = _AnalysesTypes(combo_box.currentIndex() + 1)
        canvas, ax, _ = self.plot_canvases[index]
        self.plot_canvases[index] = (canvas, ax, analyse_type)
        self._update_graph_type(ax, analyse_type)
        self.update_all_graphs(update_only=[analyse_type])

    def _update_graph_type(self, ax, analyse_type: _AnalysesTypes):
        ax.set_facecolor(self._background_color)
        ax.set_ylabel(analyse_type.y_label())
        if analyse_type.y_lim() is not None:
            ax.set_ylim(analyse_type.y_lim())

    def update_all_graphs(self, update_only: list[_AnalysesTypes] = None):
        x_axis, all_values = self.__compute_all_values()
        for canvas, ax, analyse_type in self.plot_canvases:
            if update_only is None or analyse_type in update_only:
                self.__update_specific_plot(canvas, ax, analyse_type, x_axis, all_values[analyse_type])
        self.__update_graph_size()

    def __update_graph_size(self):
        for _, ax, _ in self.plot_canvases:
            ax.figure.tight_layout()

        for canvas, _, _ in self.plot_canvases:
            canvas.draw()

    def __compute_all_values(self) -> tuple[np.ndarray, dict[_AnalysesTypes, np.ndarray]]:
        q_idx = self.dof_mapping[self.current_dof]
        x_axis, all_q = self.__generate_x_axis(q_idx)
        length = np.full((self.n_point_for_q, self.n_mus), np.nan)
        moment_arm = np.full((self.n_point_for_q, self.n_mus), np.nan)
        passive_forces = np.full((self.n_point_for_q, self.n_mus), np.nan)
        active_forces = np.full((self.n_point_for_q, self.n_mus), np.nan)
        emg = biorbd.State(0, self.activation_slider.value() / 100)
        forces = np.full((self.n_point_for_q, self.n_mus), np.nan)
        states = self.model.stateSet()
        for state in states:
            state.setActivation(self.activation_slider.value() / 100)

        for i, q_mod in enumerate(all_q):
            self.model.updateMuscles(biorbd.GeneralizedCoordinates(q_mod), True)
            muscle_forces = self.model.muscleForces(states, q_mod, np.zeros(self.model.nbQdot())).to_array()
            for m in range(self.n_mus):
                if self.checkboxes_muscle[m].isChecked():
                    mus_group_idx, mus_idx, cmp_mus = self.muscle_mapping[self.checkboxes_muscle[m].text()]
                    mus = self.model.muscleGroup(mus_group_idx).muscle(mus_idx)
                    muscles_length_jacobian = self.model.musclesLengthJacobian().to_array()

                    length[i, m] = mus.length(self.model, q_mod, False)
                    moment_arm[i, m] = -1 * muscles_length_jacobian[cmp_mus, q_idx]
                    if mus.type() != biorbd.IDEALIZED_ACTUATOR:
                        passive_forces[i, m] = biorbd.HillType(mus).FlPE()
                    else:
                        passive_forces[i, m] = 0
                    if mus.type() != biorbd.IDEALIZED_ACTUATOR:
                        active_forces[i, m] = biorbd.HillType(mus).FlCE(emg)
                    else:
                        active_forces[i, m] = emg.activation()
                    forces[i, m] = muscle_forces[m]

        return x_axis, {
            _AnalysesTypes.MUSCLE_LENGTH: length,
            _AnalysesTypes.MOMENT_ARM: moment_arm,
            _AnalysesTypes.PASSIVE_FORCES_COEFF: passive_forces,
            _AnalysesTypes.ACTIVE_FORCES_COEFF: active_forces,
            _AnalysesTypes.FORCE: forces,
        }

    def __update_specific_plot(self, canvas, ax, analyse_type: _AnalysesTypes, x, y, skip=False, autoscale_y=True):
        # Plot all active muscles
        number_of_active = 0
        for m in range(self.n_mus):
            if self.checkboxes_muscle[m].isChecked():
                if not skip:
                    ax.get_lines()[m].set_data(x, y[:, m])
                number_of_active += 1
            else:
                ax.get_lines()[m].set_data([], [])

        # Empty the vertical bar (otherwise relim takes it in account
        ax.get_lines()[-1].set_data([], [])

        # If there is no data skip relim and vertical bar adjustment
        if number_of_active != 0:
            # relim so the plot looks nice
            y_lim = None
            if analyse_type.y_lim():
                y_lim = analyse_type.y_lim()
            elif not autoscale_y:
                y_lim = ax.get_ylim()
            ax.relim()
            ax.autoscale(enable=True)
            if y_lim is not None:
                ax.set_ylim(y_lim)

            # Adjust axis label (give a generic name)
            if self.animation_checkbox.isChecked():
                ax.set_xlabel("Time frame")
            else:
                ax.set_xlabel("Along range")

            # Add vertical bar to show current dof (it must be done after relim so we know the new lims)
            q_idx = self.combobox_dof.currentIndex()
            if self.animation_checkbox.isChecked():
                x = int(self.main_window.movement_slider[1].text()) - 1  # Frame label
            else:
                x = self.__get_q_from_slider()[q_idx]
            ax.get_lines()[-1].set_data([x, x], ax.get_ylim())

        # Redraw graphs
        canvas.draw()

    def __get_q_from_slider(self):
        return copy(self.main_window.Q)

    def __generate_x_axis(self, q_idx):
        if self.animation_checkbox.isChecked():
            q = self.main_window.animated_Q
            x = np.arange(q.shape[0])
        else:
            q = np.tile(self.__get_q_from_slider(), (self.n_point_for_q, 1))
            slider = self.main_window.sliders[self.combobox_dof.currentIndex()][1]
            q[:, q_idx] = np.linspace(
                slider.minimum() / self.main_window.double_factor,
                slider.maximum() / self.main_window.double_factor,
                self.n_point_for_q,
            )
            x = q[:, q_idx]
        return x, q
