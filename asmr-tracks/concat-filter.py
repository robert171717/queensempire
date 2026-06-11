#!/usr/bin/env python3
"""Build and run an ffmpeg concat FILTER command from a concat.txt file.

The concat FILTER decodes all inputs to raw PCM before concatenation,
avoiding the MP3 frame-boundary issues that plague the concat demuxer
(-f concat -i) and concat protocol (concat:file1|file2|...).

Usage: python3 concat-filter.py <concat_file> <output_file> <work_dir>
"""
import subprocess, sys

concat_file = sys.argv[1]
output_file = sys.argv[2]
work_dir = sys.argv[3]

with open(concat_file) as f:
    lines = [line.strip() for line in f if line.startswith("file ")]

# Extract filenames from 'file \'name.mp3\''
filenames = []
for line in lines:
    # Split on single quotes: "file 'name.mp3'" -> ["file ", "name.mp3", ""]
    name = line.split("'")[1]
    filenames.append(name)

inputs = []
filters = []
for i, name in enumerate(filenames):
    inputs.extend(["-i", name])
    filters.append(f"[{i}:a]")

n = len(filenames)
filter_graph = (
    f"{''.join(filters)}concat=n={n}:v=0:a=1[concated];"
    f"[concated]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
)

cmd = [
    "ffmpeg", "-y",
    *inputs,
    "-filter_complex", filter_graph,
    "-map", "[out]",
    "-b:a", "192k",
    output_file,
]

result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
# Show last 3 lines of stderr
lines = result.stderr.strip().split("\n")
for line in lines[-3:]:
    print(line, file=sys.stderr)

if result.returncode != 0:
    print(f"ERROR: ffmpeg concat filter failed (exit {result.returncode})", file=sys.stderr)
    sys.exit(1)
