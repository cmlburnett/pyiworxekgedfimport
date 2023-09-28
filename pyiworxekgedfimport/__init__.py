import sys

import pyedflib

def main():
	fname = sys.argv[1]
	print("Filename: %s" % fname)

	with pyedflib.EdfReader(fname) as f:
		print(f.getStartdatetime())
		print(f.getFileDuration())
		print(f.getHeader())
		print(f.getSampleFrequency(1))

		for h in f.getSignalHeaders():
			print(h)

		print(list(f.readSignal(0, 0, None, False)))

if __name__ == '__main__':
	main()

