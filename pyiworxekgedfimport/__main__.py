import contextlib
import datetime
import decimal
import os
import struct
import sys

import wiff
import pyiworxekgedfimport

def main():
	if len(sys.argv) == 2:
		fname = sys.argv[1]
		wiff_fname = os.path.splitext(fname)[0] + '.wiff'
	else:
		fname = sys.argv[1]
		wiff_fname = sys.argv[2]

	print("Filename: %s" % fname)
	print("WIFF: %s" % wiff_fname)

	with pyiworxekgedfimport.EDFReader.open(fname) as f:
		props = {
			'start': f.Start,
			'end': f.Start + datetime.timedelta(seconds=f.Duration),
			'description': 'iWorx LabScribe EDF file',
			'fs': 2000, # FIXME
			'channels': [],
		}
		for idx,ch in enumerate(f.Signals):
			if ch['Label'] == 'EDF Annotations':
				continue

			props['channels'].append({
				'idx': idx,
				'name': ch['Label'],
				'bits': 16,
				'unit': ch['PhysicalDimension'],
				'comment': 'Physical (%d,%d) to (%d,%d)' % (ch['PhysicalMinimum'],ch['PhysicalMaximum'], ch['DigitalMinimum'],ch['DigitalMaximum']),
			})

		f.writeWIFF(wiff_fname, props)

if __name__ == '__main__':
	main()

