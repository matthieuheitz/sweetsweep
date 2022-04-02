#!/usr/bin/env python3

import os
import math
import json
import matplotlib.pyplot as plt

import sweetsweep

# Create the dictionary of values to sweep for each parameter
# For example:
param_sweep = {}
param_sweep["alpha"] = [5, 10, 15]
param_sweep["beta"] = [0.1, 0.2, 0.5]
param_sweep["gamma"] = ["Red", "Blue"]

# Main folder for the sweep
my_sweep_dir = "./my_sweep"
os.makedirs(my_sweep_dir, exist_ok=True)

# Name of the image to save
image_filename = "image.png"


# Save the param_sweep file
params = param_sweep.copy()
# Add parameters for the viewer if you need (see README.md)
params["viewer_filePattern"] = image_filename
# params["viewer_cropLBRT"] = [0, 0, 0, 0]
json.dump(params, open(os.path.join(my_sweep_dir, "sweep.txt"), "w"))


# Create the function for the experiment.
# The sweep.parameter_sweep() will call it with the following arguments:
# - exp_id: the experiment index (integer)
# - param_dict: a dictionary containing the parameters of the current experiment
# - exp_dir: the experiment directory, where you can save your output
def my_experiment(exp_id, param_dict, exp_dir):

    print("Experiment #%d:"%exp_id, param_dict)

    # #########################
    # Run your experiment here
    # #########################

    # Access the parameters with:
    # param_dict["alpha"]
    # param_dict["beta"]
    # ...

    x = [math.sin(param_dict["beta"]*i-param_dict["alpha"]) for i in range(100)]

    # ################
    # Save the output
    # ################

    # Save the image you want to see in the viewer using `image_filename`
    # For example:
    plt.figure(figsize=(10, 10))
    plt.plot(x, c=param_dict["gamma"])
    plt.savefig(os.path.join(exp_dir, image_filename), bbox_inches="tight")
    plt.close()


# Run the sweep
sweetsweep.parameter_sweep(param_sweep, my_experiment, my_sweep_dir)
