import time

import numpy as np
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QComboBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt

import biorbd


class MuscleAnalyses:
    def __init__(self, parent, model, active_palette, inactive_palette, background_color=(.5, .5, .5)):
        # Centralize the materials
        analyses_muscle_layout = QHBoxLayout(parent)

        # Get some aliases
        self.model = model
        self.n_mus = self.model.nbMuscleTotal()
        self.n_q = self.model.nbQ()

        # Add muscle selector
        selector_layout = QVBoxLayout()
        combo_muscle = QComboBox()
        combo_muscle.setPalette(active_palette)
        self.muscle_mapping = dict()
        cmp_mus = 0
        for group in range(model.nbMuscleGroups()):
            for mus in range(model.muscleGroup(group).nbMuscles()):
                name = biorbd.s2mMuscleHillType.getRef(model.muscleGroup(group).muscle(mus)).name()
                combo_muscle.addItem(name)
                self.muscle_mapping[name] = (group, mus)
                cmp_mus += 1
        selector_layout.addWidget(combo_muscle)

        # Add dof selector
        combo_dof = QComboBox()
        combo_dof.setPalette(active_palette)
        self.dof_mapping = dict()
        for cmp_dof, name in enumerate(model.nameDof()):
            combo_dof.addItem(name)
            self.dof_mapping[name] = cmp_dof
        selector_layout.addWidget(combo_dof)

        combo_muscle.currentIndexChanged.connect(lambda: self.__plot_muscle_length(combo_dof, combo_muscle))
        combo_dof.currentIndexChanged.connect(lambda: self.__plot_muscle_length(combo_dof, combo_muscle))
        analyses_muscle_layout.addLayout(selector_layout)

        # Add plots
        analyses_layout = QGridLayout()
        self.canvas = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas, 0, 0)
        analyses_muscle_layout.addLayout(analyses_layout)

        # Add muscle length plot
        self.ax_muscle_length = self.canvas.figure.subplots()
        self.ax_muscle_length.set_facecolor(background_color)
        self.ax_muscle_length.set_title("Muscle length over q")
        self.ax_muscle_length.set_ylabel("Muscle length (m)")
        self.ax_muscle_length.plot(np.nan, np.nan, 'w')

    def __plot_muscle_length(self, combo_dof, combo_muscle):
        q_idx = self.dof_mapping[combo_dof.currentText()]
        mus_group_idx, mus_idx = self.muscle_mapping[combo_muscle.currentText()]
        q, length = self.__get_muscle_lengths(q_idx, mus_group_idx, mus_idx)
        self.ax_muscle_length.get_lines()[0].set_data(q, length)
        self.ax_muscle_length.autoscale(True)
        self.canvas.figure.canvas.draw()

        # Adjust axis label
        self.ax_muscle_length.set_xlabel(self.model.nameDof()[q_idx] + " (rad)")

    def __get_muscle_lengths(self, q_idx, mus_group_idx, mus_idx):
        n_points = 100
        length = np.ndarray((n_points))
        q = np.linspace(-np.pi, np.pi, n_points)
        q_actual = np.zeros(self.n_q)
        for i, q_mod in enumerate(q):
            q_actual[q_idx] = q_mod
            length[i] = biorbd.s2mMuscleHillType.getRef(
                self.model.muscleGroup(mus_group_idx).muscle(mus_idx)).length(self.model, q_actual)
        return q, length
