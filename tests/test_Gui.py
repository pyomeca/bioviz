import pathlib

import biorbd
from bioviz import Viz


def get_test_folder():
    return pathlib.Path(__file__).parent.resolve()


def test_model_load():

    model_path = f"{get_test_folder()}/../examples/pyomecaman.bioMod"

    # From path
    b1 = Viz(model_path=model_path)

    # From a loaded model
    m = biorbd.Model(model_path)
    b2 = Viz(loaded_model=m)
