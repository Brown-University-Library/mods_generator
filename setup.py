from setuptools import setup, find_packages

setup(name='mods_generator',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'bdrxml',
        'xlrd',
    ]
)

