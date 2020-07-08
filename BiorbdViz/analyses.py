from functools import partial
from copy import copy

import numpy as np
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QScrollArea,
    QLabel,
    QSlider,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt

import biorbd


class MuscleAnalyses:
    def __init__(self, parent, main_window, background_color=(0.5, 0.5, 0.5)):
        # Centralize the materials
        analyses_muscle_layout = QHBoxLayout(parent)

        # Get some aliases
        self.main_window = main_window
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
        self.animation_checkbox.stateChanged.connect(partial(self.update_all_graphs, False, False, False, False))

        # Add plots
        analyses_layout = QGridLayout()
        analyses_muscle_layout.addLayout(analyses_layout)
        self.n_point_for_q = 50

        # Add muscle length plot
        self.canvas_muscle_length = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_muscle_length, 0, 0)
        self.ax_muscle_length = self.canvas_muscle_length.figure.subplots()
        self.ax_muscle_length.set_facecolor(background_color)
        self.ax_muscle_length.set_title("Muscle length")
        self.ax_muscle_length.set_ylabel("Length (m)")

        # Add moment arm plot
        self.canvas_moment_arm = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_moment_arm, 0, 1)
        self.ax_moment_arm = self.canvas_moment_arm.figure.subplots()
        self.ax_moment_arm.set_facecolor(background_color)
        self.ax_moment_arm.set_title("Moment arm")
        self.ax_moment_arm.set_ylabel("Moment arm (m)")

        # Add passive forces
        self.canvas_passive_forces = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_passive_forces, 1, 0)
        self.ax_passive_forces = self.canvas_passive_forces.figure.subplots()
        self.ax_passive_forces.set_facecolor(background_color)
        self.ax_passive_forces.set_title("Passive forces")
        self.ax_passive_forces.set_ylabel("Passive forces coeff")

        # Add active forces
        self.canvas_active_forces = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        active_forces_layout = QHBoxLayout()
        analyses_layout.addLayout(active_forces_layout, 1, 1)
        active_forces_layout.addWidget(self.canvas_active_forces)
        self.ax_active_forces = self.canvas_active_forces.figure.subplots()
        self.ax_active_forces.set_facecolor(background_color)
        self.ax_active_forces.set_title("Active forces")
        self.ax_active_forces.set_ylabel("Active forces coeff")
        self.active_forces_slider = QSlider()
        active_forces_layout.addWidget(self.active_forces_slider)
        self.active_forces_slider.setPalette(self.main_window.palette_active)
        self.active_forces_slider.setMinimum(0)
        self.active_forces_slider.setMaximum(100)
        self.active_forces_slider.valueChanged.connect(partial(self.update_all_graphs, True, True, True, False))

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
                self.checkboxes_muscle[cmp_mus].toggled.connect(
                    partial(self.update_all_graphs, False, False, False, False)
                )
                muscle_layout.addWidget(self.checkboxes_muscle[cmp_mus])

                # Add the plot to the axes
                self.ax_muscle_length.plot(np.nan, np.nan, "w")
                self.ax_moment_arm.plot(np.nan, np.nan, "w")
                self.ax_passive_forces.plot(np.nan, np.nan, "w")
                self.ax_active_forces.plot(np.nan, np.nan, "w")
                cmp_mus += 1

        # Add vertical bar for position of current dof
        self.ax_muscle_length.plot(np.nan, np.nan, "k")
        self.ax_moment_arm.plot(np.nan, np.nan, "k")
        self.ax_passive_forces.plot(np.nan, np.nan, "k")
        self.ax_active_forces.plot(np.nan, np.nan, "k")

        radio_muscle_group.setLayout(muscle_layout)
        muscles_scroll = QScrollArea()
        muscles_scroll.setFrameShape(0)
        muscles_scroll.setWidgetResizable(True)
        muscles_scroll.setWidget(radio_muscle_group)
        selector_layout.addWidget(muscles_scroll)
        selector_layout.addStretch()

    def add_movement_to_dof_choice(self):
        self.animation_checkbox.setPalette(self.main_window.palette_active)
        self.animation_checkbox.setEnabled(True)
        self.n_point_for_q = self.main_window.animated_Q.shape[0]

    def __set_current_dof(self):
        self.current_dof = self.combobox_dof.currentText()
        self.update_all_graphs(False, False, False, False)

    def update_all_graphs(self, skip_muscle_length, skip_moment_arm, skip_passive_forces, skip_active_forces):
        x_axis, length, moment_arm, passive_forces, active_forces = self.__compute_all_values()
        self.__update_specific_plot(
            self.canvas_muscle_length, self.ax_muscle_length, x_axis, length, skip_muscle_length
        )

        self.__update_specific_plot(self.canvas_moment_arm, self.ax_moment_arm, x_axis, moment_arm, skip_moment_arm)

        self.__update_specific_plot(
            self.canvas_passive_forces, self.ax_passive_forces, x_axis, passive_forces, skip_passive_forces
        )

        self.__update_specific_plot(
            self.canvas_active_forces, self.ax_active_forces, x_axis, active_forces, skip_active_forces
        )

        self.__update_graph_size()

    def __update_graph_size(self):
        self.ax_muscle_length.figure.tight_layout()
        self.ax_moment_arm.figure.tight_layout()
        self.ax_passive_forces.figure.tight_layout()
        self.ax_active_forces.figure.tight_layout()

        self.canvas_muscle_length.draw()
        self.canvas_moment_arm.draw()
        self.canvas_passive_forces.draw()
        self.canvas_active_forces.draw()

    def __compute_all_values(self):
        q_idx = self.dof_mapping[self.current_dof]
        x_axis, all_q = self.__generate_x_axis(q_idx)
        length = np.ndarray((self.n_point_for_q, self.n_mus))
        moment_arm = np.ndarray((self.n_point_for_q, self.n_mus))
        passive_forces = np.ndarray((self.n_point_for_q, self.n_mus))
        active_forces = np.ndarray((self.n_point_for_q, self.n_mus))
        emg = biorbd.State(0, self.active_forces_slider.value() / 100)
        for i, q_mod in enumerate(all_q):
            self.model.UpdateKinematicsCustom(biorbd.GeneralizedCoordinates(q_mod))
            muscles_length_jacobian = self.model.musclesLengthJacobian().to_array()
            for m in range(self.n_mus):
                if self.checkboxes_muscle[m].isChecked():
                    mus_group_idx, mus_idx, _ = self.muscle_mapping[self.checkboxes_muscle[m].text()]
                    mus = self.model.muscleGroup(mus_group_idx).muscle(mus_idx)
                    mus.updateOrientations(self.model, q_mod, 1)

                    length[i, m] = mus.length(self.model, q_mod, False)
                    moment_arm[i, m] = muscles_length_jacobian[mus_idx, q_idx]
                    if mus.type() != biorbd.IDEALIZED_ACTUATOR:
                        passive_forces[i, m] = biorbd.HillType(mus).FlPE()
                    else:
                        passive_forces[i, m] = 0
                    if mus.type() != biorbd.IDEALIZED_ACTUATOR:
                        active_forces[i, m] = biorbd.HillType(mus).FlCE(emg)
                    else:
                        active_forces[i, m] = 0

        return x_axis, length, moment_arm, passive_forces, active_forces

    def __update_specific_plot(self, canvas, ax, x, y, skip=False):
        # Plot all active muscles
        number_of_active = 0
        for m in range(self.n_mus):
            if self.checkboxes_muscle[m].isChecked():
                if not skip:
                    ax.get_lines()[m].set_data(x, y[:, m])
                number_of_active += 1
            else:
                ax.get_lines()[m].set_data(np.nan, np.nan)

        # Empty the vertical bar (otherwise relim takes it in account
        ax.get_lines()[-1].set_data(np.nan, np.nan)

        # If there is no data skip relim and vertical bar adjustment
        if number_of_active != 0:
            # relim so the plot looks nice
            ax.relim()
            ax.autoscale(enable=True)

            # Adjust axis label (give a generic name)
            if self.animation_checkbox.isChecked():
                ax.set_xlabel("Time frame")
            else:
                ax.set_xlabel("Along range")

            # Add vertical bar to show current dof (it must be done after relim so we know the new lims)
            q_idx = self.combobox_dof.currentIndex()
            if self.animation_checkbox.isChecked():
                x = int(self.main_window.movement_slider[1].text())  # Frame label
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
