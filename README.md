# `bioviz`
`bioviz` is the Python visualizer of the `biorbd` biomechanical library (https://github.com/pyomeca/biorbd). 
This library provides filters and analyses for biomechanical data in C++, Python and MATLAB languages.

However, there is no built-in visualization system, therefore this Python module! 
It allow for a beautiful, yet simplistic visualization of the model in static or dynamic poses. 

So, without further ado, let's remove `biorbd` from the darkness!

# How to install
There are two main ways to install `bioviz` on your computer: installing the binaries from Anaconda (easiest) or installing from the sources (requires to download the sources)

## Anaconda (For Windows, Linux and Mac)
The easiest way to install `bioviz` is to download the binaries from Anaconda (https://anaconda.org/) repositories. The project is hosted on the conda-forge channel (https://anaconda.org/conda-forge/bioviz).

After having installed properly an anaconda client [my suggestion would be Miniconda (https://conda.io/miniconda.html)] and loaded the desired environment to install `biorbd` in, just type the following command:
```bash
conda install -c conda-forge bioviz
```
Please note that this will install all the dependencies of `bioviz` *including* `biorbd`. If you are a developer of `biorbd`, this is therefore not the prefered method of installation since the `biorbd` binaries from conda-forge may interfere with those you create. 

## Installing from the sources
To install from the sources, you simply have to download the source, navigate to the root folder and (assuming your conda environment is loaded if neede) type the following command
```bash
python setup.py install
```
Please note that this method will not install the dependencies for you, therefore you will have to install them manually, *including* `biorbd`. Moreover, the *setuptools* dependencies must be installed prior to the installation in order for it to work.

## Dependencies
`bioviz` relies on several libraries. The most obvious one is `biorbd`, but *pyomeca* is also requires and some others. The first hand dependencies (meaning that some dependencies may require other libraries themselves) are: pandas (https://pandas.pydata.org/), numpy (https://numpy.org/), scipy (https://scipy.org/), matplotlib (https://matplotlib.org/), vtk (https://vtk.org/), PyQt (https://www.riverbankcomputing.com/software/pyqt), biorbd (https://github.com/pyomeca/biorbd), pyomeca (https://github.com/pyomeca/pyomeca) and ezc3d (https://github.com/pyomeca/ezc3d). All these can manually be install using (assuming the anaconda environment is loaded if needed) `pip3` command or the Anaconda's following command.
```bash
conda install pandas numpy scipy matplotlib vtk pyqt biorbd pyomeca ezc3d -cconda-forge
```

# How to use
`bioviz` is being as minimalistic as possible in order to make it easy to use. Basically, one has to  `import` the library, load the model and you are good to go. The following code shows how to launch the software without any other options.
```Python
import bioviz
bioviz.Viz('path/to/model.bioMod').exec()
```
Please note that the `exec()` method won't return the hand until the window is closed. If for some reasons, one wants to keep control of the code, they can manually update the GUI using the following snippet. The while loop will then exit when the window is closed. 

```Python
import bioviz
biorbd_viz = bioviz.Viz('path/to/model.bioMod')
while biorbd_viz.vtk_window.is_active:
    # Do some stuff...
    biorbd_viz.refresh_window()
```

## Interacting with the model

The interaction with the model is fairly easy. Using the sliders on the left hand side of the main window, you can change the position of the model, according to the degrees-of-freedom the model has. Pressing the reset button replaces the model at its default attitude. 

## Options at loading
If you are interacting with the model using `biorbd`, you may want to link that model you are interacting with and the one used by `bioviz`. To do so, you can actually pass the model using the `loaded_model` parameter of the constructor, like so.
```Python
import biorbd
import bioviz
model = biorbd.Model('path/to/model.bioMod')
# Do some stuff with you model...
bioviz.Viz(loaded_model=model).exec()
```

The element that are shown on the model can be turned *off* at the loading of the window. The elements are: the *mesh of the segments*, the *global/segments center of mass*, the *global/segments reference frame*, the *skin markers*, the *muscles*, the *analyses panel*. The following code turns everything *off*, which is a bit useless since nothing will be shown.
```Python
import bioviz
bioviz.Viz('path/to/model.bioMod', 
    show_meshes=False,
    show_global_center_of_mass=False, show_segments_center_of_mass=False,
    show_global_ref_frame=False, show_local_ref_frame=False, 
    show_markers=False, 
    show_muscles=False, 
    show_analyses_panel=False
).exec()
```

## Loading a movement

### From the GUI

For loading a movement that the model will perform, one has simply to click on the *Load movement* button and load the previously save movement file. The file must be a numpy array of $n_{Frames} \times n_{DoF}$ matrix.

### From the command line

A second method of attaching a movement to the model is to manually attach it to the GUI. To do so, one simply has to call the `load_movement` function then either call the `exec` function, or manually update the GUI. The following code shows these two different methods (depending if `manually_animate` is set to `True` or `False`. Please note that the `exec()` way is preferred. 

```Python
import numpy as np
import bioviz
manually_animate = False

# Load the model
biorbd_viz = bioviz.Viz('path/to/model.bioMod')

# Create a movement 
n_frames = 200
all_q = np.zeros((n_frames, biorbd_viz.nQ))
all_q[:, 4] = np.linspace(0, np.pi / 2, n_frames)

# Animate the model
if manually_animate:
    i = 0
    while biorbd_viz.vtk_window.is_active:
        biorbd_viz.set_q(all_q[i, :])
        i = (i+1) % n_frames
else:
    biorbd_viz.load_movement(all_q)
    biorbd_viz.exec()

```

## Analyses panel

Slowly but surely, it is plan that the visualizer will become a proper GUI of `biorbd`, allowing for instance to interactively modify a *bioMod* file or to perform biomechanical analyses. For now, there is one muscle analyses panel which is available. 

### Muscle analyses panel
By clicking on *Muscles* in the *Analyses* pane, the main window should expand showing a simple muscle analyses panel. In this panel you can select the muscle to plot and the DoF (degree-of-freedom) to run the analyses on. By default, the analyses are perform from $-\pi$ to $\pi$. The vertical bar shows the current position of the model. Changing the position's slider will automatically update the plots of the analyses. 

The *muscle length* plot shows the length of the muscle over the range of the select DoF assuming every other DoFs are constant. 

The *moment arm* plot shows the moment arm about the selected DoF over the range of the selected DoF assuming every other DoFs are constant.

The *passive forces* plot shows the forces of the passive element of the muscle (assuming there are passive elements) over  the range of the selected DoF assuming every other DoFs are constant.

Finally, the *active forces* plot shows the forces of the active element of the muscle (assuming there as active elements) over  the range of the selected DoF assuming every other DoFs are constant. Just next to the plot, there is a slider that activate the muscle (from 0% to 100% activation).

# How to contribute

You are very welcome to contribute to the project! There are to main ways to contribute. 

The first way is to actually code new features for `bioviz` such as new analyses modules. The easiest way to do so is to fork the project, make the modifications and then open a pull request to the main project. 

The second way is to open issues to report bugs or to ask for new features. I am trying to be as reactive as possible, so don't hesitate to do so!

# Cite
If you use `biorbd` (or its GUI `bioviz`), we would be grateful if you could cite it as follows:

```
@misc{Michaud2018biorbdViz,
    author = {Michaud, Benjamin and Begon, Mickael},
    title = {bioviz: A vizualization python toolbox for biorbd},
    howpublished={Web page},
    url = {https://github.com/pyomeca/bioviz},
    year = {2018}
}
```
