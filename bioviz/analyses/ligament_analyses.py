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
    QWidget,
    QSlider,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import pyplot as plt

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd


class LigamentAnalyses:
    def __init__(self, main_window, parent: QWidget = None, background_color=(0.5, 0.5, 0.5)):
        # Centralize the materials
        self.widget = parent if parent is not None else QWidget()
        analyses_ligament_layout = QHBoxLayout(self.widget)

        # Get some aliases
        self.main_window = main_window
        self.model = self.main_window.model
        self.n_lig = self.model.nbLigaments()
        self.n_q = self.model.nbQ()

        # Add dof selector
        selector_layout = QVBoxLayout()
        analyses_ligament_layout.addLayout(selector_layout)
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
        self.animation_checkbox.stateChanged.connect(partial(self.update_all_graphs, False, False, False))

        # Add plots
        analyses_layout = QGridLayout()
        analyses_ligament_layout.addLayout(analyses_layout)
        self.n_point_for_q = 50

        # Add ligament length plot
        self.canvas_ligament_length = FigureCanvasQTAgg(plt.figure(facecolor=background_color))
        analyses_layout.addWidget(self.canvas_ligament_length, 0, 0)
        self.ax_ligament_length = self.canvas_ligament_length.figure.subplots()
        self.ax_ligament_length.set_facecolor(background_color)
        self.ax_ligament_length.set_title("Ligament length")
        self.ax_ligament_length.set_ylabel("Length (m)")

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
        self.ax_passive_forces.set_ylabel("Forces")

        # Add ligament selector
        radio_ligament = QGroupBox()
        ligament_layout = QVBoxLayout()
        self.ligament_mapping = dict()
        self.checkboxes_ligament = list()
        for l in range(self.model.nbLigaments()):
            name = self.model.ligament(l).name().to_string()
            # Add the CheckBox
            self.checkboxes_ligament.append(QCheckBox())
            self.checkboxes_ligament[l].setPalette(self.main_window.palette_active)
            self.checkboxes_ligament[l].setText(name)
            self.checkboxes_ligament[l].toggled.connect(
                partial(self.update_all_graphs, False, False, False)
            )
            ligament_layout.addWidget(self.checkboxes_ligament[l])

            # Add the plot to the axes
            self.ax_ligament_length.plot(np.nan, np.nan, "w")
            self.ax_moment_arm.plot(np.nan, np.nan, "w")
            self.ax_passive_forces.plot(np.nan, np.nan, "w")

        # Add vertical bar for position of current dof
        self.ax_ligament_length.plot(np.nan, np.nan, "k")
        self.ax_moment_arm.plot(np.nan, np.nan, "k")
        self.ax_passive_forces.plot(np.nan, np.nan, "k")

        radio_ligament.setLayout(ligament_layout)
        ligaments_scroll = QScrollArea()
        ligaments_scroll.setFrameShape(0)
        ligaments_scroll.setWidgetResizable(True)
        ligaments_scroll.setWidget(radio_ligament)
        selector_layout.addWidget(ligaments_scroll)
        selector_layout.addStretch()

    def on_activate(self):
        pass

    def add_movement_to_dof_choice(self):
        self.animation_checkbox.setPalette(self.main_window.palette_active)
        self.animation_checkbox.setEnabled(True)
        self.n_point_for_q = self.main_window.animated_Q.shape[0]

    def __set_current_dof(self):
        self.current_dof = self.combobox_dof.currentText()
        self.update_all_graphs(False, False, False)

    def update_all_graphs(self, skip_ligament_length, skip_moment_arm, skip_passive_forces):
        x_axis, length, moment_arm, passive_forces = self.__compute_all_values()
        self.__update_specific_plot(
            self.canvas_ligament_length, self.ax_ligament_length, x_axis, length, skip_ligament_length
        )

        self.__update_specific_plot(self.canvas_moment_arm, self.ax_moment_arm, x_axis, moment_arm, skip_moment_arm)

        self.__update_specific_plot(
            self.canvas_passive_forces, self.ax_passive_forces, x_axis, passive_forces, skip_passive_forces
        )

        self.__update_graph_size()

    def __update_graph_size(self):
        self.ax_ligament_length.figure.tight_layout()
        self.ax_moment_arm.figure.tight_layout()
        self.ax_passive_forces.figure.tight_layout()

        self.canvas_ligament_length.draw()
        self.canvas_moment_arm.draw()
        self.canvas_passive_forces.draw()

    def __compute_all_values(self):
        q_idx = self.dof_mapping[self.current_dof]
        x_axis, all_q = self.__generate_x_axis(q_idx)
        length = np.ndarray((self.n_point_for_q, self.n_lig))
        moment_arm = np.ndarray((self.n_point_for_q, self.n_lig))
        passive_forces = np.ndarray((self.n_point_for_q, self.n_lig))
        for i, q_mod in enumerate(all_q):
            self.model.UpdateKinematicsCustom(biorbd.GeneralizedCoordinates(q_mod))
            for l in range(self.model.nbLigaments()):
                if self.checkboxes_ligament[l].isChecked():
                    lig = self.model.ligament(l)
                    lig.updateOrientations(self.model, q_mod, 1)
                    ligaments_length_jacobian = self.model.ligamentsLengthJacobian().to_array()

                    length[i, l] = lig.length(self.model, q_mod, False)
                    moment_arm[i, l] = -1 * ligaments_length_jacobian[l, q_idx]
                    passive_forces[i, l] = lig.Fl()

        return x_axis, length, moment_arm, passive_forces

    def __update_specific_plot(self, canvas, ax, x, y, skip=False):
        # Plot all active muscles
        number_of_active = 0
        for m in range(self.n_lig):
            if self.checkboxes_ligament[m].isChecked():
                if not skip:
                    ax.get_lines()[m].set_data(x, y[:, m])
                number_of_active += 1
            else:
                ax.get_lines()[m].set_data(np.nan, np.nan)

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
