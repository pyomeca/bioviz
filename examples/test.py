from pathlib import Path

import numpy as np

from pyosim import Analogs3dOsim

DATA_PATH = Path('/home/romain/Downloads/results/mars/1_inverse_kinematic')

x = [Analogs3dOsim().from_mot(i).time_normalization() for i in DATA_PATH.glob('*.mot')]

data = np.stack(x).squeeze()

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

app = QtGui.QApplication([])
view = pg.GraphicsView()
l = pg.GraphicsLayout(border=(100, 100, 100))
view.setCentralItem(l)
view.show()
view.setWindowTitle('pyqtgraph example: GraphicsLayout')
view.resize(1200, 700)

# import pyqtgraph.examples
# pyqtgraph.examples.run()


## Title at top
text = """
This example demonstrates the use of GraphicsLayout to arrange items in a grid.<br>
The items added to the layout must be subclasses of QGraphicsWidget (this includes <br>
PlotItem, ViewBox, LabelItem, and GrphicsLayout itself).
"""
l.addLabel(text, row=1, col=1, colspan=2)
# l.nextRow()

p1 = l.addPlot(title="Plot", row=2, col=1, colspan=3)
p1.addLegend()
for icol in range(data.shape[1]):
    # for itrial in range(data.shape[0]):
    #     p1.plot(data[itrial, icol, :])
    #
    #
    mu = data[:, icol, :].mean(axis=0)
    std = data[:, icol, :].std(axis=0)

    curves = [
        p1.plot(mu - std, pen=(icol, data.shape[1])),
        p1.plot(mu, pen=(icol, data.shape[1])),
        p1.plot(mu + std, pen=(icol, data.shape[1])),
    ]

    p1.addItem(pg.FillBetweenItem(curves[0], curves[1], brush=(200, 200, 255)))
    p1.addItem(pg.FillBetweenItem(curves[1], curves[2], brush=(icol, data.shape[1])))





p1.setXRange(-8, 100)
p2 = l.addPlot(title="Plot 2", row=2, col=4, colspan=1)
# p2.plot([1, 3, 2, 4, 3, 5])


if __name__ == '__main__':
    import sys

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
