#!/usr/bin/env python3

# This example demonstrates how to ask sweetsweep to only run one of the experiments.
# This is useful when running an array job in an HPC cluster, as each job of the array will call the same script with one index integer parameter changing.
# An example of how to run array jobs on the Alliance Canada HPC cluster can be found here: https://docs.alliancecan.ca/wiki/Job_arrays
# You can pass the array job index to this script using '--only-exp-id N'. The code below processes it, and will run only the corresponding experiment.
# It's also useful to call this script beforehand with '--get-num-exp', to obtain the number of array jobs that will be submitted, and not entering it manually.

import os
import sys
import math
import json
import matplotlib.pyplot as plt
import time

import sweetsweep


# Create the dictionary of values to sweep for each parameter
# For example:
param_sweep = {}
param_sweep["alpha"] = [5, 10, 15]
param_sweep["beta"] = [0.1, 0.2, 0.5]
param_sweep["gamma"] = ["Red", "Blue"]

## ------------------------------------
# Process argv parameters

# Don't print anything before this line
if '--get-num-exp' in sys.argv:
    print(sweetsweep.get_num_exp(param_sweep))
    exit()

only_exp_id = None
if '--only-exp-id' in sys.argv:
    only_exp_id = int(sys.argv[sys.argv.index('--only-exp-id')+1])

## ------------------------------------


my_sweep_dir = "my_sweep"   # Default output dir
# Main folder for the sweep
if '-o' in sys.argv:
    my_sweep_dir = sys.argv[sys.argv.index('-o')+1]
if '--outdir' in sys.argv:
    my_sweep_dir = sys.argv[sys.argv.index('--outdir')+1]
os.makedirs(my_sweep_dir, exist_ok=True)


# Name of the image to save
image_filename = "image.png"
# Name of the csv file to save (one row per experiment)
csv_filename = "results.csv"

# Save the param_sweep file
params = param_sweep.copy()
# Add parameters for the viewer if you need (see README.md)
params["viewer_filePattern"] = image_filename
# params["viewer_cropLBRT"] = [0, 0, 0, 0]
params["viewer_resultsCSV"] = csv_filename
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

    t0 = time.time()

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

    total_time = time.time() - t0

    # Return additional results as a dictionary, where keys will be the corresponding columns in the CSV.
    # Return the results either as their original dtype, or as how you want them to appear in the viewer:
    # return {"sum_x": sum(x), "mean_x": sum(x)/len(x), "max_x": max(x)}
    return {"time": "%0.2g"%total_time,
            "sum_x": "%0.2g"%sum(x),
            "mean_x": "%0.2g"%(sum(x)/len(x)),
            "max_x": "%0.2g"%max(x)}


# Run the sweep, the function creates and fills the CSV for you
sweetsweep.parameter_sweep(param_sweep, my_experiment, my_sweep_dir, result_csv_filename=csv_filename, only_exp_id=only_exp_id)
