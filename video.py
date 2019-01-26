# video.py
# date: 1/25/19
# author: Bruce Zheng
# calls ffmpeg to create video file of story

import sys
import json
import re
from PIL import Image
from pydub import AudioSegment
import subprocess
from timeit import default_timer as timer
import glob
import sh

assert len(sys.argv) > 1	
param_file = sys.argv[1]
params = json.loads(open(param_file).read())

story_src = params["story_src"]
image_folder = params["image_src"]
audio_folder = params["audio_temp"]
video_folder = params["video_out"]
temp_folder = params["video_temp"]
timing_folder = params["page_timing_temp"]
pixel_format = params["pixel_format"]
video_codec = params["video_codec"]
audio_codec = params["audio_codec"]

fps = params["fps"]
smooth_scale = params["smoothness"] # helps make the zoom less jittery. decrease this for better performance
output_height = params["output_height"] # decrease for faster performance

def sign(x):
	if x < 0:
		return "-"
	else:
		return "+"

def format_book_title(t):
	return re.sub(r"[ -]",'_',t)

def format_duration_ffmpeg(t):
	ff = t % 1000
	ss = t / 1000
	mm = ss / 60
	ss = ss % 60
	return "{0}:{1}.{2}".format(int(mm),int(ss),int(ff))

def make_movie(story):
	title = format_book_title(story["title"])
	final_tgt = "{0}/{1}.mp4".format(video_folder,title)
	print("Generating {0}".format(final_tgt))
	output_files = []
	total_start = timer()
	page_duration = []

	#clean up old page fragments
	temp_files = glob.glob(temp_folder + "/*")
	if len(temp_files) > 0:
		sh.rm(temp_files)
	
	#generate fragment video (01.mp4, 02.mp4...) per page
	page_number = 1
	for page in story["pages"]:
		image_src = "{0}/{1}".format(image_folder,page['img_src'])
		image_src = image_src.replace("%20"," ")
		image = Image.open(image_src)
		
		transform = [page['img_initialrect'].split(' '), page['img_finalrect'].split(' ')]
		transform = [list(map(float,T)) for T in transform]

		audio_src = "{0}/{1}_{2:02d}.mp3".format(audio_folder,title,page_number)
		audio = AudioSegment.from_mp3(audio_src)

		# generate params for ffmpeg
		num_frames = int(float(len(audio))/(1000.0/float(fps)))
		
		size_init = transform[0][3]
		size_change = transform[1][3] - transform[0][3]
		size_incr = size_change / num_frames

		zoom_init = 1.0/transform[0][3]
		zoom_change = 1.0/transform[1][3] - 1.0/transform[0][3]
		zoom_incr = zoom_change / num_frames
		
		x_init = transform[0][0]
		x_end = transform[1][0]
		x_change = x_end - x_init
		x_incr = x_change / num_frames

		y_init = transform[0][1]
		y_end = transform[1][1]
		y_change = y_end - y_init
		y_incr = y_change / num_frames

		#old non-constant zoom
		#zoom_cmd = "{0:0.10f}{1}{2:0.10f}*on".format(zoom_init - zoom_incr, sign(zoom_incr), abs(zoom_incr))
		zoom_cmd = "1/({0:0.10f}{1}{2:0.10f}*on)".format(size_init - size_incr, sign(size_incr), abs(size_incr))
		x_cmd = "{0:0.10f}*iw{1}{2:0.10f}*iw*on".format(x_init - x_incr,sign(x_incr),abs(x_incr))
		y_cmd = "{0:0.10f}*ih{1}{2:0.10f}*ih*on".format(y_init - y_incr,sign(y_incr),abs(y_incr))

		output_tgt = "{0}/{1:02d}.mp4".format(temp_folder,page_number)
		output_files.append("{0:02d}.mp4".format(page_number))

		# run ffmpeg to create page mp4
		ffmpeg_cmd = "ffmpeg -i \"{0}\" -i \"{1}\"".format(audio_src,image_src)
		ffmpeg_cmd += " -filter_complex \"scale=-2:{0}*ih,zoompan=z=\'{1}\':x=\'{2}\':y=\'{3}\':d={4}:fps={5},scale=-2:{6}\"".format(smooth_scale,zoom_cmd,x_cmd,y_cmd,num_frames,fps,output_height)
		ffmpeg_cmd += " -pix_fmt {0} -c:v {1} -c:a {2} \"{3}\"".format(pixel_format, video_codec, audio_codec, output_tgt)

		print("Generating page {0:02d}...".format(page_number),end=' ',flush=True)
		start_time = timer()
		subprocess.run(ffmpeg_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		end_time = timer()
		print("done ({0:0.2f})".format(end_time-start_time),flush=True)

		page_number += 1

		# store timing info (needed for precise sub times)
		mp4_audio = AudioSegment.from_file(output_tgt, "mp4") 
		# need to manually get duration of the file, deriving from num_frames somehow gives incorrect
		duration = len(mp4_audio)
		page_duration.append(duration)

	#page list needed for concatenate command
	pages_list = "\n".join(["file '{0}'".format(x) for x in output_files])
	pages_src = "{0}/pages.txt".format(temp_folder)
	with open(pages_src,"w+") as file:
		file.write(pages_list)
		file.close()

	#ffmpeg will ask to override, so we just remove it if it exists
	try:
		#pass
		sh.rm(final_tgt)
	except:
		pass

	combine_cmd = "ffmpeg -f concat -safe 0 -i {0} -c copy \"{1}\"".format(pages_src,final_tgt)
	print("Concatenating...",end=' ',flush=True)
	subprocess.run(combine_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	print("done")
	total_end = timer()
	print("Done generating movie ({0:0.2f})".format(total_end - total_start))

	timing_tgt = "{0}/{1}.txt".format(timing_folder,title)
	with open(timing_tgt,"w+") as file:
		file.write("\n".join([str(x) for x in page_duration]))
		file.close()

story_raw = open(story_src).read()
stories = json.loads(story_raw)

for story in stories["storyCollection"]:
	story = story["story"]
	make_movie(story)
