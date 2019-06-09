import biorbd

from BiorbdViz import BiorbdViz

def test_model_load():
    model_path = "examples/pyomecaman.s2mMod"

    # # From path
    # b1 = BiorbdViz(model_path=model_path, show_muscles=False, show_meshes=False)
    # 
    # # From a loaded model
    # m = biorbd.s2mMusculoSkeletalModel(model_path)
    # b1 = BiorbdViz(loaded_model=m, show_muscles=False, show_meshes=False)
