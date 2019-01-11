from .fileio import *
from .mesh import *
from .verif import *
from .vtk import *

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions
