#!/usr/bin/env python

from setuptools import setup

setup(
    name="dyli",
    version="0.0.0",
    author='Ross Fenning',
    author_email='Ross.Fenning@gmail.com',
    packages=['dyli'],
    description='Do you like it?',
    url='http://github.com/avengerpenguin/dyli',
    install_requires=['flask', 'flask-sqlalchemy', 'flask_rdf', 'rdflib'],
    setup_requires=['pytest-runner',],
    tests_require=['pytest', 'httpretty', 'hyperspace'],
)
