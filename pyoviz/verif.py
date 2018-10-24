from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PyQt5 import QtWidgets

from pyosim import Analogs3dOsim


class Verification(QtWidgets.QMainWindow):

    def __init__(self, list_of_analogs: list):
        # TODO:
        # select indexes
        # export to csv
        # style
        self.list_of_analogs = list_of_analogs
        self.analogs_columns = list(range(list_of_analogs[0].shape[1]))

        # init gui
        app = QtWidgets.QApplication([])
        super().__init__()
        self.init_layout()
        self.init_window()

        app.exec()

    # --- Init methods

    def init_window(self):
        self.setWindowTitle(f"Pyoviz's verification GUI")
        self.resize(1200, 700)
        self.show()

    def init_layout(self):
        self.central_widget = QtWidgets.QWidget(self)
        self.grid_layout = QtWidgets.QGridLayout(self.central_widget)

        # gui's elements
        self.init_lists()

        self.setCentralWidget(self.central_widget)

    def init_lists(self):
        # TODO
        self.current_list = QtWidgets.QListWidget(self.central_widget)
        self.current_list.setStyleSheet('font-size: 16pt')
        self.grid_layout.addWidget(self.current_list, 5, 0, 1, 1)


if __name__ == '__main__':
    DATA_PATH = Path('/home/romain/Downloads/results/mars/1_inverse_kinematic')

    x = [Analogs3dOsim().from_mot(i).time_normalization() for i in DATA_PATH.glob('*.mot')]

    data = np.stack(x).squeeze()

    for i in range(data.shape[0]):
        plt.plot(data[i, ...].T)

    plt.legend(x[0].get_2d_labels())
    plt.show()

    # Verification(list_of_analogs=x)

    #####

    import pyqtgraph as pg
    from pyqtgraph.Qt import QtGui, QtCore

    plt = pg.plot()
    plt.setWindowTitle('pyqtgraph example: Legend')
    plt.addLegend(offset=(90, 90))

    # for itrial in range(data.shape[0]):
    #     plt.plot(data[itrial, 0, :], pen=(itrial, data.shape[0]))

    # brushes = [0.5, (100, 100, 255), 0.5]

    for icol in range(data.shape[1]):
        mu = data[:, icol, :].mean(axis=0)
        plt.plot(mu, pen=(icol, data.shape[1]), name=icol)


    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


