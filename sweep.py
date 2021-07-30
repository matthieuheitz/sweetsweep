#!/usr/bin/env python3

import os


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
def parameter_sweep(param_dict, experiment_func, sweep_dir, start_index=0):

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
                if sweep_dir:
                    # Create a folder for that experiment
                    exp_dir = os.path.join(sweep_dir, ("exp_%0"+str(len(str(num_exp)))+"d_")%exp_id)
                    for k, v in current_dict.items():
                        exp_dir += "_" + k + str(v)
                    os.makedirs(exp_dir, exist_ok=True)

                    experiment_func(exp_id, current_dict, exp_dir)
                else:
                    experiment_func(exp_id, current_dict)

                exp_id = exp_id + 1

        return exp_id

    recursive_call(start_index, current_dict, 0)
