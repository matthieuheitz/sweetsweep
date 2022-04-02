#!/usr/bin/env python
# coding: utf-8

import os
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import sweetsweep
import json

matplotlib.use("Agg")


my_sweep_dir = "../test-sweep-specific-dict"
os.makedirs(my_sweep_dir, exist_ok=True)


# Parameter dictionary
param_sweep = {}

# Test parameters
# all_param_dict["T"] = [2,4]  # number of timepoints
param_sweep["D"] = ["SA","SB","MA","MB"]
param_sweep["E"] = [0.1,0.2,0.3]  # entropic regularization
param_sweep["N"] = [5,10]

# Test different specific dicts
# specific_dict = {"N": {"D": ["MAB"]}}
# specific_dict = {"E": {"D": ["SA","SB","MA","MB"]}}
specific_dict = {"E": {"D": ["SA","SB"]}}
# specific_dict = {"E": {"D": ["SA","SB",]},"N": {"D": ["MA"]}}
# specific_dict = {"E": {"D": ["SA","SB",], "T": [4]},"N": {"D": ["MA"]}}
# specific_dict = {"E": {"D": ["SA"]},"N": {"D": ["MA"]}}
# specific_dict = {"E": {"D": ["SA","SB","MA","MB"]},"N": {"D": ["MA"]}}
# specific_dict = {"E": {"N": [10]}}

skip_exps = []
skip_exps.append({"N":[10], "E":[0.2,0.3]})


json.dump(param_sweep, open(os.path.join(my_sweep_dir, "sweep.txt"), "w"))


def test(exp_id, exp_param_dict, exp_dir):

    with open(os.path.join(exp_dir,"exp-%d"%exp_id),'w') as f:
        f.write(str(exp_param_dict))

    n = 5
    plt.figure()
    plt.imshow(np.random.randint(0,2,n**2).reshape(n,n))
    plt.tight_layout()
    plt.savefig(os.path.join(exp_dir,"test.png"))
    plt.close()

    return {"time": "%0.2g"%np.random.rand(),
            "b": np.random.rand(),
            }
    # print("Experiment #%d:"%exp_id, exp_param_dict)


sweetsweep.parameter_sweep(param_sweep, test, my_sweep_dir, start_index=0, result_csv_filename="results.csv",
                      specific_dict=specific_dict, skip_exps=skip_exps)
