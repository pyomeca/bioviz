"""
Visualization toolkit in pyomeca
"""
import os
import time
import sys

import numpy as np
from PyQt5 import QtWidgets
from PyQt5.QtGui import QPalette, QColor

from vtk import (
    vtkActor,
    vtkCellArray,
    vtkInteractorStyleTrackballCamera,
    vtkLine,
    vtkPoints,
    vtkPolyData,
    vtkPolyDataMapper,
    vtkPolyLine,
    vtkRenderer,
    vtkSphereSource,
    vtkUnsignedCharArray,
    vtkOggTheoraWriter,
    vtkWindowToImageFilter,
    vtkPolygon,
    vtkExtractEdges,
    vtkArrowSource,
    vtkNamedColors,
    vtkMath,
    vtkMatrix4x4,
    vtkMinimalStandardRandomSequence,
    vtkTransform,
    vtkTransformPolyDataFilter,
    vtkPlaneSource,
    vtkPNGWriter,
)

from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from pyomeca import Markers, Rototrans
from .mesh import Mesh

first = True
if first:
    app = QtWidgets.QApplication(sys.argv)
    first = False


class VtkWindow(QtWidgets.QMainWindow):
    def __init__(self, background_color=(0, 0, 0)):
        """
        Main window of a bioviz object. If one is interested in placing the main window inside another widget, they
        should call VktWindow first, add whatever widgets/layouts they want in the 'VtkWindow.main_layout',
        including, of course, the actual avatar from 'VtkWindow.vtkWidget'.
        Parameters
        ----------
        background_color : tuple(int)
            Color of the background
        """
        QtWidgets.QMainWindow.__init__(self)
        self.frame = QtWidgets.QFrame()
        self.setCentralWidget(self.frame)

        self.ren = vtkRenderer()
        self.ren.SetBackground(background_color)
        self.ren.GetActiveCamera().ParallelProjectionOn()

        self.avatar_widget = QVTKRenderWindowInteractor(self.frame)
        self.avatar_widget.GetRenderWindow().SetSize(1000, 100)
        self.avatar_widget.GetRenderWindow().AddRenderer(self.ren)

        self.interactor = self.avatar_widget.GetRenderWindow().GetInteractor()
        self.interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        self.interactor.Initialize()
        self.change_background_color(background_color)

        self.main_layout = QtWidgets.QGridLayout()
        self.main_layout.addWidget(self.avatar_widget)
        self.frame.setLayout(self.main_layout)
        self.video_recorder = vtkOggTheoraWriter()
        self.is_fixed_sized = False
        self.minimum_size = self.minimumSize()
        self.maximum_size = self.maximumSize()

        self.show()
        app._in_event_loop = True
        self.is_active = True
        self.should_reset_camera = False
        app.processEvents()

    def closeEvent(self, event):
        """
        Things to do when the window is closed
        """
        self.is_active = False
        app._in_event_loop = False
        # It seems that interactor closes slower than the windows preventing from properly closing the interface.
        # The work-around is to wait a little bit
        time.sleep(0.1)
        super()

    def update_frame(self):
        """
        Force the repaint of the window
        """
        if self.should_reset_camera:
            self.ren.ResetCamera()
            self.should_reset_camera = False
        self.interactor.Render()
        app.processEvents()

    def get_camera_position(self) -> tuple:
        return self.ren.GetActiveCamera().GetPosition()

    def set_camera_position(self, x: float, y: float, z: float):
        cam = self.ren.GetActiveCamera()
        cam.SetPosition(x, y, z)
        self.ren.ResetCamera()

    def get_camera_roll(self) -> float:
        return self.ren.GetActiveCamera().GetRoll()

    def set_camera_roll(self, roll: float):
        cam = self.ren.GetActiveCamera()
        cam.SetRoll(roll)
        self.ren.ResetCamera()

    def get_camera_zoom(self) -> float:
        return 1 / self.ren.GetActiveCamera().GetParallelScale()

    def set_camera_zoom(self, zoom: float):
        cam = self.ren.GetActiveCamera()
        cam.SetParallelScale(1 / zoom)

    def get_camera_focus_point(self) -> tuple:
        return self.ren.GetActiveCamera().GetFocalPoint()

    def set_camera_focus_point(self, x: float, y: float, z: float):
        self.ren.GetActiveCamera().SetFocalPoint(x, y, z)

    def change_background_color(self, color):
        """
        Dynamically change the background color of the windows
        Parameters
        ----------
        color : tuple(int)
        """
        self.ren.SetBackground(color)
        self.setPalette(QPalette(QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))))

    def snapshot(self, save_path: str):
        w2if = vtkWindowToImageFilter()
        w2if.SetInput(self.avatar_widget.GetRenderWindow())
        w2if.Update()

        w = vtkPNGWriter()
        folder_path = os.path.dirname(save_path)
        try:
            os.mkdir(folder_path)
        except FileExistsError:
            pass

        w.SetFileName(save_path)
        w.SetInputData(w2if.GetOutput())

        w.Write()

    def record(self, finish=False, button_to_block=(), file_name=None):
        windowToImageFilter = vtkWindowToImageFilter()
        self.video_recorder.SetInputConnection(windowToImageFilter.GetOutputPort())

        if file_name:
            self.video_recorder.SetFileName(file_name)
            self.video_recorder.Start()
            if not self.is_fixed_sized:
                self.setFixedSize(self.size())

        windowToImageFilter.SetInput(self.avatar_widget.GetRenderWindow())
        windowToImageFilter.ReadFrontBufferOff()
        windowToImageFilter.Update()

        was_true = []
        for b in button_to_block:
            was_true.append(b.isEnabled())
            b.setEnabled(False)
        self.video_recorder.Write()
        for i, b in enumerate(button_to_block):
            if was_true[i]:
                b.setEnabled(True)

        if finish:
            self.video_recorder.End()
            if not self.is_fixed_sized:
                self.setMinimumSize(self.minimum_size)
                self.setMaximumSize(self.maximum_size)


class VtkModel(QtWidgets.QWidget):
    def __init__(
        self,
        parent,
        markers_size=0.010,
        markers_color=(1, 1, 1),
        markers_opacity=1.0,
        contacts_color=(0, 1, 0),
        contacts_size=0.01,
        contacts_opacity=1.0,
        soft_contacts_color=(1, 0.35, 0),
        soft_contacts_size=0.1,
        soft_contacts_opacity=0.35,
        global_ref_frame_length=0.15,
        global_ref_frame_width=5,
        global_center_of_mass_size=0.0075,
        global_center_of_mass_color=(0, 0, 0),
        global_center_of_mass_opacity=1.0,
        segments_center_of_mass_size=0.005,
        segments_center_of_mass_color=(0, 0, 0),
        segments_center_of_mass_opacity=1.0,
        mesh_color=(0, 0, 0),
        patch_color=(0.89, 0.855, 0.788),
        mesh_opacity=0.8,
        mesh_linewidth=1,
        force_wireframe=False,
        wrapping_color=(0, 0, 1),
        wrapping_opacity=1.0,
        muscle_color=(150 / 255, 15 / 255, 15 / 255),
        muscle_opacity=1.0,
        ligament_color=(77 / 255, 0 / 255, 128 / 255),
        ligament_opacity=1.0,
        rt_length=0.1,
        rt_width=2,
        force_color=(85, 78, 0),
        force_opacity=1.0,
    ):
        """
        Creates a model that will holds things to plot
        Parameters
        ----------
        parent
            Parent of the Model window
        markers_size : float
            Size the markers should be drawn
        markers_color : Tuple(int)
            Color the markers should be drawn (1 is max brightness)
        markers_opacity : float
            Opacity of the markers (0.0 is completely transparent, 1.0 completely opaque)
        rt_length : int
            Length of the axes of the system of axes
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.parent_window = parent

        palette = QPalette()
        palette.setColor(self.backgroundRole(), QColor(255, 255, 255))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        self.markers = Markers()
        self.markers_size = markers_size
        self.markers_color = markers_color
        self.markers_opacity = markers_opacity
        self.markers_actors = list()

        self.contacts = Markers()
        self.contacts_size = contacts_size
        self.contacts_color = contacts_color
        self.contacts_opacity = contacts_opacity
        self.contacts_actors = list()

        self.soft_contacts = Markers()
        self.soft_contacts_size = soft_contacts_size
        self.soft_contacts_color = soft_contacts_color
        self.soft_contacts_opacity = soft_contacts_opacity
        self.soft_contacts_actors = list()

        self.has_global_ref_frame = False
        self.global_ref_frame_length = global_ref_frame_length
        self.global_ref_frame_width = global_ref_frame_width

        self.global_center_of_mass = Markers()
        self.global_center_of_mass_size = global_center_of_mass_size
        self.global_center_of_mass_color = global_center_of_mass_color
        self.global_center_of_mass_opacity = global_center_of_mass_opacity
        self.global_center_of_mass_actors = list()

        self.segments_center_of_mass = Markers()
        self.segments_center_of_mass_size = segments_center_of_mass_size
        self.segments_center_of_mass_color = segments_center_of_mass_color
        self.segments_center_of_mass_opacity = segments_center_of_mass_opacity
        self.segments_center_of_mass_actors = list()

        self.all_rt = []
        self.n_rt = 0
        self.rt_length = rt_length
        self.rt_width = rt_width
        self.rt_actors = list()
        self.parent_window.should_reset_camera = True

        self.all_meshes = []
        self.mesh_color = mesh_color
        self.force_wireframe = force_wireframe
        self.patch_color = patch_color
        self.mesh_opacity = mesh_opacity
        self.mesh_linewidth = mesh_linewidth
        self.mesh_actors = list()

        self.all_muscles = []
        self.muscle_color = muscle_color
        self.muscle_opacity = muscle_opacity
        self.muscle_actors = list()

        self.all_ligaments = []
        self.ligament_color = ligament_color
        self.ligament_opacity = ligament_opacity
        self.ligament_actors = list()

        self.all_wrappings = []
        self.wrapping_color = wrapping_color
        self.wrapping_opacity = wrapping_opacity
        self.wrapping_actors = list()

        self.all_forces = []
        self.force_centers = []
        self.max_forces = []
        self.force_color = force_color
        self.force_opacity = force_opacity
        self.normalization_ratio = 0.2
        self.force_actors = list()

        self.gravity_actors = list()

        self.plane_source = []
        self.plane_actor = []

    def set_markers_color(self, markers_color):
        """
        Dynamically change the color of the markers
        Parameters
        ----------
        markers_color : tuple(int)
            Color the markers should be drawn (1 is max brightness)
        """
        self.markers_color = markers_color
        self.update_markers(self.markers)

    def set_markers_size(self, markers_size):
        """
        Dynamically change the size of the markers
        Parameters
        ----------
        markers_size : float
            Size the markers should be drawn
        """
        self.markers_size = markers_size
        self.update_markers(self.markers)

    def set_markers_opacity(self, markers_opacity):
        """
        Dynamically change the opacity of the markers
        Parameters
        ----------
        markers_opacity : float
            Opacity of the markers (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.markers_opacity = markers_opacity
        self.update_markers(self.markers)

    def new_marker_set(self, markers):
        """
        Define a new marker set. This function must be called each time the number of markers change
        Parameters
        ----------
        markers : Markers3d
            One frame of markers

        """
        if len(markers.shape) > 2 and markers.shape[2] > 1:
            raise IndexError("Markers should be from one frame only")
        self.markers = markers

        # Remove previous actors from the scene
        for actor in self.markers_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.markers_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(markers.channel.size):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.markers_actors.append(vtkActor())
            self.markers_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.markers_actors[i])

        # Update marker position
        self.update_markers(self.markers)

    def update_markers(self, markers):
        """
        Update position of the markers on the screen (but do not repaint)
        Parameters
        ----------
        markers : Markers3d
            One frame of markers

        """

        if len(markers.shape) > 2 and markers.shape[2] > 1:
            raise IndexError("Markers should be from one frame only")
        if markers.channel.size != self.markers.channel.size:
            self.new_marker_set(markers)
            return  # Prevent calling update_markers recursively
        self.markers = markers
        markers = np.array(markers)

        for i, actor in enumerate(self.markers_actors):
            # mapper = actors.GetNextActor().GetMapper()
            mapper = actor.GetMapper()
            self.markers_actors[i].GetProperty().SetColor(self.markers_color)
            self.markers_actors[i].GetProperty().SetOpacity(self.markers_opacity)
            source = vtkSphereSource()
            source.SetCenter(markers[0:3, i])
            source.SetRadius(self.markers_size)
            mapper.SetInputConnection(source.GetOutputPort())

    def set_contacts_color(self, contacts_color):
        """
        Dynamically change the color of the contacts
        Parameters
        ----------
        contacts_color : tuple(int)
            Color the contacts should be drawn (1 is max brightness)
        """
        self.contacts_color = contacts_color
        self.update_contacts(self.contacts)

    def set_contacts_size(self, contacts_size):
        """
        Dynamically change the size of the contacts
        Parameters
        ----------
        contacts_size : float
            Size the contacts should be drawn
        """
        self.contacts_size = contacts_size
        self.update_contacts(self.contacts)

    def set_contacts_opacity(self, contacts_opacity):
        """
        Dynamically change the opacity of the contacts
        Parameters
        ----------
        contacts_opacity : float
            Opacity of the contacts (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.contacts_opacity = contacts_opacity
        self.update_contacts(self.contacts)

    def new_contact_set(self, contacts):
        """
        Define a new marker set. This function must be called each time the number of contacts change
        Parameters
        ----------
        contacts : Markers3d
            One frame of contacts

        """
        if contacts.time.size != 1:
            raise IndexError("Contacts should be from one frame only")
        self.contacts = contacts

        # Remove previous actors from the scene
        for actor in self.contacts_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.contacts_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(contacts.channel.size):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.contacts_actors.append(vtkActor())
            self.contacts_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.contacts_actors[i])

        # Update marker position
        self.update_contacts(self.contacts)

    def update_contacts(self, contacts):
        """
        Update position of the contacts on the screen (but do not repaint)
        Parameters
        ----------
        contacts : Markers3d
            One frame of contacts

        """

        if contacts.time.size != 1:
            raise IndexError("Contacts should be from one frame only")
        if contacts.channel.size != self.contacts.channel.size:
            self.new_contact_set(contacts)
            return  # Prevent calling update_contacts recursively
        self.contacts = contacts
        contacts = np.array(contacts)

        for i, actor in enumerate(self.contacts_actors):
            # mapper = actors.GetNextActor().GetMapper()
            mapper = actor.GetMapper()
            self.contacts_actors[i].GetProperty().SetColor(self.contacts_color)
            self.contacts_actors[i].GetProperty().SetOpacity(self.contacts_opacity)
            source = vtkSphereSource()
            source.SetCenter(contacts[0:3, i])
            source.SetRadius(self.contacts_size)
            mapper.SetInputConnection(source.GetOutputPort())

    def set_soft_contacts_color(self, soft_contacts_color):
        """
        Dynamically change the color of the soft_contacts
        Parameters
        ----------
        soft_contacts_color : tuple(int)
            Color the soft_contacts should be drawn (1 is max brightness)
        """
        self.soft_contacts_color = soft_contacts_color
        self.update_soft_contacts(self.soft_contacts)

    def set_soft_contacts_size(self, soft_contacts_size):
        """
        Dynamically change the size of the soft_contacts
        Parameters
        ----------
        soft_contacts_size : float
            Size the soft_contacts should be drawn
        """
        self.soft_contacts_size = soft_contacts_size
        self.update_soft_contacts(self.soft_contacts)

    def set_soft_contacts_opacity(self, soft_contacts_opacity):
        """
        Dynamically change the opacity of the soft_contacts
        Parameters
        ----------
        soft_contacts_opacity : float
            Opacity of the soft_contacts (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.soft_contacts_opacity = soft_contacts_opacity
        self.update_soft_contacts(self.soft_contacts)

    def new_soft_contacts_set(self, soft_contacts):
        """
        Define a new marker set. This function must be called each time the number of soft_contacts change
        Parameters
        ----------
        soft_contacts : Markers3d
            One frame of soft_contacts

        """
        if soft_contacts.time.size != 1:
            raise IndexError("soft_contacts should be from one frame only")
        self.soft_contacts = soft_contacts

        # Remove previous actors from the scene
        for actor in self.soft_contacts_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.soft_contacts_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(soft_contacts.channel.size):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.soft_contacts_actors.append(vtkActor())
            self.soft_contacts_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.soft_contacts_actors[i])
        # Update marker position
        self.update_soft_contacts(self.soft_contacts)

    def update_soft_contacts(self, soft_contacts):
        """
        Update position of the soft_contacts on the screen (but do not repaint)
        Parameters
        ----------
        soft_contacts : Markers3d
            One frame of soft_contacts

        """

        if soft_contacts.time.size != 1:
            raise IndexError("soft_contacts should be from one frame only")
        if soft_contacts.channel.size != self.soft_contacts.channel.size:
            self.new_soft_contacts_set(soft_contacts)
            return  # Prevent calling update_soft_contacts recursively
        self.soft_contacts = soft_contacts
        soft_contacts = np.array(soft_contacts)

        for i, actor in enumerate(self.soft_contacts_actors):
            # mapper = actors.GetNextActor().GetMapper()
            mapper = actor.GetMapper()
            self.soft_contacts_actors[i].GetProperty().SetColor(self.soft_contacts_color)
            self.soft_contacts_actors[i].GetProperty().SetOpacity(self.soft_contacts_opacity)
            source = vtkSphereSource()
            source.SetCenter(soft_contacts[0:3, i])
            source.SetRadius(self.soft_contacts_size[i])
            mapper.SetInputConnection(source.GetOutputPort())

    def set_global_center_of_mass_color(self, global_center_of_mass_color):
        """
        Dynamically change the color of the global center of mass
        Parameters
        ----------
        global_center_of_mass_color : tuple(int)
            Color the center of mass should be drawn (1 is max brightness)
        """
        self.global_center_of_mass_color = global_center_of_mass_color
        self.update_global_center_of_mass(self.global_center_of_mass)

    def set_global_center_of_mass_size(self, global_center_of_mass_size):
        """
        Dynamically change the size of the global center of mass
        Parameters
        ----------
        global_center_of_mass_size : float
            Size the center of mass should be drawn
        """
        self.global_center_of_mass_size = global_center_of_mass_size
        self.update_global_center_of_mass(self.global_center_of_mass)

    def set_global_center_of_mass_opacity(self, global_center_of_mass_opacity):
        """
        Dynamically change the opacity of the global center of mass
        Parameters
        ----------
        global_center_of_mass_opacity : float
            Opacity of the center of mass (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.global_center_of_mass_opacity = global_center_of_mass_opacity
        self.update_global_center_of_mass(self.global_center_of_mass)

    def new_global_center_of_mass_set(self, global_center_of_mass):
        """
        Define a new global center of mass set. This function must be called each time the number of center
        of mass change
        Parameters
        ----------
        global_center_of_mass : Markers3d
            One frame of segment center of mas

        """
        if global_center_of_mass.channel.size != 1:
            raise IndexError("Global center of mass should be from one frame only")
        self.global_center_of_mass = global_center_of_mass

        # Remove previous actors from the scene
        for actor in self.global_center_of_mass_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.global_center_of_mass_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(global_center_of_mass.channel.size):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.global_center_of_mass_actors.append(vtkActor())
            self.global_center_of_mass_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.global_center_of_mass_actors[i])

        # Update marker position
        self.update_global_center_of_mass(self.global_center_of_mass)

    def update_global_center_of_mass(self, global_center_of_mass):
        """
        Update position of the segment center of mass on the screen (but do not repaint)
        Parameters
        ----------
        global_center_of_mass : Markers3d
            One frame of center of mass

        """

        if global_center_of_mass.time.size != 1:
            raise IndexError("Segment center of mass should be from one frame only")
        if global_center_of_mass.channel.size != self.global_center_of_mass.channel.size:
            self.new_global_center_of_mass_set(global_center_of_mass)
            return  # Prevent calling update_center_of_mass recursively
        self.global_center_of_mass = global_center_of_mass

        for i, actor in enumerate(self.global_center_of_mass_actors):
            # mapper = actors.GetNextActor().GetMapper()
            mapper = actor.GetMapper()
            self.global_center_of_mass_actors[i].GetProperty().SetColor(self.global_center_of_mass_color)
            self.global_center_of_mass_actors[i].GetProperty().SetOpacity(self.global_center_of_mass_opacity)
            source = vtkSphereSource()
            source.SetCenter(global_center_of_mass[0:3, i])
            source.SetRadius(self.global_center_of_mass_size)
            mapper.SetInputConnection(source.GetOutputPort())

    def set_segments_center_of_mass_color(self, segments_center_of_mass_color):
        """
        Dynamically change the color of the segments center of mass
        Parameters
        ----------
        segments_center_of_mass_color : tuple(int)
            Color the center of mass should be drawn (1 is max brightness)
        """
        self.segments_center_of_mass_color = segments_center_of_mass_color
        self.update_segments_center_of_mass(self.segments_center_of_mass)

    def set_segments_center_of_mass_size(self, segments_center_of_mass_size):
        """
        Dynamically change the size of the segments center of mass
        Parameters
        ----------
        segments_center_of_mass_size : float
            Size the center of mass should be drawn
        """
        self.segments_center_of_mass_size = segments_center_of_mass_size
        self.update_segments_center_of_mass(self.segments_center_of_mass)

    def set_segments_center_of_mass_opacity(self, segments_center_of_mass_opacity):
        """
        Dynamically change the opacity of the segments center of mass
        Parameters
        ----------
        segments_center_of_mass_opacity : float
            Opacity of the center of mass (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.segments_center_of_mass_opacity = segments_center_of_mass_opacity
        self.update_segments_center_of_mass(self.segments_center_of_mass)

    def new_segments_center_of_mass_set(self, segments_center_of_mass):
        """
        Define a new segments center of mass set. This function must be called each time the number of center
        of mass change
        Parameters
        ----------
        segments_center_of_mass : Markers3d
            One frame of segment center of mas

        """
        if segments_center_of_mass.time.size != 1:
            raise IndexError("Segments center of mass should be from one frame only")
        self.segments_center_of_mass = segments_center_of_mass

        # Remove previous actors from the scene
        for actor in self.segments_center_of_mass_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.segments_center_of_mass_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(segments_center_of_mass.channel.size):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.segments_center_of_mass_actors.append(vtkActor())
            self.segments_center_of_mass_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.segments_center_of_mass_actors[i])

        # Update marker position
        self.update_segments_center_of_mass(self.segments_center_of_mass)

    def update_segments_center_of_mass(self, segments_center_of_mass):
        """
        Update position of the segment center of mass on the screen (but do not repaint)
        Parameters
        ----------
        segments_center_of_mass : Markers3d
            One frame of center of mass

        """

        if segments_center_of_mass.time.size != 1:
            raise IndexError("Segment center of mass should be from one frame only")
        if segments_center_of_mass.channel.size != self.segments_center_of_mass.channel.size:
            self.new_segments_center_of_mass_set(segments_center_of_mass)
            return  # Prevent calling update_center_of_mass recursively
        self.segments_center_of_mass = segments_center_of_mass

        for i, actor in enumerate(self.segments_center_of_mass_actors):
            # mapper = actors.GetNextActor().GetMapper()
            mapper = actor.GetMapper()
            self.segments_center_of_mass_actors[i].GetProperty().SetColor(self.segments_center_of_mass_color)
            self.segments_center_of_mass_actors[i].GetProperty().SetOpacity(self.segments_center_of_mass_opacity)
            source = vtkSphereSource()
            source.SetCenter(segments_center_of_mass[0:3, i])
            source.SetRadius(self.segments_center_of_mass_size)
            mapper.SetInputConnection(source.GetOutputPort())

    def set_mesh_color(self, mesh_color):
        """
        Dynamically change the color of the mesh
        Parameters
        ----------
        mesh_color : tuple(int)
            Color the mesh should be drawn (1 is max brightness)
        """
        self.mesh_color = mesh_color
        self.update_mesh(self.all_meshes)

    def set_mesh_opacity(self, mesh_opacity):
        """
        Dynamically change the opacity of the mesh
        Parameters
        ----------
        mesh_opacity : float
            Opacity of the mesh (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.mesh_opacity = mesh_opacity
        self.update_mesh(self.all_meshes)

    def new_mesh_set(self, all_meshes):
        """
        Define a new mesh set. This function must be called each time the number of meshes change
        Parameters
        ----------
        all_meshes : MeshCollection
            One frame of mesh

        """
        if isinstance(all_meshes, Mesh):
            mesh_tp = []
            mesh_tp.append(all_meshes)
            all_meshes = mesh_tp

        if not isinstance(all_meshes, list):
            raise TypeError("Please send a list of mesh to update_mesh")
        self.all_meshes = all_meshes

        # Remove previous actors from the scene
        for actor in self.mesh_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.mesh_actors = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, mesh) in enumerate(self.all_meshes):
            if mesh.time.size != 1:
                raise IndexError("Mesh should be from one frame only")

            points = vtkPoints()
            for j in range(mesh.channel.size):
                # points.InsertNextPoint([0, 0, 0])
                points.InsertNextPoint(mesh.data[:3, j, 0].tolist())

            # Create an array for each triangle
            draw_patch = not mesh.automatic_triangles and not self.force_wireframe
            if draw_patch:
                poly_type = vtkPolygon
                n_ids = 3
                color = self.patch_color[i]
            else:
                poly_type = vtkPolyLine
                n_ids = 4
                color = self.mesh_color
            cells = vtkCellArray()

            # Create the polygons
            for j in range(mesh.triangles.shape[1]):
                poly = poly_type()
                poly.GetPointIds().SetNumberOfIds(n_ids)  # make a tri
                for k in range(len(mesh.triangles[:, j])):
                    poly.GetPointIds().SetId(k, mesh.triangles[k, j])
                if not draw_patch:
                    poly.GetPointIds().SetId(3, mesh.triangles[0, j])  # Close the triangle
                cells.InsertNextCell(poly)

            poly_data = vtkPolyData()
            poly_data.SetPoints(points)
            if draw_patch:
                poly_data.SetPolys(cells)
            else:
                poly_data.SetLines(cells)

            mapper = vtkPolyDataMapper()
            mapper.SetInputData(poly_data)

            # Create an actor
            self.mesh_actors.append(vtkActor())
            self.mesh_actors[i].SetMapper(mapper)
            self.mesh_actors[i].GetProperty().SetColor(color)
            self.mesh_actors[i].GetProperty().SetOpacity(self.mesh_opacity)

            self.parent_window.ren.AddActor(self.mesh_actors[i])

        # Update marker position
        self.update_mesh(self.all_meshes)

    def update_mesh(self, all_meshes):
        """
        Update position of the mesh on the screen (but do not repaint)
        Parameters
        ----------
        all_meshes : MeshCollection
            One frame of mesh

        """
        if isinstance(all_meshes, Mesh):
            mesh_tp = []
            mesh_tp.append(all_meshes)
            all_meshes = mesh_tp

        for i, mesh in enumerate(all_meshes):
            if mesh.time.size != 1:
                raise IndexError("Mesh should be from one frame only")

            if len(self.all_meshes) <= i or mesh.channel.size != self.all_meshes[i].channel.size:
                self.new_mesh_set(all_meshes)
                return  # Prevent calling update_markers recursively

        if not isinstance(all_meshes, list):
            raise TypeError("Please send a list of mesh to update_mesh")

        self.all_meshes = all_meshes

        for (i, mesh) in enumerate(self.all_meshes):
            points = vtkPoints()
            n_vertex = mesh.channel.size
            mesh = np.array(mesh)
            for j in range(n_vertex):
                points.InsertNextPoint(mesh[0:3, j])

            poly_line = self.mesh_actors[i].GetMapper().GetInput()
            poly_line.SetPoints(points)
            self.mesh_actors[i].GetProperty().SetLineWidth(self.mesh_linewidth)

    def set_muscle_color(self, muscle_color):
        """
        Dynamically change the color of the muscles
        Parameters
        ----------
        muscle_color : tuple(int)
            Color the muscles should be drawn
        """
        self.muscle_color = muscle_color
        self.update_muscles(self.all_muscles)

    def set_muscle_opacity(self, muscle_opacity):
        """
        Dynamically change the opacity of the muscles
        Parameters
        ----------
        muscle_opacity : float
            Opacity of the muscles (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.muscle_opacity = muscle_opacity
        self.update_muscle(self.all_muscles)

    def new_muscle_set(self, all_muscles):
        """
        Define a new muscle set. This function must be called each time the number of muscles change
        Parameters
        ----------
        all_muscles : MeshCollection
            One frame of mesh

        """
        if isinstance(all_muscles, Mesh):
            musc_tp = []
            musc_tp.append(all_muscles)
            all_muscles = musc_tp

        if not isinstance(all_muscles, list):
            raise TypeError("Please send a list of muscle to update_muscle")
        self.all_muscles = all_muscles

        # Remove previous actors from the scene
        for actor in self.muscle_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.muscle_actors = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, mesh) in enumerate(self.all_muscles):
            if mesh.time.size != 1:
                raise IndexError("Muscles should be from one frame only")

            points = vtkPoints()
            for j in range(mesh.channel.size):
                points.InsertNextPoint([0, 0, 0])

            # Create an array for each triangle
            cell = vtkCellArray()
            for j in range(mesh.triangles.shape[1]):  # For each triangle
                line = vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(4)
                for k in range(len(mesh.triangles[:, j])):  # For each index
                    line.GetPointIds().SetId(k, mesh.triangles[k, j])
                line.GetPointIds().SetId(3, mesh.triangles[0, j])  # Close the triangle
                cell.InsertNextCell(line)
            poly_line = vtkPolyData()
            poly_line.SetPoints(points)
            poly_line.SetLines(cell)

            # Create a mapper
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(poly_line)

            # Create an actor
            self.muscle_actors.append(vtkActor())
            self.muscle_actors[i].SetMapper(mapper)
            self.muscle_actors[i].GetProperty().SetColor(self.muscle_color)
            self.muscle_actors[i].GetProperty().SetOpacity(self.muscle_opacity)
            self.muscle_actors[i].GetProperty().SetLineWidth(5)

            self.parent_window.ren.AddActor(self.muscle_actors[i])

        # Update marker position
        self.update_muscle(self.all_muscles)

    def update_muscle(self, all_muscles):
        """
        Update position of the muscles on the screen (but do not repaint)
        Parameters
        ----------
        all_muscles : MeshCollection
            One frame of muscle mesh

        """
        if isinstance(all_muscles, Mesh):
            musc_tp = []
            musc_tp.append(all_muscles)
            all_muscles = musc_tp

        for i, muscle in enumerate(all_muscles):
            if muscle.time.size != 1:
                raise IndexError("Muscle should be from one frame only")

            if len(self.all_muscles) <= i or muscle.channel.size != self.all_muscles[i].channel.size:
                self.new_muscle_set(all_muscles)
                return  # Prevent calling update_markers recursively

        if not isinstance(all_muscles, list):
            raise TypeError("Please send a list of muscles to update_muscle")

        self.all_muscles = all_muscles

        for (i, mesh) in enumerate(self.all_muscles):
            points = vtkPoints()
            n_vertex = mesh.channel.size
            mesh = np.array(mesh)
            for j in range(n_vertex):
                points.InsertNextPoint(mesh[0:3, j])

            poly_line = self.muscle_actors[i].GetMapper().GetInput()
            poly_line.SetPoints(points)

    def set_ligament_color(self, ligament_color):
        """
        Dynamically change the color of the ligaments
        Parameters
        ----------
        ligament_color : tuple(int)
            Color the ligaments should be drawn
        """
        self.ligament_color = ligament_color
        self.update_ligaments(self.all_ligaments)

    def set_ligament_opacity(self, ligament_opacity):
        """
        Dynamically change the opacity of the ligaments
        Parameters
        ----------
        ligament_opacity : float
            Opacity of the ligaments (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.ligament_opacity = ligament_opacity
        self.update_ligament(self.all_ligaments)

    def new_ligament_set(self, all_ligaments):
        """
        Define a new ligament set. This function must be called each time the number of ligaments change
        Parameters
        ----------
        all_ligaments : MeshCollection
            One frame of mesh

        """
        if isinstance(all_ligaments, Mesh):
            lig_tp = []
            lig_tp.append(all_ligaments)
            all_ligaments = lig_tp

        if not isinstance(all_ligaments, list):
            raise TypeError("Please send a list of ligament to update_ligament")
        self.all_ligaments = all_ligaments

        # Remove previous actors from the scene
        for actor in self.ligament_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.ligament_actors = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, mesh) in enumerate(self.all_ligaments):
            if mesh.time.size != 1:
                raise IndexError("ligaments should be from one frame only")

            points = vtkPoints()
            for j in range(mesh.channel.size):
                points.InsertNextPoint([0, 0, 0])

            # Create an array for each triangle
            cell = vtkCellArray()
            for j in range(mesh.triangles.shape[1]):  # For each triangle
                line = vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(4)
                for k in range(len(mesh.triangles[:, j])):  # For each index
                    line.GetPointIds().SetId(k, mesh.triangles[k, j])
                line.GetPointIds().SetId(3, mesh.triangles[0, j])  # Close the triangle
                cell.InsertNextCell(line)
            poly_line = vtkPolyData()
            poly_line.SetPoints(points)
            poly_line.SetLines(cell)

            # Create a mapper
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(poly_line)

            # Create an actor
            self.ligament_actors.append(vtkActor())
            self.ligament_actors[i].SetMapper(mapper)
            self.ligament_actors[i].GetProperty().SetColor(self.ligament_color)
            self.ligament_actors[i].GetProperty().SetOpacity(self.ligament_opacity)
            self.ligament_actors[i].GetProperty().SetLineWidth(5)

            self.parent_window.ren.AddActor(self.ligament_actors[i])

        # Update marker position
        self.update_ligament(self.all_ligaments)

    def update_ligament(self, all_ligaments):
        """
        Update position of the ligaments on the screen (but do not repaint)
        Parameters
        ----------
        all_ligaments : MeshCollection
            One frame of ligament mesh

        """
        if isinstance(all_ligaments, Mesh):
            lig_tp = []
            lig_tp.append(all_ligaments)
            all_ligaments = lig_tp

        for i, ligament in enumerate(all_ligaments):
            if ligament.time.size != 1:
                raise IndexError("ligament should be from one frame only")

            if len(self.all_ligaments) <= i or ligament.channel.size != self.all_ligaments[i].channel.size:
                self.new_ligament_set(all_ligaments)
                return  # Prevent calling update_markers recursively

        if not isinstance(all_ligaments, list):
            raise TypeError("Please send a list of ligaments to update_ligament")

        self.all_ligaments = all_ligaments

        for (i, mesh) in enumerate(self.all_ligaments):
            points = vtkPoints()
            n_vertex = mesh.channel.size
            mesh = np.array(mesh)
            for j in range(n_vertex):
                points.InsertNextPoint(mesh[0:3, j])

            poly_line = self.ligament_actors[i].GetMapper().GetInput()
            poly_line.SetPoints(points)

    def set_wrapping_color(self, wrapping_color):
        """
        Dynamically change the color of the wrapping
        Parameters
        ----------
        wrapping_color : tuple(int)
            Color the wrapping should be drawn (1 is max brightness)
        """
        self.wrapping_color = wrapping_color
        self.update_wrapping(self.all_wrappings)

    def set_wrapping_opacity(self, wrapping_opacity):
        """
        Dynamically change the opacity of the wrapping
        Parameters
        ----------
        wrapping_opacity : float
            Opacity of the wrapping (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.wrapping_opacity = wrapping_opacity
        self.update_wrapping(self.all_wrappings)

    def new_wrapping_set(self, all_wrappings, seg):
        """
        Define a new wrapping set. This function must be called each time the number of wrappings change
        Parameters
        ----------
        all_wrappings : MeshCollection
            One frame of wrapping

        """
        if isinstance(all_wrappings, Mesh):
            wrapping_tp = []
            wrapping_tp.append(all_wrappings)
            all_wrappings = wrapping_tp

        if not isinstance(all_wrappings, list):
            raise TypeError("Please send a list of wrapping to update_wrapping")
        self.all_wrappings[seg] = all_wrappings

        # Remove previous actors from the scene
        for actor in self.wrapping_actors[seg]:
            self.parent_window.ren.RemoveActor(actor)
        self.wrapping_actors[seg] = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, wrapping) in enumerate(self.all_wrappings[seg]):
            if wrapping.time.size != 1:
                raise IndexError("Mesh should be from one frame only")

            points = vtkPoints()
            for j in range(wrapping.channel.size):
                points.InsertNextPoint([0, 0, 0])

            # Create an array for each triangle
            cell = vtkCellArray()
            for j in range(wrapping.triangles.shape[1]):  # For each triangle
                line = vtkPolyLine()
                line.GetPointIds().SetNumberOfIds(4)
                for k in range(len(wrapping.triangles[:, j])):  # For each index
                    line.GetPointIds().SetId(k, wrapping.triangles[k, j])
                line.GetPointIds().SetId(3, wrapping.triangles[0, j])  # Close the triangle
                cell.InsertNextCell(line)
            poly_line = vtkPolyData()
            poly_line.SetPoints(points)
            poly_line.SetLines(cell)

            # Create a mapper
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(poly_line)

            # Create an actor
            self.wrapping_actors[seg].append(vtkActor())
            self.wrapping_actors[seg][i].SetMapper(mapper)
            self.wrapping_actors[seg][i].GetProperty().SetColor(self.wrapping_color)
            self.wrapping_actors[seg][i].GetProperty().SetOpacity(self.wrapping_opacity)

            self.parent_window.ren.AddActor(self.wrapping_actors[seg][i])

        # # Update marker position
        # self.update_wrapping(self.all_wrappings)

    def update_wrapping(self, all_wrappings):
        """
        Update position of the wrapping on the screen (but do not repaint)
        Parameters
        ----------
        all_wrappings : MeshCollection
            One frame of wrapping

        """
        if not self.all_wrappings:
            self.all_wrappings = [[]] * len(all_wrappings)
            self.wrapping_actors = [[]] * len(all_wrappings)

        for seg, wrappings in enumerate(all_wrappings):
            for i, wrapping in enumerate(wrappings):
                if wrapping.time.size != 1:
                    raise IndexError("Mesh should be from one frame only")

                if (
                    len(self.all_wrappings[seg]) <= i
                    or wrapping.channel.size != self.all_wrappings[seg][i].channel.size
                ):
                    self.new_wrapping_set(wrappings, seg)
                    # return  # Prevent calling update_markers recursively

            if not isinstance(wrappings, list):
                raise TypeError("Please send a list of wrapping to update_wrapping")

            self.all_wrappings[seg] = wrappings

            for (i, wrapping) in enumerate(self.all_wrappings[seg]):
                points = vtkPoints()
                n_vertex = wrapping.channel.size
                wrapping = np.array(wrapping)
                for j in range(n_vertex):
                    points.InsertNextPoint(wrapping[0:3, j])

                poly_line = self.wrapping_actors[seg][i].GetMapper().GetInput()
                poly_line.SetPoints(points)

    def new_rt_set(self, all_rt):
        """
        Define a new rt set. This function must be called each time the number of rt change
        Parameters
        ----------
        all_rt : Rototrans
            One frame of all Rototrans to draw

        """
        if isinstance(all_rt, Rototrans):
            rt_tp = []
            rt_tp.append(all_rt[:, :])
            all_rt = rt_tp

        if not isinstance(all_rt, list):
            raise TypeError("Please send a list of rt to new_rt_set")

        # Remove previous actors from the scene
        for actor in self.rt_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.rt_actors = list()

        for i, rt in enumerate(all_rt):
            if rt.time.size != 1:
                raise IndexError("RT should be from one frame only")

            # Create the polyline which will hold the actors
            lines_poly_data = vtkPolyData()

            # Create four points of a generic system of axes
            pts = vtkPoints()
            pts.InsertNextPoint([0, 0, 0])
            pts.InsertNextPoint([1, 0, 0])
            pts.InsertNextPoint([0, 1, 0])
            pts.InsertNextPoint([0, 0, 1])
            lines_poly_data.SetPoints(pts)

            # Create the first line(between Origin and P0)
            line0 = vtkLine()
            line0.GetPointIds().SetId(0, 0)
            line0.GetPointIds().SetId(1, 1)

            # Create the second line(between Origin and P1)
            line1 = vtkLine()
            line1.GetPointIds().SetId(0, 0)
            line1.GetPointIds().SetId(1, 2)

            # Create the second line(between Origin and P1)
            line2 = vtkLine()
            line2.GetPointIds().SetId(0, 0)
            line2.GetPointIds().SetId(1, 3)

            # Create a vtkCellArray container and store the lines in it
            lines = vtkCellArray()
            lines.InsertNextCell(line0)
            lines.InsertNextCell(line1)
            lines.InsertNextCell(line2)

            # Add the lines to the polydata container
            lines_poly_data.SetLines(lines)

            # Create a vtkUnsignedCharArray container and store the colors in it
            colors = vtkUnsignedCharArray()
            colors.SetNumberOfComponents(3)
            colors.InsertNextTuple([255, 0, 0])
            colors.InsertNextTuple([0, 255, 0])
            colors.InsertNextTuple([0, 0, 255])
            lines_poly_data.GetCellData().SetScalars(colors)

            # Create a mapper
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(lines_poly_data)

            # Create an actor
            self.rt_actors.append(vtkActor())
            self.rt_actors[i].SetMapper(mapper)
            self.rt_actors[i].GetProperty().SetLineWidth(self.rt_width)

            self.parent_window.ren.AddActor(self.rt_actors[i])

        # Set rt orientations
        self.n_rt = len(all_rt)
        self.update_rt(all_rt)

    def update_rt(self, all_rt):
        """
        Update position of the Rototrans on the screen (but do not repaint)
        Parameters
        ----------
        all_rt : RototransCollection
            One frame of all Rototrans to draw

        """
        if isinstance(all_rt, Rototrans):
            rt_tp = []
            rt_tp.append(all_rt[:, :])
            all_rt = rt_tp

        if len(all_rt) != self.n_rt:
            self.new_rt_set(all_rt)
            return  # Prevent calling update_rt recursively

        if not isinstance(all_rt, list):
            raise TypeError("Please send a list of rt to new_rt_set")

        self.all_rt = all_rt

        for i, rt in enumerate(self.all_rt):
            if rt.time.size != 1:
                raise IndexError("RT should be from one frame only")

            # Update the end points of the axes and the origin
            pts = vtkPoints()
            pts.InsertNextPoint(rt.meca.translation)
            pts.InsertNextPoint(rt.meca.translation + rt.isel(col=0)[0:3] * self.rt_length)
            pts.InsertNextPoint(rt.meca.translation + rt.isel(col=1)[0:3] * self.rt_length)
            pts.InsertNextPoint(rt.meca.translation + rt.isel(col=2)[0:3] * self.rt_length)

            # Update polydata in mapper
            lines_poly_data = self.rt_actors[i].GetMapper().GetInput()
            lines_poly_data.SetPoints(pts)

    def create_global_ref_frame(self):
        """
        Define a new global reference frame set. This function must be called once
        Parameters
        ----------
        global_ref_frame : Rototrans
            One frame of all Rototrans to draw

        """

        if self.has_global_ref_frame:
            raise RuntimeError("create_global_ref_frame should only be called once")
        self.has_global_ref_frame = True

        # Create the polyline which will hold the actors
        lines_poly_data = vtkPolyData()

        # Create four points of a generic system of axes
        pts = vtkPoints()
        pts.InsertNextPoint([0, 0, 0])
        pts.InsertNextPoint([self.global_ref_frame_length, 0, 0])
        pts.InsertNextPoint([0, self.global_ref_frame_length, 0])
        pts.InsertNextPoint([0, 0, self.global_ref_frame_length])
        lines_poly_data.SetPoints(pts)

        # Create the first line(between Origin and P0)
        line0 = vtkLine()
        line0.GetPointIds().SetId(0, 0)
        line0.GetPointIds().SetId(1, 1)

        # Create the second line(between Origin and P1)
        line1 = vtkLine()
        line1.GetPointIds().SetId(0, 0)
        line1.GetPointIds().SetId(1, 2)

        # Create the second line(between Origin and P1)
        line2 = vtkLine()
        line2.GetPointIds().SetId(0, 0)
        line2.GetPointIds().SetId(1, 3)

        # Create a vtkCellArray container and store the lines in it
        lines = vtkCellArray()
        lines.InsertNextCell(line0)
        lines.InsertNextCell(line1)
        lines.InsertNextCell(line2)

        # Add the lines to the polydata container
        lines_poly_data.SetLines(lines)

        # Create a vtkUnsignedCharArray container and store the colors in it
        colors = vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.InsertNextTuple([255, 0, 0])
        colors.InsertNextTuple([0, 255, 0])
        colors.InsertNextTuple([0, 0, 255])
        lines_poly_data.GetCellData().SetScalars(colors)

        # Create a mapper
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(lines_poly_data)

        # Create an actor
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetLineWidth(self.global_ref_frame_width)

        self.parent_window.ren.AddActor(actor)

    def set_force_color(self, force_color):
        """
        Dynamically change the color of the force
        Parameters
        ----------
        force_color : tuple(int)
            Color the force should be drawn (1 is max brightness)
        """
        self.force_color = force_color

    def set_force_opacity(self, force_opacity):
        """
        Dynamically change the opacity of the _force
        Parameters
        ----------
        force_opacity : float
            Opacity of the force (0.0 is completely transparent, 1.0 completely opaque)
        Returns
        -------

        """
        self.force_opacity = force_opacity

    def new_force_set(self, segment_jcs, all_forces, max_forces, normalization_ratio):
        """
        Define a new force set.
        Parameters
        ----------
        segment_jcs : list
            list of transformation for each segment
        all_forces : np.ndarray
            force array. Dims are : (1) segments, (2) application and magnitude point arrow coordinates (3) frame
        max_forces : list
            list of maximal force for each segment on all frames

        """
        # Arrow visualization parameters
        arrow_source = vtkArrowSource()
        arrow_source.SetTipResolution(15)
        arrow_source.SetShaftResolution(8)
        arrow_source.SetShaftRadius(0.015)
        arrow_source.SetTipLength(0.2)
        arrow_source.SetTipRadius(0.08)

        self.arrow_source = arrow_source

        transform = vtkTransform()

        transform_polydata = vtkTransformPolyDataFilter()
        transform_polydata.SetTransform(transform)
        transform_polydata.SetInputConnection(arrow_source.GetOutputPort())

        self.all_forces = all_forces
        # Remove previous actors from the scene
        for actor in self.force_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.force_actors = list()

        for i, forces in enumerate(all_forces):
            # Create a mapper
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(transform_polydata.GetOutputPort())

            # Create an actor
            self.force_actors.append(vtkActor())
            self.force_actors[i].SetMapper(mapper)
            self.force_actors[i].GetProperty().SetColor(self.force_color)
            self.force_actors[i].GetProperty().SetOpacity(self.force_opacity)

            self.parent_window.ren.AddActor(self.force_actors[i])
            # self.parent_window.ren.ResetCamera()

        # Set rt orientations
        self.n_force = len(all_forces)
        self.update_force(segment_jcs, all_forces, max_forces, normalization_ratio)

    @staticmethod
    def compute_basis_force(application_point, magnitude_point):
        """
        Compute basis to plot vtk arrow object from two points.
        Parameters
        ----------
        application_point : list
            list of the 3 coordinates for the arrow starting point
        magnitude_point: list
            list of the 3 coordinates for the arrow ending point
        Return
        ----------
            matrix of the transformation and the length of the arrow.
        """
        # Compute a basis
        normalizedX = [0.0] * 3
        normalizedY = [0.0] * 3
        normalizedZ = [0.0] * 3

        # The X axis is a vector from start to end
        vtkMath.Subtract(magnitude_point, application_point, normalizedX)
        length = vtkMath.Norm(normalizedX)
        vtkMath.Normalize(normalizedX)

        rng = vtkMinimalStandardRandomSequence()
        rng.SetSeed(8775070)
        max_r = 10.0

        # The Z axis is an arbitrary vector cross X
        arbitrary = [0.0] * 3
        for i in range(0, 3):
            arbitrary[i] = rng.GetRangeValue(-max_r, max_r)
            rng.Next()
        vtkMath.Cross(normalizedX, arbitrary, normalizedZ)
        vtkMath.Normalize(normalizedZ)

        # The Y axis is Z cross X
        vtkMath.Cross(normalizedZ, normalizedX, normalizedY)
        matrix = vtkMatrix4x4()

        # Create the direction cosine matrix
        matrix.Identity()
        for i in range(0, 3):
            matrix.SetElement(i, 0, normalizedX[i])
            matrix.SetElement(i, 1, normalizedY[i])
            matrix.SetElement(i, 2, normalizedZ[i])

        return matrix, length

    def update_force(self, segment_jcs, all_forces, max_forces, normalization_ratio):
        """
        Update force on the screen (but do not repaint)
        Parameters
        ----------
        segment_jcs : list
            list of roto-translation matrix for each segment
        all_forces : np.ndarray
            force array. Dims are : (1) nb of segments, (2) arrow start and end points coordinates (3) frame
        max_forces : list
            list of maximal force for each segment compute from all frames
        normalization_ratio : float
            ratio to normalize force for visualization
        """
        if self.all_forces == []:
            self.new_force_set(segment_jcs, all_forces, max_forces, normalization_ratio)
            return  # Prevent calling update_markers recursively

        self.max_forces = max_forces
        self.all_forces = all_forces
        for i, forces in enumerate(all_forces):
            # Express force from current segment basis to global basis
            rot_seg = segment_jcs[i][:3, :3]
            trans_seg = segment_jcs[i][:-1, 3:]
            force_magnitude = np.dot(rot_seg, forces[3:, :])
            force_magnitude = force_magnitude + trans_seg
            force_application = np.dot(rot_seg, forces[:3, :])
            force_application = force_application + trans_seg
            application_point = [force_application[0, :], force_application[1, :], force_application[2, :]]
            magnitude_point = [force_magnitude[0, :], force_magnitude[1, :], force_magnitude[2, :]]
            # Compute a basis for the arrow scaling
            matrix, length = self.compute_basis_force(application_point, magnitude_point)
            # Normalize force for visualization
            length = length * normalization_ratio / max_forces[i]
            transform = vtkTransform()
            transform.Translate(application_point)
            transform.Concatenate(matrix)
            transform.Scale(length, length, length)

            # Create an actor
            mapper = self.force_actors[i].GetMapper()
            transform_polydata = vtkTransformPolyDataFilter()
            transform_polydata.SetTransform(transform)
            transform_polydata.SetInputConnection(self.arrow_source.GetOutputPort())

            mapper.SetInputConnection(transform_polydata.GetOutputPort())

            self.force_actors[i].SetMapper(mapper)
            self.force_actors[i].GetProperty().SetColor(self.force_color)
            self.force_actors[i].GetProperty().SetOpacity(self.force_opacity)

    def new_gravity_vector(self, segment_rt, gravity, length, normalization_ratio, vector_color):
        """
        Define a new gravity vector.
        Parameters
        ----------
        segment_rt : np.ndarray
            homogeneous matrix in which coordinates are applied
        gravity : np.ndarray
            gravity array with 3 application coordinates and 3 magnitude coordinates
        length : float
            absolut length of gravity vector to scale arrow
        normalization_ratio: float
            ratio to scale arrow
        vector_color: tuple
            tuple of RGB for vector color

        """
        # Arrow visualization parameters
        arrow_source = vtkArrowSource()
        arrow_source.SetTipResolution(15)
        arrow_source.SetShaftResolution(8)
        arrow_source.SetShaftRadius(0.015)
        arrow_source.SetTipLength(0.2)
        arrow_source.SetTipRadius(0.08)

        self.arrow_source = arrow_source

        # Arrow orientation
        transform = vtkTransform()
        transform_polydata = vtkTransformPolyDataFilter()
        transform_polydata.SetTransform(transform)
        transform_polydata.SetInputConnection(arrow_source.GetOutputPort())

        rot_seg = segment_rt[:3, :3]
        trans_seg = segment_rt[:-1, 3:]
        force_magnitude = np.dot(rot_seg, gravity[3:])
        force_magnitude = force_magnitude + trans_seg.reshape(3)
        force_application = np.dot(rot_seg, gravity[:3])
        force_application = force_application + trans_seg.reshape(3)
        application_point = [force_application[0], force_application[1], force_application[2]]
        magnitude_point = [force_magnitude[0], force_magnitude[1], force_magnitude[2]]

        # Compute a basis for the arrow scaling
        matrix, length = self.compute_basis_force(application_point, magnitude_point)

        # Normalize force for visualization
        length = length * normalization_ratio / length
        transform = vtkTransform()
        transform.Translate(application_point)
        transform.Concatenate(matrix)
        transform.Scale(length, length, length)

        # Create an actor
        mapper = vtkPolyDataMapper()

        transform_polydata = vtkTransformPolyDataFilter()
        transform_polydata.SetTransform(transform)
        transform_polydata.SetInputConnection(self.arrow_source.GetOutputPort())
        mapper.SetInputConnection(transform_polydata.GetOutputPort())

        self.gravity_actors = vtkActor()
        self.gravity_actors.SetMapper(mapper)
        self.gravity_actors.GetProperty().SetColor(vector_color)

        self.parent_window.ren.AddActor(self.gravity_actors)

    def new_floor(self, origin, normal, color, scale):
        self.plane_source = vtkPlaneSource()
        n_grid_per_meter = 2
        resolution = [scale[0] * n_grid_per_meter, scale[1] * n_grid_per_meter]
        self.plane_source.SetResolution(resolution[0], resolution[1])

        # Ground orientation
        self.plane_source.SetCenter(origin)
        self.plane_source.SetNormal(normal)
        self.plane_source.Update()

        # Scale ground size
        transform = vtkTransform()
        transform.Scale(scale)

        transform_polydata = vtkTransformPolyDataFilter()
        transform_polydata.SetTransform(transform)
        transform_polydata.SetInputConnection(self.plane_source.GetOutputPort())

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(transform_polydata.GetOutputPort())

        self.plane_actor = vtkActor()
        self.plane_actor.SetMapper(mapper)
        self.plane_actor.GetProperty().EdgeVisibilityOn()
        self.plane_actor.GetProperty().SetEdgeColor(1, 1, 1)
        self.plane_actor.GetProperty().SetColor(color)
        self.plane_actor.GetProperty().SetOpacity(0.02)

        self.parent_window.ren.AddActor(self.plane_actor)
