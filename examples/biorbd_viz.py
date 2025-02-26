# """
# Example script for animating a model
# """

from enum import Enum, auto
import os

import numpy as np
from bioviz import Viz


class AnimBy(Enum):
    MANUAL = auto()
    AUTOMATIC = auto()
    NO_ANIMATION = auto()


def main(anim_by: AnimBy):
    b = Viz(model_path=f"{os.path.dirname(__file__)}/pyomecaman.bioMod")

    if anim_by == AnimBy.MANUAL:
        n_frames = 200
        Q = np.zeros((b.nQ, n_frames))
        Q[4, :] = np.linspace(0, np.pi / 2, n_frames)
        i = 0
        while b.vtk_window.is_active:
            b.set_q(Q[:, i])
            i = (i + 1) % n_frames
    elif anim_by == AnimBy.AUTOMATIC:
        n_frames = 200
        all_q = np.zeros((b.nQ, n_frames))
        all_q[4, :] = np.linspace(0, np.pi / 2, n_frames)
        b.load_movement(all_q)
        b.exec()
    elif anim_by == AnimBy.NO_ANIMATION:
        b.exec()
    else:
        raise NotImplementedError("anim_by not implemented")


if __name__ == "__main__":
    main(AnimBy.AUTOMATIC)
