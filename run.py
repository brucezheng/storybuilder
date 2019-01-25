import sys
import os
import subprocess
import json
from timeit import default_timer as timer

if len(sys.argv) < 2:
	print("Need to indicate parameter file (e.g. params.json)")
	exit(1)
param_file = sys.argv[1]
params = json.loads(open(param_file).read())

subs_on = params["subtitles"]

def make_sure_exists(directory):
	if not os.path.exists(directory):
	    os.makedirs(directory)

folder_params = [ "audio_temp", "video_temp", "page_timing_temp", "subs_temp", "video_out", "subs_out", "video_subs_out" ]
folders = [ params[param_name] for param_name in folder_params ]
for folder in folders:
	make_sure_exists(folder)

audio_cmd = "python3 audio.py {0}".format(param_file)
video_cmd = "python3 video.py {0}".format(param_file)
subs_cmd = "python3 subs.py {0}".format(param_file)

def run_cmd(cmd_name, cmd):
	start_time = timer()
	print("Running {0}...".format(cmd_name))
	subprocess.run(cmd, shell=True)
	end_time = timer()
	print("Running {0} done ({1:0.2f})".format(cmd_name, end_time-start_time))

start_time = timer()
run_cmd("audio.py",audio_cmd)
run_cmd("video.py",video_cmd)
if subs_on:
	run_cmd("subs.py",subs_cmd)
end_time = timer()
print("Finished running. ({0:0.2f})".format(end_time-start_time))