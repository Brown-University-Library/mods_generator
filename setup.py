from setuptools import setup, find_packages

setup(name='mods_generator',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'bdrxml @ https://github.com/Brown-University-Library/bdrxml/archive/v0.9.zip#sha1=9eeff5ed1435dac16795d54680112e15ba3bb485',
        'xlrd==1.1.0',
    ]
)

