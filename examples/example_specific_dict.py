#!/usr/bin/env python3

# This example demonstrates how to use the specific_dict and skip_exps parameters of sweetsweep.
# Since some experiments are redundant (in this case the pairs of experiments for the 2 values of 'marker', when plot_type=="plot"), their results will be exactly the same.
# So sweetsweep only runs one of them (the first one) and creates a symlink to it for the subsequent redundant ones. 
# This can save a lot of disk space and also means that the user experience in the viewer will be better, because it will display the results, even for the redundant experiments
# Finally, in the CSV result file, the results are redundant and are not repeated. Instead, the second column called "src_exp_id" is -1 for non-redundant experiments, 
# and gives the exp_id for which the results are the same, for redundant experiments.

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
param_sweep["plot_type"] = ['plot', 'scatter']
param_sweep["marker"] = ['T', 'O']

# This command should be read as: "The parameter 'marker' is specific to 'plot_type' having the value 'scatter'."
specific_dict = {"marker": {'plot_type': 'scatter'}}
# This command should be read as: "Skip the experiment where alpha=5 and beta=0.5".
# None of the folders for experiments matching these values will be created.
# The viewer will show errors in the log, but they can be ignored.
skip_exps = {'alpha': 5, "beta": 0.5}


my_sweep_dir = "my_sweep_with_specific_dict"   # Default output dir
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
    if param_dict["plot_type"] == 'plot':
        plt.plot(x)
    if param_dict["plot_type"] == 'scatter':
        if param_dict["marker"] == "T":
            marker = "^"
        if param_dict["marker"] == "O":
            marker = "o"
        plt.scatter(range(100), x, marker=marker)

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


# Run the sweep
sweetsweep.parameter_sweep(param_sweep, my_experiment, my_sweep_dir, result_csv_filename=csv_filename, skip_exps=skip_exps, specific_dict=specific_dict)
# sweetsweep.parameter_sweep_parallel(param_sweep, my_experiment, my_sweep_dir, result_csv_filename=csv_filename)

# The parameter_sweep_parallel doesn't yet support skip_exps and specific_dict.
