"""
This script prepares umbrella sampling windows from arbitrary pulling trajectories.
Only works for 1D collective variables.
Contact: Ladislav Bartos | ladmeb@gmail.com
Released under MIT License.
"""

# @@@@@@@@@@@@@@@@@@@@@@@@
# @       OPTIONS        @
# @@@@@@@@@@@@@@@@@@@@@@@@

# version of gromacs to activate using the Infinity modules
GROMACS_VERSION = "gromacs:2021.4-plumed"


# <<<<PULLING FILES>>>>
# the script assumes that all files from the different pulling simulations
# are named correspondingly and are just located in different directories

# name of the file containing values of the collective variable captured during the pulling simulation
PULL_X     = "pulling_pullx.xvg"

# name of the .mdp file used for pulling simulations
PULL_MDP   = "pulling.mdp"

# name of the .tpr file used for pulling simulations
PULL_TPR   = "pulling.tpr"

# name of the .xtc file from the pulling simulations
PULL_XTC   = "pulling.xtc"

# name of the topology file of the system
SYSTEM_TOP = "system.top"

# name of the index file of the system
SYSTEM_NDX = "index.ndx"

# names of additional files that should be copied from 
# the pulling directories into individual umbrella sampling windows
# leave empty ([]) if not needed
PULL_ADDITIONAL = ["reference.gro"]



# <<<<UMBRELLA INPUT FILES>>>>

# path to the "window list" with definitions of individual umbrella sampling windows
# NOTE that "window list" must follow the correct format (REFERENCE_VALUE FORCE_CONSTANT WINDOW_ORIGIN)
WINDOW_LIST = "example_windows.txt"

# path to the .mdp file used for umbrella sampling windows
# note that in the mdp file:
# a) "[FORCE_CONSTANT]" and "[K_CONST]" (for backwards compatibility) 
#    will be replaced with the FORCE_CONSTANT specified for the target window
# b) "[REFERENCE_VALUE]" and "[INIT_DIST]" (for backwards compatibility)
#    will be replaced with the REFERENCE_VALUE specified for the target window 
# c) "[PULL_GROUP_1/2]" will be replaced with the PULL_GROUP specified for the target set of umbrella windows
UMBRELLA_MDP = "example_umbrella.mdp"

# name of the run script for umbrella sampling
UMBRELLA_RUN = "precycle_md_dim"

# paths to additional files that should be copied into the individual umbrella sampling windows
UMBRELLA_ADDITIONAL = []



# <<<<ADDITIONAL FILES>>>>

# paths to additional files that should be copied into the directory from which this script is being run
GLOBAL_ADDITIONAL = []


# <<<<MDP VALIDATION>>>>

# validate the umbrella mdp file (will print warning if validation fails)
# you can also set any of the options below to None and they will not be checked
VALIDATE_MDP = True

# expected value of the mdp option 'pull'
VALIDATE_PULL = "yes"

# expected _minimal_ value of the mdp option 'pull-nstfout'
VALIDATE_NSTFOUT = 1000

# expected _minimal_value of the mdp option 'pull-nstxout'
VALIDATE_NSTXOUT = 1000

# index of the restraint used for umbrella sampling
VALIDATE_UMBRELLA_ID = 1


# <<<<INDEX VALIDATION>>>>

# validate the index file
VALIDATE_NDX = True


# <<<<ADDITIONAL OPTIONS>>>>

# name of the logfile
LOGFILE = "prepare_windows.log"

# precision of the trajectory splitting
SKIP_MULTIPLIER = 5

# column in the PULL_X file corresponding to time (counting from zero)
TIME_COL = 0

# column in the PULL_X file corresponding to the CV value
CV_COL   = 1

# when copying itp files into umbrella sampling windows, 
# (do not) copy entire directories, if provided
COPY_ITP_DIRECTORIES = True




# @@@@@@@@@@@@@@@@@@@@@@@@
# @ DO NOT EDIT THE FILE @
# @   BELOW THIS LINE!   @
# @@@@@@@@@@@@@@@@@@@@@@@@

try:
    import sys, os, shutil
except ModuleNotFoundError:
    print("\nError. Missing required libraries (sys, os, shutil).\n")
    sys.exit()
    
# @@@@@@@@@@@@@@@@@@@@@@@@
# @       GENERAL        @
# @@@@@@@@@@@@@@@@@@@@@@@@

SCRIPT_NAME   = "Prepare Windows"
VERSION       = "2022/10/12"

# @@@@@@@@@@@@@@@@@@@@@@@@
# @   BASIC FUNCTIONS    @
# @@@@@@@@@@@@@@@@@@@@@@@@

def logprint(text, file):
    """
    Prints text into STDOUT & logs text into file.
    """
    print(text, end = "")
    file.write(text)

def decomment(text, decommenter = "#"):
    """
    Returns decommented 'text'.
    """
    return text.split(decommenter)[0]

def longest_string(strings):
    """
    Returns the length of the longest string from strings.
    """
    return len(max(strings, key=len))

# @@@@@@@@@@@@@@@@@@@@@@@@
# @   PULL DIRECTORIES   @
# @@@@@@@@@@@@@@@@@@@@@@@@

def check_pull_files(pull_dir):
    """
    Checks whether the files from pulling exist.
    Returns True, if they do. Else returns False.
    """
    files = [PULL_X, PULL_MDP, PULL_TPR, PULL_XTC, SYSTEM_TOP, SYSTEM_NDX]
    files.extend(PULL_ADDITIONAL)
    for file in files:
        if not os.path.exists(f"{pull_dir}/{file}"):
            print(f"\nError. File {file} is not present in the directory {pull_dir}.\n")
            return False
    
    return True

def get_pulls(w_list):
    """
    Reads paths to pulling directories from w_list.
    """
    pulls = []
    for line in open(w_list):
        parsed = decomment(line).split()
        if len(parsed) == 2 and parsed[0].lower() in ["pull_dir", "pull-dir", "pulldir", "pulling_directory", "pulling-directory", "pullingdirectory"]:
            return [parsed[1]]
        elif len(parsed) == 3 and "pull" not in parsed[0]:
            pulls.append(parsed[2])
        elif len(parsed) != 0 and "pull" not in parsed[0]:
            print(f"\nError. Incorrect format of file {w_list}.\n")
            sys.exit()
    
    return list(set(pulls))

def get_pull_groups(w_list):
    """
    Reads pull groups defined in the w_list file.
    """
    pull_group_1 = None
    pull_group_2 = None
    
    for line in open(w_list):
        parsed = decomment(line).split()
        if len(parsed) == 2:
            if parsed[0].lower().replace("_","").replace("-","") in ["pullgroup1", "pulledgroup1"]:
                pull_group_1 = parsed[1]
            elif parsed[0].lower().replace("_","").replace("-","") in ["pullgroup2", "pulledgroup2"]:
                pull_group_2 = parsed[1]
        
        elif len(parsed) == 3 and parsed[0].lower().replace("_","").replace("-","") in ["pullgroups"]:
            pull_group_1 = parsed[1]
            pull_group_2 = parsed[2]
    
    return (pull_group_1, pull_group_2)

def load_pullx(px_file):
    """
    Loads times and CV values from px_file.
    """
    t, cv = [], []
    for line in open(px_file):
        if line.strip()[0] not in ["#", "@"]:
            t.append(float(line.split()[TIME_COL]))
            cv.append(float(line.split()[CV_COL]))
    
    return (t, cv)

def get_itps(topology):
    """
    Returns a list of itp files included in topology.
    """
    itps = []
    for line in open(topology):
        if "#include" in line:
            itps.append(line.split()[1].replace('"',''))
    
    return itps

# @@@@@@@@@@@@@@@@@@@@@@@@
# @   SPLITTING PULL     @
# @@@@@@@@@@@@@@@@@@@@@@@@

def get_step_prec(mdp_file):
    """
    Gets values associated with 'nstxout-compressed' and 'pull-nstxout' from the 'mdp_file'.
    This does not test for the validity of the values and assumes 
    that the format of the mdp file is 'option = value' (with spaces around '=')
    """
    for line in open(mdp_file):
        parsed = decomment(line, ";").split()
        if len(parsed) == 0: continue
        if parsed[0] == "nstxout-compressed" or parsed[0] == "nstxout_compressed":
            xtc = int(parsed[2])
        if parsed[0] == "pull-nstxout" or parsed[0] == "pull_nstxout":
            pullx = int(parsed[2])
    
    return (xtc, pullx)

def get_time_step(mdp_file):
    """
    Gets time step of the simulation from the 'mdp_file'.
    """
    for line in open(mdp_file):
        parsed = decomment(line).split()
        if len(parsed) == 0: continue
        if parsed[0] == "dt":
            return float(parsed[2])

def extract_time(file):
    """
    Extract time from target simulation frame.
    """
    for line in open(file):
        if "t=" in line:
            return float(line.split()[line.split().index("t=")+1])

def split_trajectory(pull_dir):
    """
    Splits trajectory from target pulling directory.
    """
    # check that the trajectory is not already split
    if os.path.exists(f"{pull_dir}/frames/unfinished"):
        shutil.rmtree(f"{pull_dir}/frames")
        
    if not os.path.exists(f"{pull_dir}/frames"):
        dt = get_time_step(f"{pull_dir}/{PULL_MDP}")
        xtc, pullx = get_step_prec(f"{pull_dir}/{PULL_MDP}")
        if pullx % xtc == 0:
            # time step = time elapsed between two consecutive frames
            time_step = pullx * dt * SKIP_MULTIPLIER
            skip = (pullx // xtc) * SKIP_MULTIPLIER
        else:
            time_step = xtc * dt * SKIP_MULTIPLIER
            logprint("Warning. Using 'xtc' time step...", log)
            skip = SKIP_MULTIPLIER        
            
        os.system(f"module add {GROMACS_VERSION} && cd {pull_dir} && mkdir frames && cd frames && touch unfinished && yes 0 | gmx trjconv -s ../{PULL_TPR} -f ../{PULL_XTC} -o conf.gro -sep -skip {skip} -quiet && rm unfinished")
    
    # if the trajectory is already split, get time_step from generated frames
    else:
        time_step = extract_time(f"{pull_dir}/frames/conf1.gro") - extract_time(f"{pull_dir}/frames/conf0.gro")
    
    return time_step

# @@@@@@@@@@@@@@@@@@@@@@@@
# @  WINDOWS PREPARATION @
# @@@@@@@@@@@@@@@@@@@@@@@@

def load_windows(w_list, origin = None):
    """
    Loads information about umbrella sampling windows from w_list.
    """
    distances, biases, origins = [], [], []
    for line in open(w_list):
        parsed = decomment(line).split()
        if len(parsed) >= 2 and "pull" not in parsed[0].lower():
            try:
                distances.append(float(parsed[0]))
                biases.append(int(parsed[1]))
            except Exception:
                print(f"\nError. Could not parse line '{line}' from '{w_list}'.\n")
                sys.exit()
           
            if origin is not None:
                origins.append(origin)
            elif len(parsed) == 3:
                origins.append(parsed[2])
            else:
                print(f"\nError. Incorrect format of file {w_list}.\n")
                sys.exit()                
    
    return distances, biases, origins

def create_directories(n_windows, log):
    """
    Creates directories for umbrella sampling windows.
    Returns the number of warnings raised.
    """
    return_code = 0
    
    for i in range(1, n_windows + 1):
        win_dir = f"win{i:0{len(str(n_windows))}d}"
        if os.path.exists(win_dir):
            logprint(f">>> Warning. Directory {win_dir} already exists.\n", log)
            return_code += 1
        else:
            os.mkdir(win_dir)
    
    return return_code

def validate_umbrella_mdp(mdp_content, pull_groups, log):
    """
    Validates that the umbrella mdp is reasonably correct.
    Returns the number of warnings raised.
    """
    return_code = 0
    
    groups = {}
    
    skip_groups = False
    pull_coordinate_exists = False
    if VALIDATE_UMBRELLA_ID is None: 
        pull_coordinate_exists = True
        skip_groups = True
    
    pull_code_specified = False
    if VALIDATE_PULL is None: pull_code_specified = True
    
    for line in mdp_content.split("\n"):
        split = line.split(";")[0].split()
        if len(split) == 0: continue
        
        if split[0] == "pull" and VALIDATE_PULL is not None:
            pull_code_specified = True
            
            if split[2] != VALIDATE_PULL:
                logprint(f">>> Warning. Value of the 'pull' option is '{split[2]}' which is not the requested value ('{VALIDATE_PULL}'). Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
        
        if VALIDATE_NSTFOUT is not None and (split[0] == "pull-nstfout" or split[0] == "pull_nstfout"):
            try:
                val = float(split[2])
            except ValueError:
                logprint(f">>> Warning. While validating the mdp file, option '{split[2]}' could not be parsed.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
                val = None
            
            if val is None: continue
            
            if val > VALIDATE_NSTFOUT:
                logprint(f">>> Warning. Value of the 'nstfout' option might be too large. Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
        
        if VALIDATE_NSTXOUT is not None and (split[0] == "pull-nstxout" or split[0] == "pull_nstxout"):
            try:
                val = float(split[2])
            except ValueError:
                logprint(f">>> Warning. While validating the mdp file, option '{split[2]}' could not be parsed.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
                val = None
            
            if val is None: continue                
            
            if val > VALIDATE_NSTXOUT:
                logprint(f">>> Warning. Value of the 'nstxout' option might be too large. Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
        
        if not skip_groups and ("pull_group" in split[0] and "_name" in split[0]) or ("pull-group" in split[0] and "-name" in split[0]):
            groups[split[0].replace("pull_group", "").replace("_name", "").replace("pull-group", "").replace("-name", "")] = split[2]
        
        if not skip_groups and (split[0] == f"pull_coord{VALIDATE_UMBRELLA_ID}_groups" or split[0] == f"pull-coord{VALIDATE_UMBRELLA_ID}-groups"):
            pull_coordinate_exists = True
            
            umbrella_groups = [split[2], split[3]]            
            
            # try parsing the values to integers
            try:
                x, y = int(umbrella_groups[0]), int(umbrella_groups[1])
            except ValueError:
                logprint(f">>> Warning. Could not parse identifiers of the umbrella groups to integers. Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
            
            # search for the group ids in the dictionary
            try:
                umbrella_group_names = [groups[umbrella_groups[0]], groups[umbrella_groups[1]]]
            except KeyError:
                logprint(f">>> Warning. Could not find umbrella group identifiers in the defined pull groups. Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
                continue
            
            # verify that the group names are not the same
            if umbrella_group_names[0] == umbrella_group_names[1]:
                logprint(f">>> Warning. Two identical umbrella groups ('{umbrella_group_names[0]}' and '{umbrella_group_names[1]}') identified. Check your mdp file.\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1                
            
            # verify that the requested pull groups are in the mdp file
            if pull_groups[0] is not None and pull_groups[0] not in umbrella_group_names:
                logprint(f">>> Warning. Expected umbrella group name '{pull_groups[0]}', got '{umbrella_group_names[0]}' and '{umbrella_group_names[1]}'\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1
            
            if pull_groups[1] is not None and pull_groups[1] not in umbrella_group_names:
                logprint(f">>> Warning. Expected umbrella group name '{pull_groups[1]}', got '{umbrella_group_names[0]}' and '{umbrella_group_names[1]}'\n", log)
                logprint(f">>> Concerned line: '{line}'\n", log)
                return_code += 1           
    
    if not pull_code_specified:
        logprint(f">>> Warning. Could not find a required option 'pull = {VALIDATE_PULL}'. Check your mdp file.\n", log)
        return_code += 1
    
    if not pull_coordinate_exists:
        logprint(">>> Warning. Could not find 'groups' of the umbrella coordinate. Check your mdp file.\n", log)
        return_code += 1
    
    return return_code

def modify_mdp_content(content, reference, bias, pull_groups):
    """
    Modifies the content of an mdp file.
    """
    content = content.replace("[FORCE_CONSTANT]", str(bias)).replace("[K_CONST]", str(bias))
    content = content.replace("[REFERENCE_VALUE]", str(reference)).replace("[INIT_DIST]", str(reference))
    if pull_groups[0] is not None:
        content = content.replace("[PULL_GROUP_1]", pull_groups[0]).replace("[PULL_GROUP1]", pull_groups[0])
    if pull_groups[1] is not None:
        content = content.replace("[PULL_GROUP_2]", pull_groups[1]).replace("[PULL_GROUP2]", pull_groups[1])    
    
    return content

def fetch_umbrella_mdp(umbrella_mdp, destination, reference, bias, pull_groups):
    """
    Copies umbrella_mdp into destination and modifies its content.
    """
    with open(umbrella_mdp) as file:
        mdp_content = file.read()
    
    mdp_content = modify_mdp_content(mdp_content, reference, bias, pull_groups)
    
    with open(f"{destination}/umbrella.mdp", "w") as file:
        file.write(mdp_content)
    
def validate_ndx_file(mdp_content, path_ndx, log):
    """
    Checks that all ndx groups that are defined in the mdp file also exist in the ndx file.
    Returns the number of warnings raised.
    """
    return_code = 0
    
    # prepare a list containing the relevant groups
    groups = []
    for line in mdp_content.split("\n"):
        split = line.split(";")[0].split()
        if len(split) == 0: continue
        
        if ("pull_group" in split[0] and "_name" in split[0]) or ("pull-group" in split[0] and "-name" in split[0]):
            groups.append(split[2])
    
    # read ndx file searching for the relevant groups
    ndx_groups = []
    try:
        open(path_ndx).close()
    except FileNotFoundError:
        print(f"Error. File {path_ndx} could not be read.")
        sys.exit()            
    
    for line in open(path_ndx):
        if "[" in line and "]" in line:
            ndx_groups.append(line.replace("[","").replace("]","").strip())
    
    for group in groups:
        if group not in ndx_groups:
            logprint(f">>> Warning. Group {group} is defined in the mdp file but it was not found in the ndx file.\n", log)
            return_code += 1
    
    return return_code
    

def fetch_files(references, biases, origins, real_cvs, real_times, time_steps, pull_groups, log):
    """
    Fetches necessary files for the umbrella sampling windows.
    """
    n_windows = len(references)
    origin_length = longest_string(origins)
    for (i, ref) in enumerate(references):
        conf = int(real_times[i] / time_steps[origins[i]])
        wid = f"{i+1:0{len(str(n_windows))}d}"

        logprint(f">>> Window {wid}:   Conf: {int(conf): 5d}   Origin: {origins[i]:{origin_length}s}   ", log)
        logprint(f"Time: {int(real_times[i]): 9d}   Bias: {biases[i]: 5d}   CV value: {real_cvs[i]: 2.4f}   CV reference: {references[i]: 2.3f}   ", log)
        
        try:
            shutil.copy(f"{origins[i]}/frames/conf{conf}.gro", f"win{i+1:0{len(str(n_windows))}d}/system.gro")
        except:
            logprint("ERROR\n", log)
            print(f"Error. File {origins[i]}/frames/conf{conf}.gro could not be copied.")
            sys.exit()
        
        files = [SYSTEM_TOP, SYSTEM_NDX]
        files.extend(PULL_ADDITIONAL)
        
        for file in files:
            try:
                shutil.copy(f"{origins[i]}/{file}", f"win{wid}")
            except:
                logprint("ERROR\n", log)
                print(f"Error. File {file} could not be copied.")
                sys.exit()        
        
        files = get_itps(f"{origins[i]}/{SYSTEM_TOP}")
        copied_dirs = []
        for file in files:
            # if directory is detected in #include, copy the entire directory instead of the individual files
            # this behavior can be disabled by setting COPY_ITP_DIRECTORIES to False
            if COPY_ITP_DIRECTORIES and "/" in file and \
               file.split("/")[-2] not in [".", "..", origins[i]]:
                directory = file.split("/")[-2]
                
                if directory in copied_dirs:
                    continue
                
                try:
                    shutil.copytree(f"{origins[i]}/{directory}", f"win{wid}/{directory}")
                    copied_dirs.append(directory)
                except:
                    logprint("ERROR\n", log)
                    print(f"Error. Directory {directory} could not be copied.")
                    sys.exit()
            else:
                try:
                    shutil.copy(f"{origins[i]}/{file}", f"win{wid}")
                except:
                    logprint("ERROR\n", log)
                    print(f"Error. File {file} could not be copied.")
                    sys.exit()                
        
        
        
        UMBRELLA_ADDITIONAL.append(UMBRELLA_RUN)
        for file in UMBRELLA_ADDITIONAL:
            try:
                if file is not None:
                    shutil.copy(file, f"win{wid}")
            except:
                logprint("ERROR\n", log)
                print(f"Error. File {file} could not be copied.")
                sys.exit()                
        
        try:
            fetch_umbrella_mdp(UMBRELLA_MDP, f"win{wid}", references[i], biases[i], pull_groups)
        except:
            logprint("ERROR\n", log)
            print(f"Error. File {UMBRELLA_MDP} could not be copied.")
            sys.exit()
        
        os.system(f"echo 'Initial configuration for this umbrella sampling window was taken from: {origins[i]}' > win{wid}/origin")
        
        logprint("OK\n", log)

# @@@@@@@@@@@@@@@@@@@@@@@@
# @   OTHER FUNCTIONS    @
# @@@@@@@@@@@@@@@@@@@@@@@@

def find_configurations(win_references, win_origins, times, cvs, time_steps):
    """
    Searches for frames suitable to be used as initial configurations for umbrella sampling windows.
    """
    real_cvs = []
    real_times = []
    
    # filter cvs and times
    filtered_times = {}
    filtered_cvs = {}
    for origin in times.keys():
        for i in range(len(times[origin])):
            if times[origin][i] % time_steps[origin] == 0:
                try:
                    filtered_times[origin].append(times[origin][i])
                    filtered_cvs[origin].append(cvs[origin][i])
                except KeyError:
                    filtered_times[origin] = [times[origin][i]]
                    filtered_cvs[origin]   = [cvs[origin][i]]
    
    for wid in range(len(win_references)):
        win_ref  = win_references[wid]
        win_orig = win_origins[wid]
        
        rref = min(filtered_cvs[win_orig], key = lambda x: abs(x - win_ref))
        real_cvs.append(rref)
        index = filtered_cvs[win_orig].index(rref)
        real_times.append(filtered_times[win_orig][index])
    
    return real_cvs, real_times    


# @@@@@@@@@@@@@@@@@@@@@@@@
# @         MAIN         @
# @@@@@@@@@@@@@@@@@@@@@@@@

def main():
    log = open(LOGFILE, "w")
    print()
    logprint(f"{SCRIPT_NAME} v{VERSION}\n", log)
    
    logprint("\nSearching for pulling directories...\n", log)
    pull_dirs = get_pulls(WINDOW_LIST)
    
    # check whether the required files exist in pulling directories
    for pd in pull_dirs:
        logprint(f">>> {pd:{longest_string(pull_dirs) + 5}s}", log)
        if check_pull_files(pd): logprint("OK\n", log)
        else: sys.exit()
        
    logprint("\nSplitting pulling trajectories...\n", log)
    time_steps = {}
    for pd in pull_dirs:
        logprint(f">>> {pd:{longest_string(pull_dirs) + 5}s}", log)
        time_steps[pd] = split_trajectory(pd)
        logprint("OK\n", log)
    
    logprint(f"\nLoading windows from {WINDOW_LIST}...\n", log)
    references, biases, origins = load_windows(WINDOW_LIST, None if len(pull_dirs) > 1 else pull_dirs[0])
    logprint(f">>> {len(references)} windows loaded\n", log)
    
    # get pull groups
    logprint("\nLooking for pull groups...\n", log)
    pull_groups = get_pull_groups(WINDOW_LIST)
    for (i, group) in enumerate(pull_groups):
        if group is not None:
            logprint(f">>> using explicitly defined pull group {i+1} '{pull_groups[i]}'.\n", log)    
    if pull_groups[0] is None and pull_groups[1] is None:
        logprint(f">>> no pull groups found in '{WINDOW_LIST}'\n", log)
    
    # validate the mdp file
    n_warnings = 0
    try:
        with open(UMBRELLA_MDP) as file:
            mdp_content = file.read()
    except Exception:
        print(f"Error. File {UMBRELLA_MDP} could not be read.")
        sys.exit()

    mdp_content = modify_mdp_content(mdp_content, references, biases, pull_groups)
    
    if VALIDATE_MDP:
        logprint(f"\nValidating the mdp file '{UMBRELLA_MDP}'...\n", log)        
        n_warnings += validate_umbrella_mdp(mdp_content, pull_groups, log)
        if n_warnings == 0:
            logprint(">>> mdp file has been validated. No problems have been found.\n", log)

    # validate the ndx file
    if VALIDATE_NDX:
        for pull in pull_dirs:
            logprint(f"\nValidating the ndx file from pulling directory '{pull}'...\n", log)
            old_n_warnings = n_warnings
            n_warnings += validate_ndx_file(mdp_content, f"{pull}/{SYSTEM_NDX}", log)
            
            if old_n_warnings == n_warnings:
                logprint(">>> ndx file has been validated. No problems have been found.\n", log)
    
    # read CV from pulling
    logprint("\nReading CV values from pulling...\n", log)
    times, cvs = {}, {}
    for pd in pull_dirs:
        logprint(f">>> {pd:{longest_string(pull_dirs) + 5}s}", log)
        t, cv = load_pullx(f"{pd}/{PULL_X}")
        times[pd] = t
        cvs[pd] = cv
        logprint("OK\n", log)
    
    logprint(f"\nSearching for configurations...\n", log)
    real_cvs, real_times = find_configurations(references, origins, times, cvs, time_steps)
    
    logprint(f"\nPreparing umbrella sampling windows...\n", log)
    # creating directories
    n_warnings += create_directories(len(references), log)
    # fetching files for umbrella sampling windows
    fetch_files(references, biases, origins, real_cvs, real_times, time_steps, pull_groups, log)
    
    # copy additional global files
    for file in GLOBAL_ADDITIONAL:
        try:
            shutil.copy(file, ".")
        except:
            print(f"Error. File {file} could not be copied.")
            sys.exit()
    
    if n_warnings == 0:
        logprint("\nUmbrella sampling windows have been succesfully generated (no warnings).\n", log)
    elif n_warnings == 1:
        logprint(f"\n1 WARNING has been raised during the run! Check the log file for more details.\n", log)
    else:
        logprint(f"\n{n_warnings} WARNINGS have been raised during the run! Check the log file for more details.\n", log)
    
    print()
    log.close()






if __name__ == "__main__":
    main()