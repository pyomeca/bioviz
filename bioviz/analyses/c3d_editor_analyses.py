from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QCheckBox

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd


class C3dEditorAnalyses:
    def __init__(self, parent, main_window, background_color=(0.5, 0.5, 0.5)):
        # Centralize the materials
        main_layout = QHBoxLayout(parent)

        # Get some aliases
        self.main_window = main_window

        selector_layout = QVBoxLayout()
        main_layout.addLayout(selector_layout)
        animation_checkbox = QCheckBox()
        selector_layout.addWidget(animation_checkbox)
        animation_checkbox.setText("From animation")
