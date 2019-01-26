import re
import platform

def sign(x):
	if x < 0:
		return "-"
	else:
		return "+"

def format_book_title(t):
	result = re.sub(r"[ -]",'_',t)
	result = re.sub(r"[\'\":;.,/?\\\(\)\{\}\[\]]","",result)
	return result

def format_time_srt(t):
	ss = t / 1000
	ff = t % 1000
	mm = ss / 60
	ss = ss % 60
	hh = mm / 60
	mm = mm % 60
	return "{0:02d}:{1:02d}:{2:02d},{3:03d}".format(int(hh),int(mm),int(ss),int(ff))

def format_time_ffmpeg(t):
	ff = t % 1000
	ss = t / 1000
	mm = ss / 60
	ss = ss % 60
	return "{0}:{1}.{2}".format(int(mm),int(ss),int(ff))
