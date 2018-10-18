from setuptools import setup, find_packages

setup(name='mods_generator',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'bdrxml==0.9',
        'xlrd==1.1.0',
    ]
    dependency_links=[
        'https://github.com/Brown-University-Library/bdrxml/archive/v0.9.zip#egg=bdrxml-0.9',
    ],
)

