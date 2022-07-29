import biorbd


class BiorbdUtils:
    @staticmethod
    def get_marker_names(model: biorbd.Model):
        return tuple(name.to_string() for name in model.markerNames())


class Ezc3dUtils:
    @staticmethod
    def get_point_names():
        pass
