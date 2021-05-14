# SweetSweep
Qt application to quickly visualize results from parameter sweeps

![application screenshot](./screenshots/app.png)

## Quick start

You can use this app if the output folders of your parameter sweep are
named using their respective parameter values, like so:
```
$ ls results/
results_Example_reprog_sig0.05_ab0.05_multistart100/
results_Example_reprog_sig0.05_ab0.05_multistart200/
results_Example_reprog_sig0.05_ab0.1_multistart100/
results_Example_reprog_sig0.05_ab0.1_multistart200/
results_Example_reprog_sig0.05_ab0.2_multistart100/
results_Example_reprog_sig0.05_ab0.2_multistart200/
results_Example_reprog_sig0.05_ab0.3_multistart100/
results_Example_reprog_sig0.05_ab0.3_multistart200/
results_Example_reprog_sig0.1_ab0.05_multistart100/
results_Example_reprog_sig0.1_ab0.05_multistart200/
results_Example_reprog_sig0.1_ab0.1_multistart100/
results_Example_reprog_sig0.1_ab0.1_multistart200/
results_Example_reprog_sig0.1_ab0.2_multistart100/
results_Example_reprog_sig0.1_ab0.2_multistart200/
results_Example_reprog_sig0.1_ab0.3_multistart100/
results_Example_reprog_sig0.1_ab0.3_multistart200/
sweep.txt
```

You also need to specify a configuration file `sweep.txt` that describes each
parameter and its values, as a json file:
```
$ cat results/sweep.txt
{
"sig": [0.05,0.1],
"ab": [0.05,0.1,0.2,0.3],
"multistart": [100,200]
}
```
Let's say that each directory contains a file `iter_001_insertion.png`,
and you want to compare the results in this file depending on the parameters.

This app allows you to:
- quickly visualize individual files, and easily switch between
parameter values
- visualize grids of the results with varying parameters in the X and Y axis
- save those visualizations to file


### Config file

- You can input the config file path manually, or if there is a `sweep.txt`
  file in the main folder, it will be loaded automatically.
- The parameter values don't have to be numerical, they can be anything as 
  long as their `str()` representation is unique: `bool, int, str`, etc.
- You can also add the meta parameter `viewer_cropLBRT` in this config file,
  e.g.: `"viewer_cropLBRT": [35,40,30,15],` and the application will load 
  these values for cropping images (LBRT: Left,Bottom,Right,Top).

### Miscellaneous

- The app can access mounted folders, which is great to avoid copying to your
  computer all result folders from the server on which you ran the sweep.
  I only tried on Linux with a folder mounted with `sftp`, in which case the URL
  you need to provide is:
  `/run/user/$uid/gvfs/sftp:host=<host>,user=<user>/path/to/folder`.
  Replace `<host>` by the host name, `<user>` by your username, `$uid` by
  your user id, which you can get by running `id -u` (it is `1000` if you are the
  only user on your system), and `path/to/folder` by the path to the remote folder.
