from pathlib import Path

import matplotlib.pyplot as plt

from pyosim import Analogs3dOsim


class Verification:

    def __init__(self):
        # TODO:
        # interp
        # select indexes
        # export to csv
        # style
        pass


if __name__ == '__main__':
    DATA_PATH = Path('/home/romain/Downloads/results/mars/1_inverse_kinematic')

    x = [Analogs3dOsim().from_mot(i) for i in DATA_PATH.glob('*.mot')]
    for i in x:
        i.plot()
        plt.show()
