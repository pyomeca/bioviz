import json
import os
from typing import Callable

from PyQt5.QtWidgets import QBoxLayout, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QInputDialog, QWidget, QLineEdit
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
        self.event_colors = (
            ("red", Qt.red),
            ("green", Qt.green),
            ("blue", Qt.blue),
            ("magenta", Qt.magenta),
            ("cyan", Qt.cyan),
            ("yellow", Qt.yellow),
        )
        self.event_buttons = []
        self.current_event_selected = -1
        button = self.add_button(
            "ADD EVENT", events_layout, callback=lambda button: self._create_event_button(button, events_layout)
        )
        self._read_events(button, events_layout)

        event_editor_layout = QVBoxLayout()
        self.add_subtitle("Event editor", event_editor_layout)
        move_event_layout = QHBoxLayout()
        move_event_layout.setAlignment(Qt.AlignCenter)
        self.add_button("<", layout=move_event_layout, callback=lambda _: self._select_event(-1))
        self.current_event_text = self.add_text("", layout=move_event_layout)
        self.add_button(">", layout=move_event_layout, callback=lambda _: self._select_event(1))
        event_editor_layout.addLayout(move_event_layout)
        event_info_layout = QHBoxLayout()
        event_info_layout.setAlignment(Qt.AlignCenter)
        self.selected_event_name = self.add_text("", event_info_layout)
        self.selected_event_frame = self.add_text("", event_info_layout)
        self.selected_event_frame_edit = self.add_text("", event_info_layout, editable=True)
        self.selected_event_frame_edit.setMaximumWidth(50)
        self.selected_event_frame_edit.setVisible(False)
        event_editor_layout.addLayout(event_info_layout)

        # Add export button
        export_layout = QVBoxLayout()
        self.add_subtitle("C3D editor", export_layout)
        self.add_button("Export C3D", layout=export_layout, callback=lambda _: self._export_c3d())

        main_layout.addStretch()
        main_layout.addLayout(time_set_layout)
        main_layout.addStretch()
        main_layout.addLayout(events_layout)
        main_layout.addStretch()
        main_layout.addLayout(event_editor_layout)
        main_layout.addStretch()
        main_layout.addLayout(export_layout)
        main_layout.addStretch()

    def add_subtitle(self, title, layout: QBoxLayout) -> None:
        head_layout = QHBoxLayout()
        head_layout.setAlignment(Qt.AlignCenter)
        self.add_text(title, layout=head_layout)
        layout.addLayout(head_layout)

    def add_text(self, label: str, layout: QBoxLayout, editable: bool = False) -> QLabel:
        qlabel = QLabel(label) if not editable else QLineEdit(label)
        qlabel.setPalette(self.main_window.palette_active)
        layout.addWidget(qlabel)
        return qlabel

    def add_button(self, label: str, layout: QBoxLayout, callback: Callable, insert_index=None, color=None) -> QPushButton:
        qpush_button = QPushButton(label)
        if color is None:
            qpush_button.setPalette(self.main_window.palette_active)
        else:
            qpush_button.setStyleSheet(f"background-color : {color}")
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

        self.event_buttons.append(
            self.add_button(
                text,
                layout=layout,
                insert_index=n_events,
                callback=lambda _: self._add_event_to_trial(n_events - 1),
                color=self.event_colors[n_events - 1][0],
            )
        )

        if n_events == len(self.event_colors):
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

    def _add_event_to_trial(self, index: int):
        self.main_window.set_event(
            self.main_window.movement_slider[0].value() - 1,
            self.event_buttons[index].text(),
            color=self.event_colors[index][1]
        )

    def _select_event(self, step: int):
        self.current_event_selected += step
        if self.current_event_selected < -1:
            self.current_event_selected = self.main_window.last_event_index
        if self.current_event_selected > self.main_window.last_event_index:
            self.current_event_selected = -1

        event = self.main_window.select_event(self.current_event_selected)

        if self.current_event_selected < 0:
            self.current_event_text.setText("")
            self.selected_event_name.setText("No event selected")
            self.selected_event_frame.setText("")
            self.selected_event_frame_edit.setVisible(False)
        else:
            self.current_event_text.setText(str(self.current_event_selected))
            self.selected_event_name.setText(f"{event['name']}: ")
            self.selected_event_frame.setText(str(event["frame"]))
            self.selected_event_frame_edit.setVisible(True)

    def _set_time(self, index: int):
        if index == 0:
            self.main_window.set_movement_first_frame(self.main_window.movement_slider[0].value() - 1)
        elif index == 1:
            self.main_window.set_movement_last_frame(self.main_window.movement_slider[0].value())
        else:
            raise ValueError("insert_index should be 0 for start or 1 for end")

    def _export_c3d(self):
        print("C3d exported")
