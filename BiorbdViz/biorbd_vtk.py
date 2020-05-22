"""
Visualization toolkit in pyomeca
"""

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
)
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from pyomeca import Markers3d, RotoTrans, RotoTransCollection
from .mesh import Mesh, MeshCollection

first = True
if first:
    app = QtWidgets.QApplication(sys.argv)
    first = False


class VtkWindow(QtWidgets.QMainWindow):
    def __init__(self, background_color=(0, 0, 0)):
        """
        Main window of a BiorbdViz object. If one is interested in placing the main window inside another widget, they
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

    def change_background_color(self, color):
        """
        Dynamically change the background color of the windows
        Parameters
        ----------
        color : tuple(int)
        """
        self.ren.SetBackground(color)
        self.setPalette(QPalette(QColor(color[0] * 255, color[1] * 255, color[2] * 255)))

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
        global_ref_frame_length=0.15,
        global_ref_frame_width=5,
        global_center_of_mass_size=0.0075,
        global_center_of_mass_color=(0, 0, 0),
        global_center_of_mass_opacity=1.0,
        segments_center_of_mass_size=0.005,
        segments_center_of_mass_color=(0, 0, 0),
        segments_center_of_mass_opacity=1.0,
        mesh_color=(0, 0, 0),
        mesh_opacity=1.0,
        muscle_color=(150 / 255, 15 / 255, 15 / 255),
        muscle_opacity=1.0,
        rt_length=0.1,
        rt_width=2,
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

        self.markers = Markers3d()
        self.markers_size = markers_size
        self.markers_color = markers_color
        self.markers_opacity = markers_opacity
        self.markers_actors = list()

        self.has_global_ref_frame = False
        self.global_ref_frame_length = global_ref_frame_length
        self.global_ref_frame_width = global_ref_frame_width

        self.global_center_of_mass = Markers3d()
        self.global_center_of_mass_size = global_center_of_mass_size
        self.global_center_of_mass_color = global_center_of_mass_color
        self.global_center_of_mass_opacity = global_center_of_mass_opacity
        self.global_center_of_mass_actors = list()

        self.segments_center_of_mass = Markers3d()
        self.segments_center_of_mass_size = segments_center_of_mass_size
        self.segments_center_of_mass_color = segments_center_of_mass_color
        self.segments_center_of_mass_opacity = segments_center_of_mass_opacity
        self.segments_center_of_mass_actors = list()

        self.all_rt = RotoTransCollection()
        self.n_rt = 0
        self.rt_length = rt_length
        self.rt_width = rt_width
        self.rt_actors = list()
        self.parent_window.should_reset_camera = True

        self.all_meshes = MeshCollection()
        self.mesh_color = mesh_color
        self.mesh_opacity = mesh_opacity
        self.mesh_actors = list()

        self.all_muscles = MeshCollection()
        self.muscle_color = muscle_color
        self.muscle_opacity = muscle_opacity
        self.muscle_actors = list()

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
        if markers.get_num_frames() != 1:
            raise IndexError("Markers should be from one frame only")
        self.markers = markers

        # Remove previous actors from the scene
        for actor in self.markers_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.markers_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(markers.get_num_markers()):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.markers_actors.append(vtkActor())
            self.markers_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.markers_actors[i])
            self.parent_window.ren.ResetCamera()

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

        if markers.get_num_frames() != 1:
            raise IndexError("Markers should be from one frame only")
        if markers.get_num_markers() != self.markers.get_num_markers():
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
        if global_center_of_mass.get_num_frames() != 1:
            raise IndexError("Global center of mass should be from one frame only")
        self.global_center_of_mass = global_center_of_mass

        # Remove previous actors from the scene
        for actor in self.global_center_of_mass_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.global_center_of_mass_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(global_center_of_mass.get_num_markers()):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.global_center_of_mass_actors.append(vtkActor())
            self.global_center_of_mass_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.global_center_of_mass_actors[i])
            self.parent_window.ren.ResetCamera()

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

        if global_center_of_mass.get_num_frames() != 1:
            raise IndexError("Segment center of mass should be from one frame only")
        if global_center_of_mass.get_num_markers() != self.global_center_of_mass.get_num_markers():
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
        if segments_center_of_mass.get_num_frames() != 1:
            raise IndexError("Segments center of mass should be from one frame only")
        self.segments_center_of_mass = segments_center_of_mass

        # Remove previous actors from the scene
        for actor in self.segments_center_of_mass_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.segments_center_of_mass_actors = list()

        # Create the geometry of a point (the coordinate) points = vtk.vtkPoints()
        for i in range(segments_center_of_mass.get_num_markers()):
            # Create a mapper
            mapper = vtkPolyDataMapper()

            # Create an actor
            self.segments_center_of_mass_actors.append(vtkActor())
            self.segments_center_of_mass_actors[i].SetMapper(mapper)

            self.parent_window.ren.AddActor(self.segments_center_of_mass_actors[i])
            self.parent_window.ren.ResetCamera()

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

        if segments_center_of_mass.get_num_frames() != 1:
            raise IndexError("Segment center of mass should be from one frame only")
        if segments_center_of_mass.get_num_markers() != self.segments_center_of_mass.get_num_markers():
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
            mesh_tp = MeshCollection()
            mesh_tp.append(all_meshes)
            all_meshes = mesh_tp

        if all_meshes.get_num_frames() != 1:
            raise IndexError("Mesh should be from one frame only")

        if not isinstance(all_meshes, MeshCollection):
            raise TypeError("Please send a list of mesh to update_mesh")
        self.all_meshes = all_meshes

        # Remove previous actors from the scene
        for actor in self.mesh_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.mesh_actors = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, mesh) in enumerate(self.all_meshes):
            points = vtkPoints()
            for j in range(mesh.get_num_vertex()):
                points.InsertNextPoint([0, 0, 0])

            # Create an array for each triangle
            cell = vtkCellArray()
            for j in range(mesh.get_num_triangles()):  # For each triangle
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
            self.mesh_actors.append(vtkActor())
            self.mesh_actors[i].SetMapper(mapper)
            self.mesh_actors[i].GetProperty().SetColor(self.mesh_color)
            self.mesh_actors[i].GetProperty().SetOpacity(self.mesh_opacity)

            self.parent_window.ren.AddActor(self.mesh_actors[i])
            self.parent_window.ren.ResetCamera()

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
            mesh_tp = MeshCollection()
            mesh_tp.append(all_meshes)
            all_meshes = mesh_tp

        if all_meshes.get_num_frames() != 1:
            raise IndexError("Mesh should be from one frame only")

        for i in range(len(all_meshes)):
            if all_meshes.get_mesh(i).get_num_vertex() != self.all_meshes.get_mesh(i).get_num_vertex():
                self.new_mesh_set(all_meshes)
                return  # Prevent calling update_markers recursively

        if not isinstance(all_meshes, MeshCollection):
            raise TypeError("Please send a list of mesh to update_mesh")

        self.all_meshes = all_meshes

        for (i, mesh) in enumerate(self.all_meshes):
            points = vtkPoints()
            n_vertex = mesh.get_num_vertex()
            mesh = np.array(mesh)
            for j in range(n_vertex):
                points.InsertNextPoint(mesh[0:3, j])

            poly_line = self.mesh_actors[i].GetMapper().GetInput()
            poly_line.SetPoints(points)

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
            musc_tp = MeshCollection()
            musc_tp.append(all_muscles)
            all_muscles = musc_tp

        if all_muscles.get_num_frames() != 1:
            raise IndexError("Muscles should be from one frame only")

        if not isinstance(all_muscles, MeshCollection):
            raise TypeError("Please send a list of muscle to update_muscle")
        self.all_muscles = all_muscles

        # Remove previous actors from the scene
        for actor in self.muscle_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.muscle_actors = list()

        # Create the geometry of a point (the coordinate) points = vtkPoints()
        for (i, mesh) in enumerate(self.all_muscles):
            points = vtkPoints()
            for j in range(mesh.get_num_vertex()):
                points.InsertNextPoint([0, 0, 0])

            # Create an array for each triangle
            cell = vtkCellArray()
            for j in range(mesh.get_num_triangles()):  # For each triangle
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
            self.parent_window.ren.ResetCamera()

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
            musc_tp = MeshCollection()
            musc_tp.append(all_muscles)
            all_muscles = musc_tp

        if all_muscles.get_num_frames() != 1:
            raise IndexError("Muscle should be from one frame only")

        for i in range(len(all_muscles)):
            if all_muscles.get_mesh(i).get_num_vertex() != self.all_muscles.get_mesh(i).get_num_vertex():
                self.new_muscle_set(all_muscles)
                return  # Prevent calling update_markers recursively

        if not isinstance(all_muscles, MeshCollection):
            raise TypeError("Please send a list of muscles to update_muscle")

        self.all_muscles = all_muscles

        for (i, mesh) in enumerate(self.all_muscles):
            points = vtkPoints()
            n_vertex = mesh.get_num_vertex()
            mesh = np.array(mesh)
            for j in range(n_vertex):
                points.InsertNextPoint(mesh[0:3, j])

            poly_line = self.muscle_actors[i].GetMapper().GetInput()
            poly_line.SetPoints(points)

    def new_rt_set(self, all_rt):
        """
        Define a new rt set. This function must be called each time the number of rt change
        Parameters
        ----------
        all_rt : RotoTransCollection
            One frame of all RotoTrans to draw

        """
        if isinstance(all_rt, RotoTrans):
            rt_tp = RotoTransCollection()
            rt_tp.append(all_rt[:, :])
            all_rt = rt_tp

        if not isinstance(all_rt, RotoTransCollection):
            raise TypeError("Please send a list of rt to new_rt_set")

        # Remove previous actors from the scene
        for actor in self.rt_actors:
            self.parent_window.ren.RemoveActor(actor)
        self.rt_actors = list()

        for i, rt in enumerate(all_rt):
            if rt.get_num_frames() != 1:
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
            self.parent_window.ren.ResetCamera()

        # Set rt orientations
        self.n_rt = all_rt.get_num_rt()
        self.update_rt(all_rt)

    def update_rt(self, all_rt):
        """
        Update position of the RotoTrans on the screen (but do not repaint)
        Parameters
        ----------
        all_rt : RotoTransCollection
            One frame of all RotoTrans to draw

        """
        if isinstance(all_rt, RotoTrans):
            rt_tp = RotoTransCollection()
            rt_tp.append(all_rt[:, :])
            all_rt = rt_tp

        if all_rt.get_num_rt() != self.n_rt:
            self.new_rt_set(all_rt)
            return  # Prevent calling update_rt recursively

        if not isinstance(all_rt, RotoTransCollection):
            raise TypeError("Please send a list of rt to new_rt_set")

        self.all_rt = all_rt

        for i, rt in enumerate(self.all_rt):
            if rt.get_num_frames() != 1:
                raise IndexError("RT should be from one frame only")

            # Update the end points of the axes and the origin
            pts = vtkPoints()
            pts.InsertNextPoint(rt.translation())
            pts.InsertNextPoint(rt.translation() + rt[0:3, 0, :] * self.rt_length)
            pts.InsertNextPoint(rt.translation() + rt[0:3, 1, :] * self.rt_length)
            pts.InsertNextPoint(rt.translation() + rt[0:3, 2, :] * self.rt_length)

            # Update polydata in mapper
            lines_poly_data = self.rt_actors[i].GetMapper().GetInput()
            lines_poly_data.SetPoints(pts)

    def create_global_ref_frame(self):
        """
        Define a new global reference frame set. This function must be called once
        Parameters
        ----------
        global_ref_frame : RotoTrans
            One frame of all RotoTrans to draw

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
        self.parent_window.ren.ResetCamera()
