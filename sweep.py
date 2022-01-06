#!/usr/bin/env python3

import os
import time
import csv
import pathos.multiprocessing as mp
from pathos.helpers import mp as pathos_multiprocess



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
def parameter_sweep(param_dict, experiment_func, sweep_dir, start_index=0, result_csv_filename=""):

    if not param_dict:
        print("The parameter dictionary is empty. Nothing to do.")
        return

    # Fill the current_dict and count number of experiments
    current_dict={}
    num_exp = 1
    for k in param_dict.keys():
        current_dict[k] = param_dict[k][0]
        num_exp *= len(param_dict[k])

    print("\nThere are a total of",num_exp,"experiments.\n")

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
                            # Create the csv file, write the header.
                            with open(os.path.join(sweep_dir, result_csv_filename), mode='w') as csv_file:
                                csv_writer = csv.writer(csv_file)
                                csv_writer.writerow(["exp_id"] + list(param_dict.keys()) + list(result_dict.keys()))

                        # Save additional results by writing them to the CSV
                        with open(os.path.join(sweep_dir, result_csv_filename), mode='a') as csv_file:
                            csv_writer = csv.writer(csv_file)
                            csv_row = [exp_id] + list(current_dict.values())    # Write exp_id and current param values
                            csv_row += list(result_dict.values())   # Write returned data
                            csv_writer.writerow(csv_row)
                    else:
                        print("WARNING: Can't write results to CSV: received 'None' from experiment_func().")

                exp_id = exp_id + 1

        return exp_id

    # Start experiments
    recursive_call(start_index, current_dict, 0)






# Same function as above, except that it runs the sweep with a multiprocessing pool of `max_workers` workers.
# The results are written individually to the CSV file as they are produced, so that it's always readable during the sweep
def parameter_sweep_parallel(param_dict, experiment_func, sweep_dir, max_workers=4, start_index=0, result_csv_filename=""):

    if not param_dict:
        print("The parameter dictionary is empty. Nothing to do.")
        return

    # Fill the current_dict and count number of experiments
    current_dict={}
    num_exp = 1
    for k in param_dict.keys():
        current_dict[k] = param_dict[k][0]
        num_exp *= len(param_dict[k])

    print("\nThere are a total of",num_exp,"experiments.\n")

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