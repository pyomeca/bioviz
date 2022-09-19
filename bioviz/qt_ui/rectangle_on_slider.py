from enum import Enum, auto

from PyQt5.QtWidgets import QWidget, QSlider
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter


class RectangleOnSlider(QWidget):
    class Side(Enum):
        Left = auto()
        Right = auto()

    def __init__(self, parent, side: Side = Side.Left):
        if not isinstance(parent, QSlider):
            raise RuntimeError("RectangleOnSlider must be used on a QSlider")
        self.slider: QSlider = parent

        QWidget.__init__(self)
        self.setParent(self.slider)
        self.side = side
        self.value = -1

    def _compute_value_position(self, value):
        n_elements = self.slider.maximum() - self.slider.minimum()
        proportion = value / n_elements
        return proportion * self.slider.width()

    def paintEvent(self, event):
        if self.value == -1:
            return

        paint = QPainter()
        paint.begin(self)
        paint.setPen(Qt.black)
        paint.setBrush(Qt.gray)
        paint.setOpacity(0.75)

        position = int(self._compute_value_position(self.value))
        if self.side == RectangleOnSlider.Side.Left:
            paint.drawRect(0, 0, position, self.slider.height() - 1)
        else:
            paint.drawRect(
                position, 0, self.slider.width() - position - 1, self.slider.height() - 1
            )

        paint.end()
