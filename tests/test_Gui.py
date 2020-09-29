import biorbd

from bioviz import Viz


def test_model_load():
    model_path = "examples/pyomecaman.s2mMod"

    # From path
    b1 = Viz(model_path=model_path, show_muscles=False, show_meshes=False)

    # From a loaded model
    m = biorbd.s2mMusculoSkeletalModel(model_path)
    b1 = Viz(loaded_model=m, show_muscles=False, show_meshes=False)
