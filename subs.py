# subs.py
# date: 1/25/19
# author: Bruce Zheng
# creates srt files for given story, and transcodes subtitles

import sys
from pydub import AudioSegment
import json
import re
import subprocess
from timeit import default_timer as timer
import glob
import sh

from pathlib import Path

from sb_util import *

assert len(sys.argv) > 1	
param_file = sys.argv[1]
params = json.loads(open(param_file).read())

story_src = Path(params["story_src"])
audio_folder = Path(params["audio_temp"])
srt_folder = Path(params["subs_out"])
video_folder = Path(params["video_out"])
timing_folder = Path(params["page_timing_temp"])
sub_video_folder = Path(params["video_subs_out"])
aeneas_folder = Path(params["subs_temp"])

mode = params["subs_method"]
hardcoding = params["subs_hardcoded"]
video_codec = params["video_codec"]
split_treshold = params["subs_split"]
fps = params["fps"]

assert mode == "aeneas" or mode == "interpolate"

books = params["books"]
book_segs = {}

# "//v 1 blah blah" -> "blah blah"
def strip_header(line):
	result = line
	result = re.sub(r"\\f.*?\\f\*",'',result)
	result = re.sub(r"\\e.*?\\e\*",'',result)
	result = re.sub(r"\\x.*?\\x\*",'',result)
	result = re.sub(r"\\[a-z][0-9]?( [0-9]+)? ?",'',result)
	return result

# load book data for a given book
def load_book(book_data):
	segments = []
	book_raw = open(Path(book_data["text"])).read()
	book_lines = book_raw.split('\n')
	for line in book_lines:
		if line[:2] == "\\c":
			segments.append([])
		if line[:2] == "\\v":
			segments[-1].append(strip_header(line))
		if (line[:2] == "\\p" or line[:2] == "\\q") and len(segments[-1]) > 0 and len(strip_header(line)) > 0:
			segments[-1][-1] += "\n" + strip_header(line)
	return segments

# get verses from ref_start to ref_end
def get_seg(ref_book, ref_start,ref_end):
	result = []
	m_start = re.match(r"([0-9]+):([0-9]+)",ref_start)
	m_end = re.match(r"([0-9]+):([0-9]+)",ref_end)
	chapter = int(m_start.group(1))
	verse_start = int(m_start.group(2))
	verse_end = int(m_end.group(2))

	segments = book_segs[ref_book]
	for verse in range(verse_start,verse_end+1):
		result.append(segments[chapter-1][verse-1])
	return "\n".join(result)

# chunk a body of text on stopping points (punctuation) and character threshold
def get_chunk_text(text):
	# chunk text by newline and by characters .,?
	chunks = []
	first_line = True
	for line in text.split('\n'):
		if first_line:
			first_line = False
		else:
			line = '\n' + line
		chunks_line = re.split(r'([!.,?][’\'” "]*)',line)
		# want to include apostrophes in the preceding chunk
		chunks_merged = []
		i = 0
		for c in chunks_line:
			if i % 2 == 1:
				chunks_merged[-1] += c
			else:
				chunks_merged.append(c)
			i += 1
		chunks_merged = [x.rstrip() for x in chunks_merged]
		for c in chunks_merged:
			chunks.append(c)

	# merge chunks, splitting on character threshold
	chunks_merged = [""]
	for c in chunks:
		if c != "":
			chunks_merged[-1] += " " + c
		if len(chunks_merged[-1]) > split_treshold:
			chunks_merged.append("")
	if chunks_merged[-1] == "":
		chunks_merged = chunks_merged[:-1]
	chunks = [x.strip() for x in chunks_merged]
	return chunks

def get_chunk_subs_naive(text,start_time,duration):
	chunks = get_chunk_text(text)
	num_char = sum([len(x.strip()) for x in chunks])

	result = []
	current_time = start_time
	for c in chunks:
		chunk_duration = round(duration*float(len(c.strip()))/float(num_char))
		result.append((c, current_time, current_time + chunk_duration))
		current_time += chunk_duration
	return result

# naive method times using interpolation
def get_subs_naive(story,page_duration,padding):
	pages = story["pages"]
	book = story["ref_book"]

	page_number = 1
	current_time = padding
	result = []
	for p in pages:
		text = get_seg(book, p["ref_start"],p["ref_end"])
		duration = page_duration[page_number-1]
		chunk_subs = get_chunk_subs_naive(text,current_time,duration)
		result += chunk_subs
		current_time += duration + padding
		page_number += 1
	return result

# text alignment using aeneas
def get_subs_aeneas(story,audio):
	pages = story["pages"]
	book = story["ref_book"]

	temp_files = aeneas_folder.glob("*")
	for file in temp_files:
		sh.rm(file)
	#if len(temp_files) > 0:
	#	sh.rm(temp_files)
	
	audio_src = aeneas_folder / "audio.mp3"
	text_src = aeneas_folder / "text.txt"
	aeneas_align = aeneas_folder / "align.json"

	#audio_src = "{0}/audio.mp3".format(aeneas_folder)
	#text_src = "{0}/text.txt".format(aeneas_folder)
	#aeneas_align = "{0}/align.json".format(aeneas_folder)
	
	with open(audio_src,"w+") as file:
		file.write('')
		file.close()
	audio.export(audio_src,format="mp3")

	chunks = []
	for p in pages:
		page_text = get_seg(book,p["ref_start"],p["ref_end"])
		page_chunks = get_chunk_text(page_text)
		chunks += page_chunks

	with open(text_src,"w+") as file:
		file.write("\n".join([c.replace("\n",' ') for c in chunks]))
		file.close()

	with open(aeneas_align,"w+") as file:
		file.write(' ')
		file.close()

	params = "task_language=epo|is_text_type=plain|os_task_file_format=json|task_adjust_boundary_algorithm=percent|task_adjust_boundary_percent_value=50"
	cli_cmd = "python -m aeneas.tools.execute_task {0} {1} \"{2}\" {3}".format(audio_src,text_src,params,aeneas_align)

	print("Generating {0}...".format(aeneas_align),end=' ',flush=True)
	start_time = timer()
	subprocess.run(cli_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	end_time = timer()
	print("done ({0:0.2f})".format(end_time-start_time),flush=True)

	align_map = json.loads(open(aeneas_align).read())

	times = []
	for frag in align_map['fragments']:
		if len(frag["lines"]) == 0:
			continue
		start = int(1000 * float(frag["begin"]))
		end = int(1000 * float(frag["end"]))
		times.append((start,end))

	assert len(times) == len(chunks)

	result = []
	for i in range(len(times)):
		result.append((chunks[i],times[i][0],times[i][1]))

	return result

def generate_srt(story):
	title = format_book_title(story["title"])
	#output_tgt = "{0}/{1}.srt".format(srt_folder,title)
	output_tgt = srt_folder / "{0}.srt".format(title)

	#timing_src = "{0}/{1}.txt".format(timing_folder,title)
	timing_src = timing_folder / "{0}.txt".format(title)
	page_duration = list(map(int,open(timing_src).read().split('\n')))

	#video_src = "{0}/{1}.mp4".format(video_folder, title)
	video_src = video_folder / "{0}.mp4".format(title)
	audio = AudioSegment.from_file(video_src, "mp4")
	total_duration = len(audio)

	# ffmpeg adds some time in between each video page
	padding = int((total_duration - sum(page_duration)) / (len(page_duration) + 2))
	current_time = padding

	output_segs = []
	if mode == 'aeneas':
		chunk_subs = get_subs_aeneas(story,audio)
	else:
		chunk_subs = get_subs_naive(story,page_duration,padding)

	sub_number = 1
	for chunk_text, chunk_start, chunk_end in chunk_subs:
		timespan = "{0} --> {1}".format(format_time_srt(chunk_start), format_time_srt(chunk_end))		
		sub = "\n{0}\n{1}\n{2}".format(sub_number,timespan,chunk_text)
		output_segs.append(sub)
		sub_number += 1

	output_text = "\n".join(output_segs)
	file = open(output_tgt,"w+")
	file.write(output_text)
	file.close()
	print("Generating", output_tgt)

def transcode_subtitles(story):
	title = format_book_title(story["title"])
	video_src = video_folder / "{0}.mp4".format(title)
	sub_src = srt_folder / "{0}.srt".format(title)
	output_tgt = sub_video_folder / "{0}_subbed.mp4".format(title)
	
	#video_src = "{0}/{1}.mp4".format(video_folder,title)
	#sub_src = "{0}/{1}.srt".format(srt_folder,title)
	#output_tgt = "{0}/{1}_subbed.mp4".format(sub_video_folder,title)
	
	ffmpeg_cmd = "ffmpeg -i \"{0}\" -vf \"subtitles={1}\" -c:v {2} -c:a copy \"{3}\"".format(video_src, sub_src, video_codec, output_tgt)
	try:
		sh.rm(output_tgt)
	except:
		pass
	print("Generating {0}...".format(output_tgt),end=' ',flush=True)
	start_time = timer()
	subprocess.run(ffmpeg_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	end_time = timer()
	print("done ({0:0.2f})".format(end_time-start_time),flush=True)
 
story_raw = open(story_src).read()
stories = json.loads(story_raw)

for title in books.keys():
	book_segs[title] = load_book(books[title])

for story in stories["storyCollection"]:
	generate_srt(story["story"])
	if hardcoding:
		transcode_subtitles(story["story"])

