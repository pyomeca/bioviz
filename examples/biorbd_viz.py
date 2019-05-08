# """
# Example script for animating a model
# """

import numpy as np

from pyoviz.BiorbdViz import BiorbdViz

b = BiorbdViz(model_path="pyomecaman.s2mMod")
animate_by_hand = False

if animate_by_hand:
    n_frames = 200
    Q = np.zeros((n_frames, b.nQ))
    Q[:, 4] = np.linspace(0, np.pi/2, n_frames)
    i = 0
    while b.vtk_window.is_active:
        b.set_q(Q[i, :])
        i = (i+1) % n_frames
else:
    b.exec()
