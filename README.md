# prepare_windows

This script prepares umbrella sampling windows from an arbitrary number of pulling trajectories. Basic validation of the mdp file and ndx files provided is also performed. Requires Gromacs to run.

The script requires config file (`prepare_windows.config`) specifying options for the script. It is recommended to add `prepare_windows` to a directory in your PATH environment variable.

See `example_windows.txt` for the required format of the 'window_list' file specifying umbrella sampling windows.
See `example_umbrella.mdp` for an example of source umbrella sampling mdp file that can be used by the script.

Disclaimer: designed for the specific needs of the RoVa research group.