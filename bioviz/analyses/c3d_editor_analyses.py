import json
import os
from typing import Callable

import ezc3d

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd

from ..qt_ui import (
    QBoxLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QInputDialog,
    QWidget,
    QLineEdit,
    QFileDialog,
    Qt,
    QColorConstants,
)


class C3dEditorAnalyses:
    def __init__(self, main_window, parent: QWidget = None):
        # Get some aliases
        self.widget = parent if parent is not None else QWidget()
        self.main_window = main_window
        self.event_save_path = "bioviz_events.json"

        # Centralize the materials
        main_layout = QVBoxLayout(self.widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Set time trial
        time_set_layout = QVBoxLayout()
        self.add_subtitle("Time setter", time_set_layout)
        time_set_button_layout = QHBoxLayout()
        self.add_button("Set Start", layout=time_set_button_layout, callback=lambda _: self._set_time(0))
        self.add_button("Set End", layout=time_set_button_layout, callback=lambda _: self._set_time(1))
        time_set_layout.addLayout(time_set_button_layout)

        # Events
        self.events_layout = QVBoxLayout()
        self.add_event_button: QWidget | None = None
        self.add_subtitle("Events setter", self.events_layout)
        self.event_colors = (
            ("red", QColorConstants.Red),
            ("green", QColorConstants.Green),
            ("blue", QColorConstants.Blue),
            ("magenta", QColorConstants.Magenta),
            ("cyan", QColorConstants.Cyan),
            ("yellow", QColorConstants.Yellow),
        )
        self.event_buttons = []
        self.current_event_selected = -1
        self.first_frame_c3d = 0

        event_editor_layout = QVBoxLayout()
        self.add_subtitle("Event editor", event_editor_layout)
        move_event_layout = QHBoxLayout()
        move_event_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previous_event_button = self.add_button(
            "<", layout=move_event_layout, callback=lambda _: self._select_event(-1)
        )
        self.next_event_button = self.add_button(
            ">", layout=move_event_layout, callback=lambda _: self._select_event(1)
        )
        event_editor_layout.addLayout(move_event_layout)
        self.clear_events_button = self.add_button(
            "Clear all events", layout=event_editor_layout, callback=lambda _: self.main_window.clear_events()
        )
        self.current_event_text = self.add_subtitle("", layout=event_editor_layout)
        self.selected_event_name = self.add_subtitle("No event selected", event_editor_layout)
        event_change_info_layout = QHBoxLayout()
        event_change_info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_event_frame_text = self.add_text("Change frame: ", event_change_info_layout)
        frame_editor_layout = QVBoxLayout()
        self.selected_event_frame_edit = self.add_text("", frame_editor_layout, editable=True)
        self.selected_event_frame_edit.setMaximumWidth(50)
        self.set_event_frame_button = self.add_button(
            "Set", frame_editor_layout, callback=self._set_event_frame_from_text_edit
        )
        event_change_info_layout.addLayout(frame_editor_layout)
        self.reset_event_frame_button = self.add_button(
            "Set to\ncurrent frame", event_change_info_layout, callback=self._set_event_frame_to_current_frame
        )
        event_editor_layout.addLayout(event_change_info_layout)
        self._toggle_event_setter(False)
        self.event_from_c3d_file_name = ""

        # Add export button
        export_layout = QVBoxLayout()
        self.add_subtitle("C3D editor", export_layout)
        self.export_c3d_button = self.add_button("Export C3D", layout=export_layout, callback=self._export_c3d)

        main_layout.addStretch()
        main_layout.addLayout(time_set_layout)
        main_layout.addStretch()
        main_layout.addLayout(self.events_layout)
        main_layout.addStretch()
        main_layout.addLayout(event_editor_layout)
        main_layout.addStretch()
        main_layout.addLayout(export_layout)
        main_layout.addStretch()

    def on_activate(self):
        self._read_events()

    def add_subtitle(self, title, layout: QBoxLayout) -> QLabel:
        head_layout = QHBoxLayout()
        head_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qlabel = self.add_text(title, layout=head_layout)
        layout.addLayout(head_layout)
        return qlabel

    def add_text(self, label: str, layout: QBoxLayout, editable: bool = False) -> QLabel | QLineEdit:
        qlabel = QLabel(label) if not editable else QLineEdit(label)
        qlabel.setPalette(self.main_window.palette_active)
        layout.addWidget(qlabel)
        return qlabel

    def add_button(
        self, label: str, layout: QBoxLayout, callback: Callable, insert_index=None, color=None
    ) -> QPushButton:
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

    def _read_events(self):
        """
        A config file is saved for all the custom events created by the user.
        It is read back here
        """
        if self.add_event_button is None:
            self.add_event_button = self.add_button(
                "ADD EVENT LABEL", self.events_layout, callback=lambda _: self._create_event_button()
            )

        c3d = None
        if (
            self.main_window.c3d_file_name is not None
            and self.main_window.c3d_file_name != self.event_from_c3d_file_name
        ):
            self.event_from_c3d_file_name = self.main_window.c3d_file_name
            c3d = ezc3d.c3d(self.main_window.c3d_file_name)
            n_frames_slider = (
                self.main_window.movement_slider[0].maximum() - self.main_window.movement_slider[0].minimum() + 1
            )
            self.first_frame_c3d = c3d["header"]["points"]["first_frame"]
            n_frames_c3d = c3d["data"]["points"].shape[2]
            if n_frames_c3d != n_frames_slider:
                n_frames_c3d = c3d["header"]["points"]["last_frame"]
                self.first_frame_c3d = 0

            if n_frames_c3d != n_frames_slider:
                print(
                    "Marker data shape from C3D and movement shape do not correspond. "
                    "Automatic events loading is skipped"
                )
                c3d = None
                self.first_frame_c3d = 0

        all_event_buttons = []
        reload_events_from_c3d = False
        if c3d is not None and "EVENT" in c3d["parameters"] and c3d["parameters"]["EVENT"]["USED"]["value"] > 0:
            # Clear the previously loaded events
            for button in self.event_buttons:
                self.events_layout.removeWidget(button)
                button.deleteLater()
            self.event_buttons.clear()
            self.events_layout.update()

            labels = list(set(c3d["parameters"]["EVENT"]["LABELS"]["value"]))
            contexts = list(set(c3d["parameters"]["EVENT"]["CONTEXTS"]["value"]))
            for context in contexts:
                for label in labels:
                    all_event_buttons.append(f"{context} {label}")
            reload_events_from_c3d = True

        elif not self.event_buttons and os.path.exists(self.event_save_path):
            # Only add button if the were not previously added and there is a json file
            with open(self.event_save_path, "r") as file:
                all_event_buttons = json.load(file)

        for event in all_event_buttons:
            self._create_event_button(text=event, save=False)

        if reload_events_from_c3d:
            self.main_window.clear_events()
            for i in range(c3d["parameters"]["EVENT"]["USED"]["value"][0]):
                context = (
                    c3d["parameters"]["EVENT"]["CONTEXTS"]["value"][i]
                    if "CONTEXTS" in c3d["parameters"]["EVENT"]
                    and len(c3d["parameters"]["EVENT"]["CONTEXTS"]["value"]) > 0
                    else ""
                )
                label = (
                    c3d["parameters"]["EVENT"]["LABELS"]["value"][i]
                    if len(c3d["parameters"]["EVENT"]["LABELS"]["value"]) > 0
                    else ""
                )
                name = f"{context} {label}"
                frame = (
                    round(c3d["parameters"]["EVENT"]["TIMES"]["value"][1, i] * c3d["header"]["points"]["frame_rate"])
                    - self.first_frame_c3d
                )
                button_index = [button.text() for button in self.event_buttons].index(name)
                self.main_window.set_event(frame, name, color=self.event_colors[button_index][1])

    def _create_event_button(self, text: str = None, save: bool = True):
        if text is None:
            text, ok = QInputDialog.getText(self.add_event_button, "Create new event", "Enter the event name:")
            if not ok:
                return

        n_events = len(
            tuple(
                self.events_layout.itemAt(i).widget()
                for i in range(self.events_layout.count())
                if self.events_layout.itemAt(i).widget() is not None
            )
        )

        self.event_buttons.append(
            self.add_button(
                text,
                layout=self.events_layout,
                insert_index=n_events,
                callback=lambda _: self._add_event_to_trial(n_events - 1),
                color=self.event_colors[n_events - 1][0],
            )
        )

        if n_events == len(self.event_colors):
            self.add_event_button.setEnabled(False)
            self.add_event_button.setPalette(self.main_window.palette_inactive)

        if save:
            # Read the file first
            all_events = [event.text for event in self.event_buttons]

            all_events.append(text)
            with open(self.event_save_path, "w") as file:
                json.dump(all_events, file)

    def _add_event_to_trial(self, index: int):
        self.main_window.set_event(
            self.main_window.movement_slider[0].value() - 1,
            self.event_buttons[index].text(),
            color=self.event_colors[index][1],
        )

    def _modify_event_to_trial(self, index: int, frame: int):
        event = self.main_window.select_event(index)

        self.main_window.set_event(frame, event["name"], index, event["marker"].color)
        self._select_event(step=0)  # Refresh the window

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
            self._toggle_event_setter(False)
        else:
            self.current_event_text.setText(f"The event selected (#{self.current_event_selected}) is")
            self.selected_event_name.setText(f"'{event['name']}', set on frame: {event['frame'] + 1}")
            self._toggle_event_setter(True)

    def _toggle_event_setter(self, set_visible: bool):
        if set_visible:
            self.selected_event_frame_text.setVisible(True)
            self.selected_event_frame_edit.setVisible(True)
            self.set_event_frame_button.setVisible(True)
            self.reset_event_frame_button.setVisible(True)
        else:
            self.selected_event_frame_text.setVisible(False)
            self.selected_event_frame_edit.setVisible(False)
            self.set_event_frame_button.setVisible(False)
            self.reset_event_frame_button.setVisible(False)

    def _set_event_frame_from_text_edit(self, _):
        try:
            new_frame = int(self.selected_event_frame_edit.text()) - 1
        except:
            self.selected_event_frame_edit.setText("")
            return

        self._modify_event_to_trial(self.current_event_selected, new_frame)
        self.selected_event_frame_edit.setText("")

    def _set_event_frame_to_current_frame(self, _):
        new_frame = self.main_window.movement_slider[0].value() - 1
        self._modify_event_to_trial(self.current_event_selected, new_frame)

    def _set_time(self, index: int):
        if index == 0:
            self.main_window.set_movement_first_frame(self.main_window.movement_slider[0].value() - 1)
        elif index == 1:
            self.main_window.set_movement_last_frame(self.main_window.movement_slider[0].value())
        else:
            raise ValueError("insert_index should be 0 for start or 1 for end")

    def _export_c3d(self, _):
        filepath = os.path.dirname(self.main_window.c3d_file_name)
        modified_filename = os.path.splitext(os.path.basename(self.main_window.c3d_file_name))[0] + "_withEvents.c3d"

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name = QFileDialog.getSaveFileName(
            self.main_window.vtk_window,
            "C3d path to save",
            f"{filepath}/{modified_filename}",
            "C3D (*.c3d)",
            options=options,
        )
        if not file_name[0]:
            return

        # Load previous file and export it with the events
        c3d = ezc3d.c3d(self.main_window.c3d_file_name)

        first_frame = self.main_window.movement_first_frame + self.first_frame_c3d
        contexts, labels, times = self.convert_event_for_c3d(c3d["header"]["points"]["frame_rate"])

        c3d["header"]["points"]["first_frame"] = first_frame
        c3d["header"]["points"]["last_frame"] = self.main_window.movement_last_frame + self.first_frame_c3d
        c3d.add_parameter("EVENT", "USED", (self.main_window.n_events,))
        c3d.add_parameter("EVENT", "CONTEXTS", contexts)
        c3d.add_parameter("EVENT", "LABELS", labels)
        c3d.add_parameter("EVENT", "TIMES", times)

        c3d.write(file_name[0])

    def convert_event_for_c3d(self, frame_rate):
        first_frame = self.main_window.movement_first_frame + self.first_frame_c3d
        events = self.main_window.events

        contexts = []
        labels = []
        times = []
        for event in events:
            if event["frame"] == -1:
                continue
            split_name = event["name"].split(" ")
            if len(split_name) > 1 and (split_name[0].lower() == "left" or split_name[0].lower() == "right"):
                context = split_name[0]
                label = " ".join(split_name[1:])
            else:
                context = ""
                label = " ".join(split_name)
            contexts.append(context)
            labels.append(label)

            times.append((event["frame"] + first_frame) * 1 / frame_rate)
        times = [[0] * len(times), times]  # Add a line of zeros as Nexus does
        return contexts, labels, times
