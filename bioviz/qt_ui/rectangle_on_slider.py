from enum import Enum, auto

from PyQt5.QtWidgets import QWidget, QSlider
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter


class RectangleOnSlider(QWidget):
    class Expand(Enum):
        ExpandLeft = auto()
        ExpandRight = auto()
        FixedSize = auto()

    def __init__(self, parent, expand: Expand = Expand.FixedSize, size: int = 10, color=Qt.gray):
        if not isinstance(parent, QSlider):
            raise RuntimeError("RectangleOnSlider must be used on a QSlider")
        self.slider: QSlider = parent

        QWidget.__init__(self)
        self.setParent(self.slider)
        self.expand = expand
        self.size = size
        self.color = color
        self.value = -1
        self.is_selected = False

    def _compute_value_position(self, value):
        n_elements = self.slider.maximum() - self.slider.minimum()
        proportion = value / n_elements
        return proportion * self.slider.width()

    def paintEvent(self, event):
        if self.value < 0:
            return

        paint = QPainter()
        paint.begin(self)
        paint.setPen(Qt.black)
        paint.setBrush(self.color if not self.is_selected else Qt.black)
        paint.setOpacity(0.75)

        position = int(self._compute_value_position(self.value))
        if self.expand == RectangleOnSlider.Expand.ExpandLeft:
            paint.drawRect(0, 0, position, self.slider.height() - 1)
        elif self.expand == RectangleOnSlider.Expand.ExpandRight:
            paint.drawRect(
                position, 0, self.slider.width() - position - 1, self.slider.height() - 1
            )
        elif self.expand == RectangleOnSlider.Expand.FixedSize:
            paint.drawRect(
                int(position - self.size / 2) + 1, 0, self.size, self.slider.height() - 1
            )
        else:
            raise NotImplementedError("Wrong value for expand")

        paint.end()
