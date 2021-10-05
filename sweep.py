#!/usr/bin/env python3

import os
import csv


# This function performs a parameter sweep.
# It calls `experiment_func` with all combinations of possible parameter values listed in `param_dict`.
# - param_dict: `dict` where each (key,value) is respectively:
#                   - the parameter name
#                   - a `list` of all values (can be numbers, strings, booleans, etc.) to sweep for that parameter
# - experiment_func: a functor that takes as argument :
#                    - an experiment index (int)
#                    - a dictionary with a single value for each parameter.
#                    - if `sweep_dir` is not empty, a path to the experiment directory
# - sweep_dir: the main directory in which to store all the experiment directories
# - start_index: optional argument that sets the first experiment ID.
# - result_csv_filename: a optional CSV filename to write individual results of each experiment. Each experiment will
#                        have one row in that CSV. If this is set, then experiment_func must return the results as a
#                        dictionary, with keys being the column names, and values the value of each result for that
#                        experiment.
def parameter_sweep(param_dict, experiment_func, sweep_dir, start_index=0, result_csv_filename=""):

    if result_csv_filename:
        # Create the csv file
        csv_file = open(os.path.join(sweep_dir, result_csv_filename), mode='w')
        csv_writer = csv.writer(csv_file)
    else:
        csv_writer = None

    # Fill the current_dict and count number of experiments
    current_dict={}
    num_exp = 1
    for k in param_dict.keys():
        current_dict[k] = param_dict[k][0]
        num_exp *= len(param_dict[k])

    def recursive_call(exp_id, current_dict, param_index):
        current_key = list(param_dict.keys())[param_index]
        for v in param_dict[current_key]:
            current_dict[current_key] = v
            if param_index != len(param_dict.keys())-1:
                exp_id = recursive_call(exp_id, current_dict, param_index+1)
            else:
                # Create a folder for that experiment
                exp_dir = os.path.join(sweep_dir, ("exp_%0"+str(len(str(num_exp)))+"d_")%exp_id)
                for k, v in current_dict.items():
                    exp_dir += "_" + k + str(v)
                os.makedirs(exp_dir, exist_ok=True)

                # Run the experiment
                result_dict = experiment_func(exp_id, current_dict, exp_dir)

                if result_csv_filename:
                    if result_dict:
                        # On first experiment, write the CSV header
                        if exp_id == start_index:
                            csv_writer.writerow(["exp_id"] + list(param_dict.keys()) + list(result_dict.keys()))

                        # Save additional results by writing them to the CSV
                        csv_row = [exp_id] + list(current_dict.values())    # Write exp_id and current param values
                        csv_row += list(result_dict.values())   # Write returned data
                        csv_writer.writerow(csv_row)
                    else:
                        print("WARNING: Can't write results to CSV: received 'None' from experiment_func().")

                exp_id = exp_id + 1

        return exp_id

    # Start experiments
    recursive_call(start_index, current_dict, 0)

    # Close CSV file if necessary
    if result_csv_filename:
        csv_file.close()
