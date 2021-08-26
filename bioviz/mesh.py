import numpy as np
from pyomeca.markers import Markers


class Mesh(Markers):
    def __new__(
        cls,
        vertex=None,
        triangles=np.ndarray((3, 0)),
        **kwargs,
    ):
        if isinstance(triangles, list):
            triangles = np.array(triangles)

        s = triangles.shape
        if s[0] != 3:
            raise NotImplementedError("Mesh only implements triangle connections")

        # If triangle is empty, join lines in order
        automatic_triangles = False
        if s[1] == 0 and vertex.shape[1] > 0:
            automatic_triangles = True
            triangles = np.ndarray((3, vertex.shape[1] - 1), dtype="int")
            for i in range(vertex.shape[1] - 1):
                triangles[:, i] = [i, i + 1, i]

        attrs = {"triangles": triangles, "automatic_triangles": automatic_triangles}
        return Markers.__new__(cls, vertex, None, None, attrs=attrs, **kwargs)
