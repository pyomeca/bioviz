import json
import os
from typing import Callable

from PyQt5.QtWidgets import QBoxLayout, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QInputDialog, QWidget
from PyQt5.QtCore import Qt

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd


class C3dEditorAnalyses:
    def __init__(self, parent, main_window):
        # Get some aliases
        self.main_window = main_window
        self.event_save_path = "bioviz_events.json"
        self.n_events_max = 6

        # Centralize the materials
        main_layout = QVBoxLayout(parent)
        main_layout.setAlignment(Qt.AlignCenter)

        # Set time trial
        time_set_layout = QVBoxLayout()
        self.add_subtitle("Time setter", time_set_layout)
        time_set_button_layout = QHBoxLayout()
        self.add_button("Set Start", layout=time_set_button_layout, callback=lambda _: self._set_time(0))
        self.add_button("Set End", layout=time_set_button_layout, callback=lambda _: self._set_time(1))
        time_set_layout.addLayout(time_set_button_layout)

        # Events
        events_layout = QVBoxLayout()
        self.add_subtitle("Events setter", events_layout)
        button = self.add_button(
            "ADD EVENT", events_layout, callback=lambda button: self._create_event_button(button, events_layout)
        )
        self._read_events(button, events_layout)

        # Add export button
        export_layout = QHBoxLayout()
        self.add_button("Export C3D", layout=export_layout, callback=lambda _: self._export_c3d())

        main_layout.addStretch()
        main_layout.addLayout(time_set_layout)
        main_layout.addStretch()
        main_layout.addLayout(events_layout)
        main_layout.addStretch()
        main_layout.addLayout(export_layout)
        main_layout.addStretch()
        # main_layout.setStretch(0, 1)
        # main_layout.setStretch(1, 4)
        # main_layout.setStretch(2, 1)

    def add_subtitle(self, title, layout: QBoxLayout) -> None:
        head_layout = QHBoxLayout()
        head_layout.setAlignment(Qt.AlignCenter)
        self.add_text(title, layout=head_layout)
        layout.addLayout(head_layout)

    def add_text(self, label: str, layout: QBoxLayout) -> QLabel:
        qlabel = QLabel(label)
        qlabel.setPalette(self.main_window.palette_active)
        layout.addWidget(qlabel)
        return qlabel

    def add_button(self, label: str, layout: QBoxLayout, callback: Callable, insert_index=None) -> QPushButton:
        qpush_button = QPushButton(label)
        qpush_button.setPalette(self.main_window.palette_active)
        qpush_button.released.connect(lambda: callback(qpush_button))
        if insert_index is None:
            layout.addWidget(qpush_button)
        else:
            layout.insertWidget(insert_index, qpush_button)
        return qpush_button

    def _read_events(self, add_button: QPushButton, layout: QBoxLayout):
        """
        A config file is saved for all the custom events created by the user.
        It is read back here
        """
        all_events = []
        if os.path.exists(self.event_save_path):
            with open(self.event_save_path, "r") as file:
                all_events = json.load(file)

        for event in all_events:
            self._create_event_button(add_button, layout, text=event, save=False)

    def _create_event_button(self, button: QWidget, layout: QBoxLayout, text: str = None, save: bool = True):
        if text is None:
            text, ok = QInputDialog.getText(button, 'Create new event', 'Enter the event name:')
            if not ok:
                return

        n_events = len(
            tuple(layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget() is not None)
        )

        self.add_button(text, layout=layout, insert_index=n_events, callback=lambda _: self._add_event(n_events - 1))

        if n_events == self.n_events_max:
            button.setEnabled(False)
            button.setPalette(self.main_window.palette_inactive)

        if save:
            # Read the file first
            all_events = []
            if os.path.exists(self.event_save_path):
                with open(self.event_save_path, "r") as file:
                    all_events = json.load(file)

            all_events.append(text)
            with open(self.event_save_path, "w") as file:
                json.dump(all_events, file)

    def _add_event(self, index: int):
        print(f"Event {index}")

    def _set_time(self, index: int):
        if index == 0:
            print("Starting time set")
        elif index == 1:
            print("Ending time set")
        else:
            raise ValueError("insert_index should be 0 for start or 1 for end")

    def _export_c3d(self):
        print("C3d exported")
