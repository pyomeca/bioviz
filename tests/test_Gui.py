import os

import biorbd
from bioviz import Viz


def get_base_folder():
    """
    Return the base folder path (one level up from the tests folder)
    """
    return f"{os.path.join(os.path.dirname(os.path.abspath(__file__)))}/.."


def test_model_load():
    model_path = f"{get_base_folder()}/examples/pyomecaman.bioMod"

    # From path
    b1 = Viz(model_path=model_path)

    # From a loaded model
    m = biorbd.Model(model_path)
    b2 = Viz(loaded_model=m)
