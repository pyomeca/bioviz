"""
FileIO GUIs in pyoviz
"""

import difflib
from pathlib import Path

import ezc3d
import numpy as np
from PyQt5 import QtWidgets


class FieldsAssignment(QtWidgets.QMainWindow):
    """
    FieldsAssignment allows to assign a list of targets to a list of channels dynamically.
    Use the export method to get the output dictionary.

    Parameters
    ----------
    directory : str,  Path
        Directory which contains all data
    targets : list
        List of target strings
    kind : str
        "emg",  "analogs" or "markers"
    prefix : str
        Prefix in channel names (keeps the part after prefix)
    """

    def __init__(self, directory, targets, kind, prefix=':'):
        # set parameters
        self.trials = [ifile for idir in directory for ifile in Path(idir).glob('*.c3d')]
        self.targets = targets
        self.kind = kind
        self.prefix = prefix

        self.iassigned, self.assigned = [], []
        self.i, self.itarget = -1, 0

        # init gui
        app = QtWidgets.QApplication([])
        super().__init__()
        self.init_layout()
        self.init_window()

        self.read_and_check()

        app.exec()

    # --- Init methods

    def init_window(self):
        """Initialize main window."""
        self.setWindowTitle(f"Pyomeca's fields assignment")
        self.resize(1200, 700)
        self.show()

    def init_layout(self):
        """Initialize layout."""
        self.central_widget = QtWidgets.QWidget(self)
        self.grid_layout = QtWidgets.QGridLayout(self.central_widget)

        # gui's elements
        self.init_labels()
        self.init_lists()
        self.init_buttons()
        self.init_progress_bar()
        self.init_bars()

        self.setCentralWidget(self.central_widget)

    def init_labels(self):
        """Initialize labels."""
        # current trial label
        self.current_trial = QtWidgets.QLabel(self.central_widget)
        self.grid_layout.addWidget(self.current_trial, 0, 3, 1, 1)
        self.current_trial.setText('Current trial')

        # current fields label
        self.current_fields = QtWidgets.QLabel(self.central_widget)
        self.grid_layout.addWidget(self.current_fields, 1, 0, 1, 1)
        self.current_fields.setText('Current fields')

        # target fields label
        self.target_fields = QtWidgets.QLabel(self.central_widget)
        self.grid_layout.addWidget(self.target_fields, 1, 4, 1, 1)
        self.target_fields.setText('Assigned fields')

        # current target label
        self.current_target = QtWidgets.QLabel(self.central_widget)
        self.grid_layout.addWidget(self.current_target, 0, 0, 1, 1)
        self.current_target.setStyleSheet('font-size: 16pt')
        self.current_target.setText(f'Current target: {self.targets[self.itarget]}')

    def init_lists(self):
        """Initialize lists."""
        # current fields list
        self.current_list = QtWidgets.QListWidget(self.central_widget)
        self.current_list.setStyleSheet('font-size: 16pt')
        self.grid_layout.addWidget(self.current_list, 5, 0, 1, 1)

        # assigned fields list
        self.assigned_list = QtWidgets.QListWidget(self.central_widget)
        self.assigned_list.setStyleSheet('font-size: 16pt')
        self.grid_layout.addWidget(self.assigned_list, 5, 4, 1, 1)

    def init_buttons(self):
        """Initialize buttons."""
        # assign push button
        self.button_assign = QtWidgets.QPushButton(self.central_widget)
        self.grid_layout.addWidget(self.button_assign, 6, 3, 1, 1)
        self.button_assign.setText('Assign [1]')
        self.button_assign.setShortcut('1')
        self.button_assign.clicked.connect(self.action_assign)

        # nan push button
        self.button_nan = QtWidgets.QPushButton(self.central_widget)
        self.grid_layout.addWidget(self.button_nan, 7, 3, 1, 1)
        self.button_nan.setText('NaN [2]')
        self.button_nan.setShortcut('2')
        self.button_nan.clicked.connect(self.action_nan)

        # undo push button
        self.button_undo = QtWidgets.QPushButton(self.central_widget)
        self.grid_layout.addWidget(self.button_undo, 8, 3, 1, 1)
        self.button_undo.setText('Undo [3]')
        self.button_undo.setShortcut('3')
        self.button_undo.clicked.connect(self.action_undo)

        # done push button
        self.button_done = QtWidgets.QPushButton(self.central_widget)
        self.grid_layout.addWidget(self.button_done, 9, 3, 1, 1)
        self.button_done.setText('Done [q]')
        self.button_done.setShortcut('q')
        self.button_done.clicked.connect(self.action_done)

    def init_progress_bar(self):
        """Initialize progress bar."""
        self.progress_bar = QtWidgets.QProgressBar(self.central_widget)
        self.grid_layout.addWidget(self.progress_bar, 1, 3, 1, 1)

    def init_bars(self):
        """Initialize menu and status bar."""
        # menu bar
        self.menu_bar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self.menu_bar)

        # status bar
        self.status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(self.status_bar)

    # --- Action methods

    def read_and_check(self):
        self.i += 1
        if self.i >= len(self.trials):
            self.close()
            self.export()
        else:
            channel_names = self.action_read_file()
            self.action_check_fields(channel_names)

    def sort_list(self):
        items = []
        for index in range(self.current_list.count()):
            items.append(self.current_list.item(index))
        labels = [i.text() for i in items]
        closest = difflib.get_close_matches(self.targets[self.itarget],
                                            labels, n=1)
        if closest:
            self.current_list.clear()
            names = [i for i in labels if i != closest[0]]
            names.insert(0, closest[0])
            self.current_list.addItems(names)
            self.current_list.setCurrentRow(0)

    def action_assign(self):
        """Assign a field to the item selected in current_list."""
        choice = {
            'index': self.current_list.currentIndex().row(),
            'item': self.current_list.currentItem().text()
        }

        self.current_list.takeItem(choice['index'])
        self.assigned_list.addItem(choice['item'])

        self.iassigned.append(choice['item'])

        if len(self.iassigned) >= len(self.targets):
            self.assigned.append(self.iassigned)  # append this file's assignment
            self.iassigned = []

            self.current_list.clear()
            self.assigned_list.clear()

            self.read_and_check()
        else:
            self.itarget += 1
            self.current_target.setText(f'Current target: {self.targets[self.itarget]}')
            self.sort_list()

    def action_nan(self):
        """Assign a field to a nan."""
        self.assigned_list.addItem('NaN')
        self.iassigned.append('')

        if len(self.iassigned) >= len(self.targets):
            self.assigned.append(self.iassigned)  # append this file's assignment
            self.iassigned = []

            self.current_list.clear()
            self.assigned_list.clear()

            self.read_and_check()
        else:
            self.itarget += 1
            self.current_target.setText(f'Current target: {self.targets[self.itarget]}')
            self.sort_list()

    def action_undo(self):
        """Undo an assign or nan action."""
        choice = self.assigned_list.item(0)
        self.assigned_list.takeItem(0)

        if choice.text() != 'NaN':
            self.current_list.addItem(choice.text())

        self.iassigned.pop()
        self.itarget -= 1
        self.current_target.setText(f'Current target: {self.targets[self.itarget]}')
        self.sort_list()

    def action_done(self):
        """When you are done and want to quit."""
        choice = QtWidgets.QMessageBox.question(self,
                                                'Done?',
                                                'Exit?',
                                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if choice == QtWidgets.QMessageBox.Yes:
            print('Assignment done.')
            self.export()
            self.close()

    def action_read_file(self):
        """Read a c3d file and return channel names"""
        # update current trial label and progress bar
        self.current_trial.setText(str(self.trials[self.i].parts[-1]))
        self.progress_bar.setValue(int(self.i / len(self.trials) * 100))

        # ezc3d version
        reader = ezc3d.c3d(str(self.trials[self.i]))
        if self.kind == 'markers':
            kind_str = 'POINT'
        elif self.kind == 'analogs' or self.kind == 'emg':
            kind_str = 'ANALOG'
        else:
            raise ValueError(f'`kind` shoud be "analogs", "emg" or "markers". You provided {self.kind}')

        channel_names = [i.c_str().split(self.prefix)[-1] for i in
                         reader.parameters().group(kind_str).parameter('LABELS').valuesAsString()]
        return channel_names

    @staticmethod
    def test_in_assigned(x, channel_names):
        """test if one of the assigned contains all targets"""
        np.isin(x, channel_names).all()

    def action_check_fields(self, channel_names):
        """Check if targets are in channel names or already assigned fields. Update GUI if not"""
        if np.isin(self.targets, channel_names).all():
            # test if channel_names contains all targets
            self.read_and_check()
        else:
            if self.assigned and np.isin(self.assigned, channel_names).any(axis=1).any():
                # test if one of the assigned contains al targets
                self.read_and_check()
            else:
                self.iassigned, self.itarget = [], 0
                self.current_list.addItems(channel_names)
                self.sort_list()

    def export(self):
        """Set the output dict to object"""
        self.output = {
            self.kind: {
                'targets': self.targets,
                'assigned': self.assigned
            }
        }
