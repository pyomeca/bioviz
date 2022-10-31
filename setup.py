from setuptools import setup

setup(
    name="bioviz",
    description="Biorbd Vizualization ToolKit",
    author="Pariterre",
    author_email="pariterre@hotmail.com",
    url="https://github.com/pyomeca/biorbd-viz",
    license="Apache 2.0",
    packages=["bioviz", "bioviz/analyses", "bioviz/qt_ui"],
    package_data={"": ["ressources/*.png"]},
    keywords="bioviz",
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)
