from .sweep import parameter_sweep, parameter_sweep_parallel, get_num_exp

# Define version here
__version__ = '0.1.5'


# Command reminder for building the package
# For upload with twine, username and passord are already stored in ~/.pypirc
# python3 -m build
# python3 -m twine upload --skip-existing dist/*
