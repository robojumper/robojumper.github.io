import os
import subprocess

def process_file(rawdir, base, file):
	rel = os.path.relpath(base, rawdir)
	outfile = os.path.join('.', 'static', 'img', rel + '.png')
	subprocess.run(['dot', '-Tpng', file, '-o', outfile])
	print('dot:', file, '->', outfile)

rawdir = os.path.join('.', 'raw')
for root, subdirs, files in os.walk(rawdir):
	for file in files:
		infile = os.path.join(root, file)
		base, ext = os.path.splitext(infile)
		if ext == '.dot':
			process_file(rawdir, base, infile)