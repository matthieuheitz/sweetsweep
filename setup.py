#!/usr/bin/env python

# Switch from setup.py to pyproject.toml:
# https://snarky.ca/what-the-heck-is-pyproject-toml/
# https://stackoverflow.com/a/62983901/4195725

# # Old format when not using pyproject.toml
# from setuptools import setup, find_packages
# setup(
#     packages=find_packages()
# )

# This file is still necessary to allow editable installs (pip install -e .)
import setuptools

if __name__ == "__main__":
    setuptools.setup()
