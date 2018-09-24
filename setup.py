from setuptools import setup

# to install dependencies in a clean conda env, run: `conda env create -f env.yml`

requirements = []

setup(
    name='pyoviz',
    version='0.1.1',
    description="Toolbox for biomechanics analysis",
    author="Romain Martinez & Pariterre",
    author_email='',
    url='https://github.com/pyomeca/pyoviz',
    license='Apache 2.0',
    packages=['pyoviz'],
    install_requires=requirements,
    keywords='pyoviz',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ]
)

# TODO: update requirements