# audio.py
# date: 1/25/19
# author: Bruce Zheng
# splices audio files page-by-page for storybook

import sys
from pydub import AudioSegment
import json
import re
from timeit import default_timer as timer

from pathlib import Path

from sb_util import *

assert len(sys.argv) > 1	
param_file = sys.argv[1]
params = json.loads(open(param_file).read())

output_folder = Path(params["audio_temp"])
story_src = Path(params["story_src"])

books = params["books"]
book_segs = {}

# converts format from input json to python style format [nnn] -> {0:03d}, [n] -> {0:01d}
def convert_to_pyformat(form):
	return re.sub(r"\[(n+)\]",lambda x : '{' + "0:0{0}".format(len(x.group(1))) + '}',form)
	
# fills book_segs with audio files for given book (e.g. JHN)
def load_book(book_data):
	chapter_range = [ x + 1 for x in range(book_data["num_chapters"])]

	timing_format = convert_to_pyformat(book_data["timing"])
	audio_format = convert_to_pyformat(book_data["audio"])

	timing_src = [ Path(timing_format.format(x)) for x in chapter_range ]
	audio_src = [ Path(audio_format.format(x)) for x in chapter_range ]
	
	timing_raw = []
	audio = []

	for t in timing_src:
		with open(t) as file:
			timing_raw.append(file.read())

	for a in audio_src:
		audio.append(AudioSegment.from_mp3(a))

	segments = []

	for i in range(len(timing_raw)):
		segments.append([])

		raw = timing_raw[i].replace('\ufeff','').strip()
		timings = raw.split("\n")
		timings = [x.split("\t") for x in timings]
		timings = [(int(float(x[0]) * 1000), int(float(x[1]) * 1000), x[2]) for x in timings]
		timings = [x for x in timings if x[2][0].isdigit()]

		timings2 = []

		curr_verse = 0
		curr_start = 0
		curr_end = 0
		for x in timings:
			verse = int(re.match(r"[0-9]+",x[2]).group(0))
			if verse != curr_verse:
				timings2.append((curr_start,curr_end,curr_verse))
				curr_verse = verse
				curr_start = x[0]
			curr_end = x[1]

		timings2.append((curr_start,curr_end,curr_verse))
		timings = timings2[1:]

		for start, end, verse in timings:
			segments[i].append(audio[i][start:end])

	return segments

# assumes that start and end are in the same chapter
# get the audio file from ref_start to ref_end
def get_seg(ref_book,ref_start,ref_end):
	seg = AudioSegment.empty()
	segments = book_segs[ref_book]
	m_start = re.match(r"([0-9]+):([0-9]+)",ref_start)
	m_end = re.match(r"([0-9]+):([0-9]+)",ref_end)
	chapter = int(m_start.group(1))
	assert chapter == int(m_end.group(1))
	verse_start = int(m_start.group(2))
	verse_end = int(m_end.group(2))
	for verse in range(verse_start,verse_end+1):
		seg += segments[chapter-1][verse-1]
	return seg

# produce and write audio files for a story, page by page
def segment_story(story):
	title = format_book_title(story["title"])
	start_time = timer()
	print("Generating {0}/{1}_##.mp3...".format(output_folder,title),end=' ', flush=True)
	for p in story["pages"]:
		seg = get_seg(story["ref_book"],p["ref_start"],p["ref_end"])
		output_tgt = output_folder / "{0}_{1:02d}.mp3".format(title,p["page"])
		file = open(output_tgt,"w+")
		file.write(' ')
		file.close()
		seg.export(output_tgt, format="mp3")
	end_time = timer()
	print("done ({0:0.2f})".format(end_time-start_time),flush=True)

for title in books.keys():
	start_time = timer()
	print("Loading audio for {0}...".format(title),end=' ',flush=True)
	book_segs[title] = load_book(books[title])
	end_time = timer()
	print("done ({0:0.2f})".format(end_time-start_time),flush=True)

story_raw = open(story_src).read()
stories = json.loads(story_raw)

for story in stories["storyCollection"][-6:-5]:
	segment_story(story["story"])

