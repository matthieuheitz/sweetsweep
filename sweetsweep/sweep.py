#!/usr/bin/env python3

import os
import time
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
# - result_csv_filename: an optional CSV filename to write individual results of each experiment. Each experiment will
#                        have one row in that CSV. If this is set, then experiment_func must return the results as a
#                        dictionary, with keys being the column names, and values the value of each result for that
#                        experiment. The results are written individually to the file as soon as they are obtained,
#                        so that the file is readable during the sweep.
# - specific_dict: a dictionary containing the swept parameters that are specific to certain values of other
#                  swept parameters. This will avoid computing redundant experiments. Example: if your sweep is
#                  {"alpha":["A","B","C"],"beta":[1,2,3]}, but 'beta' only changes the result of the experiment when
#                  'alpha'="B", then set specific_dict={"beta":{"alpha":"B"}}. This way, the redundant experiments
#                  of different values of 'beta' when 'alpha" = "A" or "C" will not be computed.
# - skip_exps: a dictionary of the sets of experiments to skip. Example: if your sweep is
#              {"alpha":["A","B","C"],"beta":[1,2,3],"gamma"=[0.5,0.6,0.7]}, and you know that "gamma"=0.7 is good for
#              "beta"=1 or 2, but isn't relevant for 3, you can skip it by passing skip_exps={gamma":0.7,"beta":3}
def parameter_sweep(param_dict, experiment_func, sweep_dir, start_index=0, result_csv_filename="", specific_dict=None,
                    skip_exps=None):

    if not param_dict:
        print("The parameter dictionary is empty. Nothing to do.")
        return

    # Set some variables
    csv_path = os.path.join(sweep_dir, result_csv_filename)
    result_list = {}

    # Fill the current_dict and count number of experiments
    current_dict = {}
    num_exp = 1
    for k in param_dict.keys():
        current_dict[k] = param_dict[k][0]
        num_exp *= len(param_dict[k])

    print("\nThere are",num_exp,"experiments in total.\n")
    # if specific_dict:
    #     num_unique_exp = get_num_unique_exp(param_dict,specific_dict)
    #     print("There are %d unique experiments and %d redundant ones"%(num_unique_exp,num_exp-num_unique_exp))

    def recursive_call(exp_id, current_dict, param_index):
        current_key = list(param_dict.keys())[param_index]
        for v in param_dict[current_key]:
            current_dict[current_key] = v
            if param_index != len(param_dict.keys())-1:
                exp_id = recursive_call(exp_id, current_dict, param_index+1)
            else:
                # print("\nExperiment #%d:" % exp_id, current_dict)

                # Check if need to skip this experiment
                if skip_exps and check_skip_exp(current_dict,skip_exps):
                    # print("Skipping")
                    exp_id = exp_id + 1
                    continue

                # Get folder name for that experiment
                exp_dir = os.path.join(sweep_dir, build_dir_name(num_exp, exp_id, current_dict))

                # Check whether this experiment is redundant
                src_exp_id, src_exp_dict = check_exp_redundancy(param_dict, specific_dict, current_dict)

                # If it's redundant, make a symlink to the source experiment directory
                if src_exp_id != -1:
                    # Get the src dir name
                    src_exp_id += start_index   # Apply the index offset
                    src_exp_dir = build_dir_name(num_exp, src_exp_id, src_exp_dict)
                    # Make the symlink
                    os.symlink(src_exp_dir, exp_dir, target_is_directory=True)
                    # Get results from src experiment
                    result_dict = result_list[src_exp_id]

                # Otherwise, run the experiment
                else:
                    # Make the directory
                    os.makedirs(exp_dir, exist_ok=True)
                    # Run the experiment
                    result_dict = experiment_func(exp_id, current_dict, exp_dir)
                    # Store the result
                    result_list[exp_id] = result_dict

                # Add results to the CSV file
                if result_csv_filename:
                    if result_dict:
                        # On first experiment, write the CSV header
                        if exp_id == start_index:
                            # Create the csv file, write the header.
                            with open(csv_path, mode='w') as csv_file:
                                csv_writer = csv.writer(csv_file)
                                csv_writer.writerow(["exp_id","src_exp_id"] + list(param_dict.keys()) + list(result_dict.keys()))

                        # Save additional results by writing them to the CSV
                        with open(csv_path, mode='a') as csv_file:
                            csv_writer = csv.writer(csv_file)
                            csv_row = [exp_id, src_exp_id] + list(current_dict.values())    # Write exp_id and current param values
                            csv_row += list(result_dict.values())   # Write returned data
                            csv_writer.writerow(csv_row)
                    else:
                        print("WARNING: Can't write results to CSV: received 'None' from experiment_func().")

                exp_id = exp_id + 1

        return exp_id

    # Start experiments
    recursive_call(start_index, current_dict, 0)


def get_num_exp(sweep_dict):
    num_exp = 1
    for k in sweep_dict.keys():
        num_exp *= len(sweep_dict[k])
    return num_exp


# def get_num_unique_exp(sweep_dict,specific_dict):
#
#     for param,value_list in sweep_dict.items():
#         if param in specific_dict:
#
#         else:
#             total *= len(value_list)
#
#     return 0


def build_dir_name(n_exp, exp_id, current_dict):
    exp_dir = ("exp_%0" + str(len(str(n_exp))) + "d_") % exp_id
    for k, v in current_dict.items():
        exp_dir += "_" + k + str(v)
    return exp_dir


def get_exp_id(sweep_dict, current_dict):
    if sweep_dict.keys() != current_dict.keys():
        print("ERROR: Dictionaries don't have the same keys. Aborting.")
        exit(-1)
    # Go through the dict in reverse to get number of leaves of the sub-tree
    dict_items = list(current_dict.items())
    dict_items.reverse()
    cum_prod = 1    # Number of leaves in the subtree
    index = 0
    for k,v in dict_items:
        v_index = sweep_dict[k].index(v)
        index += v_index*cum_prod
        cum_prod *= len(sweep_dict[k])
    return index


# Check whether an experiment is redundant or not, based on a specificity dictionary
# If it is, it returns the id and param dictionary of the experiment to copy from
def check_exp_redundancy(sweep_dict, specific_dict, current_dict):

    if not specific_dict:
        return -1, {}

    # Get the list of parameters to change (to the first value of their list) to find the src experiment
    param_change = []
    for k2, v2 in specific_dict.items():
        if not k2 in sweep_dict:
            print("ERROR: parameter '%s' is not in sweep_dict." % k2)
            exit(-1)
        # If the current exp doesn't match the condition, compute only for the first value of the
        # parameter (could be any of them), and for the others, make symbolic links.
        match_condition = True
        for k3, v3 in v2.items():
            if not k3 in sweep_dict:
                print("ERROR: parameter '%s' is not in sweep_dict."%k3)
                exit(-1)
            if not set(v3).issubset(sweep_dict[k3]):
                print("ERROR: some values for '%s' in specific_dict are not in sweep_dict:"%k3)
                print("sweep_dict:", sweep_dict)
                print("specific_dict['%s']:"%k3, v3)
                exit(-1)
            match_condition &= (current_dict[k3] in v3)
            # if current_dict[k3] in v3: print("match condition", k3, "in", v3)
        if current_dict[k2] != sweep_dict[k2][0] and not match_condition:
            param_change.append(k2)
            # print("Symlink", k2)

    # Find the source folder: the one that has the results we would get if we ran this experiment.
    # It's the one for which the params in param_change have the first value of their swept list.
    if param_change:
        src_dict = current_dict.copy()
        for p in param_change:
            src_dict[p] = sweep_dict[p][0]
        src_exp_id = get_exp_id(sweep_dict, src_dict)
        # print("-> symlink to exp #%d"%src_exp_id,":",src_dict)
        return src_exp_id, src_dict
    else:
        return -1, {}


def check_skip_exp(current_dict,skip_exps):

    for condition in skip_exps:
        for k,v in condition.items():
            if current_dict[k] not in v:
                return False
    return True


# Same function as above, except that it runs the sweep with a multiprocessing pool of `max_workers` workers.
# The results are written individually to the CSV file as they are produced, so that it's always readable
# during the sweep
def parameter_sweep_parallel(param_dict, experiment_func, sweep_dir, max_workers=4, start_index=0, result_csv_filename=""):

    import pathos.multiprocessing as mp
    from pathos.helpers import mp as pathos_multiprocess

    if not param_dict:
        print("The parameter dictionary is empty. Nothing to do.")
        return

    # Fill the current_dict and count number of experiments
    current_dict={}
    num_exp = 1
    for k in param_dict.keys():
        current_dict[k] = param_dict[k][0]
        num_exp *= len(param_dict[k])

    print("\nThere are ",num_exp,"experiments in total.\n")

    # Get list of parameter dictionaries (one for each experiment)
    def make_paramdict_list(current_dict, param_index):
        current_key = list(param_dict.keys())[param_index]
        param_dict_list = []
        for v in param_dict[current_key]:
            current_dict[current_key] = v
            if param_index == len(param_dict.keys())-1:
                param_dict_list.append(current_dict.copy())
            else:
                param_dict_list += make_paramdict_list(current_dict, param_index+1)

        return param_dict_list

    paramdict_list = make_paramdict_list(current_dict, 0)

    # Experiment worker
    def run_experiment(exp_id, current_dict, result_queue):
        # Create a folder for that experiment
        exp_dir = os.path.join(sweep_dir, ("exp_%0" + str(len(str(num_exp))) + "d_") % exp_id)
        for k, v in current_dict.items():
            exp_dir += "_" + k + str(v)
        os.makedirs(exp_dir, exist_ok=True)

        # Run the experiment
        result_dict = experiment_func(exp_id, current_dict, exp_dir)

        # Send to queue to write results
        if result_csv_filename:
            if result_dict:
                result_queue.put((exp_id, current_dict, result_dict))
            else:
                print("WARNING: Can't write results to CSV: received 'None' from experiment_func().")

        return result_dict

    # Result writing listener
    def write_results_to_csv(result_queue):

        write_header = True
        # Be careful, i doesn't represent the exp_id, they usually don't terminate in order.
        # It's just because we know we should receive a total of `num_exp` results.
        for i in range(num_exp):
            exp_id, exp_param_dict, result_dict = result_queue.get()

            # Save additional results by writing them to the CSV
            with open(os.path.join(sweep_dir, result_csv_filename), mode='a') as csv_file:
                csv_writer = csv.writer(csv_file)
                # Only on first call received, write the CSV header
                if write_header:
                    csv_writer.writerow(["exp_id"] + list(exp_param_dict.keys()) + list(result_dict.keys()))
                    write_header = False
                # Write the result row
                csv_row = [exp_id] + list(exp_param_dict.values())  # Write exp_id and current param values
                csv_row += list(result_dict.values())  # Write returned data
                csv_writer.writerow(csv_row)

    # Must use Manager queue here, or will not work
    manager = pathos_multiprocess.Manager()
    queue = manager.Queue()

    # Run experiments
    t0 = time.time()
    with mp.Pool(max_workers) as pool:
        # Put listener to work first
        watcher = pool.apply_async(write_results_to_csv, (queue,))
        # Spawn workers
        pool.starmap(run_experiment, zip(range(start_index,num_exp+start_index), paramdict_list, [queue]*num_exp))

    print("Time taken to run all experiments:",time.time()-t0)
