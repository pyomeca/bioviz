from functools import partial
from copy import copy

import numpy as np
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QGroupBox, QCheckBox, QComboBox, QScrollArea, \
    QLabel, QSlider
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt

import biorbd


class MuscleAnalyses:
    def __init__(self, parent, main_window, background_color=(.5, .5, .5)):
        # Centralize the materials
        analyses_muscle_layout = QHBoxLayout(parent)

        # Get some aliases
        self.main_window = main_window
        self.model = self.main_window.model
        self.n_mus = self.model.nbMuscleTotal()
        self.n_q = self.model.nbQ()

        # Add dof selector
        selector_layout = QVBoxLayout()
        analyses_muscle_layout.addLayout(selector_layout)
        text_dof = QLabel()
        text_dof.setText("DoF to run")
        text_dof.setPalette(self.main_window.palette_active)
        selector_layout.addWidget(text_dof)

        self.combobox_dof = QComboBox()
        self.combobox_dof.setPalette(self.main_window.palette_active)
        self.dof_mapping = dict()
        for cmp_dof, name in enumerate(self.model.nameDof()):
            self.combobox_dof.addItem(name)
            self.dof_mapping[name] = cmp_dof
        selector_layout.addWidget(self.combobox_dof)
        self.combobox_dof.currentIndexChanged.connect(self.__set_current_dof)
        # Set default value
        self.current_dof = self.combobox_dof.currentText()

        # Add plots
        analyses_layout = QGridLayout()
        analyses_muscle_layout.addLayout(analyses_layout)

        # Add muscle length plot
        self.canvas_muscle_length = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_muscle_length, 0, 0)
        self.ax_muscle_length = self.canvas_muscle_length.figure.subplots()
        self.ax_muscle_length.set_facecolor(background_color)
        self.ax_muscle_length.set_title("Muscle length along range of q")
        self.ax_muscle_length.set_ylabel("Muscle length (m)")

        # Add moment arm plot
        self.canvas_moment_arm = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_moment_arm, 0, 1)
        self.ax_moment_arm = self.canvas_moment_arm.figure.subplots()
        self.ax_moment_arm.set_facecolor(background_color)
        self.ax_moment_arm.set_title("Moment arm along range of q")
        self.ax_moment_arm.set_ylabel("Muscle moment arm (m)")

        # Add passive forces
        self.canvas_passive_forces = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_passive_forces, 1, 0)
        self.ax_passive_forces = self.canvas_passive_forces.figure.subplots()
        self.ax_passive_forces.set_facecolor(background_color)
        self.ax_passive_forces.set_title("Passive forces along range of q")
        self.ax_passive_forces.set_ylabel("Passive forces coefficient")

        # Add active forces
        self.canvas_active_forces = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        active_forces_layout = QHBoxLayout()
        analyses_layout.addLayout(active_forces_layout, 1, 1)
        active_forces_layout.addWidget(self.canvas_active_forces)
        self.ax_active_forces = self.canvas_active_forces.figure.subplots()
        self.ax_active_forces.set_facecolor(background_color)
        self.ax_active_forces.set_title("Active forces along range of q")
        self.ax_active_forces.set_ylabel("Active forces coefficient")
        self.active_forces_slider = QSlider()
        active_forces_layout.addWidget(self.active_forces_slider)
        self.active_forces_slider.setPalette(self.main_window.palette_active)
        self.active_forces_slider.setMinimum(0)
        self.active_forces_slider.setMaximum(100)
        self.active_forces_slider.valueChanged.connect(partial(self.__select_muscles_on_plot, True))

        # Add muscle selector
        text_muscle = QLabel()
        text_muscle.setText("Muscles to show")
        text_muscle.setPalette(self.main_window.palette_active)
        selector_layout.addWidget(text_muscle)

        radio_muscle_group = QGroupBox()
        muscle_layout = QVBoxLayout()
        self.muscle_mapping = dict()
        self.checkboxes_muscle = list()
        cmp_mus = 0
        for group in range(self.model.nbMuscleGroups()):
            for mus in range(self.model.muscleGroup(group).nbMuscles()):
                # Map the name to the right numbers
                name = biorbd.s2mMuscleHillType.getRef(self.model.muscleGroup(group).muscle(mus)).name()
                self.muscle_mapping[name] = (group, mus, cmp_mus)

                # Add the CheckBox
                self.checkboxes_muscle .append(QCheckBox())
                self.checkboxes_muscle[cmp_mus].setPalette(self.main_window.palette_active)
                self.checkboxes_muscle[cmp_mus].setText(name)
                self.checkboxes_muscle[cmp_mus].toggled.connect(partial(self.__select_muscles_on_plot, False))
                muscle_layout.addWidget(self.checkboxes_muscle[cmp_mus])

                # Add the plot to the axes
                self.ax_muscle_length.plot(np.nan, np.nan, 'w')
                self.ax_moment_arm.plot(np.nan, np.nan, 'w')
                self.ax_passive_forces.plot(np.nan, np.nan, 'w')
                self.ax_active_forces.plot(np.nan, np.nan, 'w')
                cmp_mus += 1

        # Add vertical bar for position of current dof
        self.ax_muscle_length.plot(np.nan, np.nan, 'k')
        self.ax_moment_arm.plot(np.nan, np.nan, 'k')
        self.ax_passive_forces.plot(np.nan, np.nan, 'k')
        self.ax_active_forces.plot(np.nan, np.nan, 'k')

        radio_muscle_group.setLayout(muscle_layout)
        muscles_scroll = QScrollArea()
        muscles_scroll.setFrameShape(0)
        muscles_scroll.setWidgetResizable(True)
        muscles_scroll.setWidget(radio_muscle_group)
        selector_layout.addWidget(muscles_scroll)
        selector_layout.addStretch()

    def __set_current_dof(self):
        self.current_dof = self.combobox_dof.currentText()
        self.__select_muscles_on_plot(False)

    def update_all_graphs(self):
        self.__select_muscles_on_plot(False)

    def __select_muscles_on_plot(self, from_active_forces_slider):
        q_idx = self.dof_mapping[self.current_dof]
        # Plot all active muscles
        number_of_active = 0
        for ax_idx, checkbox in enumerate(self.checkboxes_muscle):
            if checkbox.isChecked():
                mus_group_idx, mus_idx_in_group, mus_idx = self.muscle_mapping[checkbox.text()]

                # Muscle length
                if not from_active_forces_slider:
                    q, length = self.__get_muscle_lengths(q_idx, mus_group_idx, mus_idx_in_group)
                    self.ax_muscle_length.get_lines()[ax_idx].set_data(q, length)

                    # Moment arm
                    q, jacobian = self.__get_moment_arms(q_idx, mus_idx)
                    self.ax_moment_arm.get_lines()[ax_idx].set_data(q, jacobian)

                    # Passive forces
                    q, passive_forces = self.__get_passive_forces(q_idx, mus_group_idx, mus_idx_in_group)
                    self.ax_passive_forces.get_lines()[ax_idx].set_data(q, passive_forces)

                # Active forces
                q, active_forces = self.__get_active_forces(q_idx, mus_group_idx, mus_idx_in_group)
                self.ax_active_forces.get_lines()[ax_idx].set_data(q, active_forces)

                number_of_active += 1
            else:
                self.ax_muscle_length.get_lines()[ax_idx].set_data(np.nan, np.nan)
                self.ax_moment_arm.get_lines()[ax_idx].set_data(np.nan, np.nan)
                self.ax_passive_forces.get_lines()[ax_idx].set_data(np.nan, np.nan)
                self.ax_active_forces.get_lines()[ax_idx].set_data(np.nan, np.nan)

        # Empty the vertical bar (otherwise relim takes it in account
        if not from_active_forces_slider:
            self.ax_muscle_length.get_lines()[-1].set_data(np.nan, np.nan)
            self.ax_moment_arm.get_lines()[-1].set_data(np.nan, np.nan)
            self.ax_passive_forces.get_lines()[-1].set_data(np.nan, np.nan)
        self.ax_active_forces.get_lines()[-1].set_data(np.nan, np.nan)

        # If there is no data to show
        if number_of_active == 0:
            # Redraw empty
            self.canvas_muscle_length.figure.canvas.draw()
            self.canvas_moment_arm.figure.canvas.draw()
            self.canvas_passive_forces.figure.canvas.draw()
            self.canvas_active_forces.figure.canvas.draw()
            return

        if not from_active_forces_slider:
            self.ax_muscle_length.relim()
            self.ax_muscle_length.autoscale(enable=True)
            self.ax_moment_arm.relim()
            self.ax_moment_arm.autoscale(enable=True)
            self.ax_passive_forces.relim()
            self.ax_passive_forces.autoscale(enable=True)
        self.ax_active_forces.relim()
        self.ax_active_forces.autoscale(enable=True)

        # Adjust axis label
        if not from_active_forces_slider:
            self.ax_muscle_length.set_xlabel(self.model.nameDof()[q_idx] + " (rad) along full range")
            self.ax_moment_arm.set_xlabel(self.model.nameDof()[q_idx] + " (rad) along full range")
            self.ax_passive_forces.set_xlabel(self.model.nameDof()[q_idx] + " (rad) along full range")
        self.ax_active_forces.set_xlabel(self.model.nameDof()[q_idx] + " (rad) along full range")

        # Add vertical bar to show current dof (it must be done after relim so we know the new lims
        q_idx = self.combobox_dof.currentIndex()
        q_val = self.__get_q_from_slider()[q_idx]
        if not from_active_forces_slider:
            self.ax_muscle_length.get_lines()[-1].set_data([q_val, q_val], self.ax_muscle_length.get_ylim())
            self.ax_moment_arm.get_lines()[-1].set_data([q_val, q_val], self.ax_moment_arm.get_ylim())
            self.ax_passive_forces.get_lines()[-1].set_data([q_val, q_val], self.ax_passive_forces.get_ylim())
        self.ax_active_forces.get_lines()[-1].set_data([q_val, q_val], self.ax_active_forces.get_ylim())

        # Redraw graphs
        if not from_active_forces_slider:
            self.canvas_muscle_length.figure.canvas.draw()
            self.canvas_moment_arm.figure.canvas.draw()
            self.canvas_passive_forces.figure.canvas.draw()
        self.canvas_active_forces.figure.canvas.draw()

    def __get_q_from_slider(self):
        return copy(self.main_window.Q)

    def __get_muscle_lengths(self, q_idx, mus_group_idx, mus_idx):
        n_points = 100
        length = np.ndarray((n_points))
        q = np.linspace(-np.pi, np.pi, n_points)
        q_current = self.__get_q_from_slider()
        for i, q_mod in enumerate(q):
            q_current[q_idx] = q_mod
            length[i] = biorbd.s2mMuscleHillType.getRef(
                self.model.muscleGroup(mus_group_idx).muscle(mus_idx))\
                .length(self.model, q_current)
        return q, length

    def __get_moment_arms(self, q_idx, mus_idx):
        n_points = 100
        moment_arm = np.ndarray((n_points))
        q = np.linspace(-np.pi, np.pi, n_points)
        q_current = self.__get_q_from_slider()
        for i, q_mod in enumerate(q):
            q_current[q_idx] = q_mod
            moment_arm[i] = self.model.musclesLengthJacobian(self.model, q_current).get_array()[mus_idx, q_idx]
        return q, moment_arm

    def __get_passive_forces(self, q_idx, mus_group_idx, mus_idx):
        n_points = 100
        passive_forces = np.ndarray((n_points))
        q = np.linspace(-np.pi, np.pi, n_points)
        q_current = self.__get_q_from_slider()
        mus = biorbd.s2mMuscleHillType.getRef(self.model.muscleGroup(mus_group_idx).muscle(mus_idx))
        for i, q_mod in enumerate(q):
            q_current[q_idx] = q_mod
            mus.updateOrientations(self.model, q_current)
            passive_forces[i] = mus.FlPE()
        return q, passive_forces

    def __get_active_forces(self, q_idx, mus_group_idx, mus_idx):
        n_points = 100
        active_forces = np.ndarray((n_points))
        q = np.linspace(-np.pi, np.pi, n_points)
        q_current = self.__get_q_from_slider()
        mus = biorbd.s2mMuscleHillType.getRef(self.model.muscleGroup(mus_group_idx).muscle(mus_idx))
        emg = biorbd.s2mMuscleStateActual(0, self.active_forces_slider.value()/100)
        for i, q_mod in enumerate(q):
            q_current[q_idx] = q_mod
            mus.updateOrientations(self.model, q_current)
            active_forces[i] = mus.FlCE(emg)
        return q, active_forces
