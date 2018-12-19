import yaml
from setuptools import setup

with open("env.yml", 'r') as stream:
    out = yaml.load(stream)
    requirements = out['dependencies'][1:]  # we do not return python

setup(
    name='pyoviz',
    version='2018.1',
    description="Pyomeca visualization toolkit",
    author="Romain Martinez",
    author_email='martinez.staps@gmail.com',
    url='https://github.com/pyomeca/pyomeca',
    license='Apache 2.0',
    packages=['pyoviz'],
    install_requires=requirements,
    keywords='pyoviz',
    classifiers=[
        'Programming Language :: Python :: 3.6',
	'Programming Language :: Python :: 3.7',
    ]
)
