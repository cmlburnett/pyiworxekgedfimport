import contextlib
import datetime
import decimal
import os
import struct
import sys

import wiff

class EDFReader:
	"""
	EDF file fromat reader.
	EDF contains a header segment and data segments.
	"""
	def __init__(self, f):
		version = f.read(8).strip()
		patient = f.read(80).strip()
		recordinginfo = f.read(80).strip()
		startdate = f.read(8).decode('ascii').strip()
		starttime = f.read(8).decode('ascii').strip()
		numbytes = int(f.read(8).decode('ascii').strip())
		resv = f.read(44)
		num_records = int(f.read(8).decode('ascii').strip())
		duration = int(f.read(8).decode('ascii').strip())
		ns = int(f.read(4).decode('ascii').strip())

		self._num_records = num_records
		self._num_signals = ns
		self._duration = duration
		self._start = datetime.datetime.strptime(startdate + starttime, '%d.%m.%y%H.%M.%S')

		if resv.startswith("EDF+C".encode('ascii')):
			self._format = "EDF+C"
		elif resv.startswith("EDF+D".encode('ascii')):
			self._format = "EDF+D"
		else:
			self._format = "EDF"

		self._signals = []
		for i in range(self.NumSignals):
			label = f.read(16).decode('ascii').strip()

			self._signals.append({
				'Label': label,
			})
		# All of the following depend on the number of signals
		r = range(self.NumSignals)
		for i in r:
			transducer = f.read(80).decode('ascii').strip()
			self._signals[i]['Transducer'] = transducer
		for i in r:
			physical = f.read(8).decode('ascii').strip()
			self._signals[i]['PhysicalDimension'] = physical
		for i in r:
			physical = float(f.read(8).decode('ascii').strip())
			self._signals[i]['PhysicalMinimum'] = physical
		for i in r:
			physical = float(f.read(8).decode('ascii').strip())
			self._signals[i]['PhysicalMaximum'] = physical
		for i in r:
			digital = int(f.read(8).decode('ascii').strip())
			self._signals[i]['DigitalMinimum'] = digital
		for i in r:
			digital = int(f.read(8).decode('ascii').strip())
			self._signals[i]['DigitalMaximum'] = digital
		for i in r:
			filtering = f.read(80).decode('ascii').strip()
			self._signals[i]['Filtering'] = filtering
		for i in r:
			num_samples = int(f.read(8).decode('ascii').strip())
			self._signals[i]['NumSamples'] = num_samples
		for i in r:
			resv = f.read(32).decode('ascii').strip()
			self._signals[i]['Reserved'] = resv

		self._data = []
		for i in range(self.NumRecords):
			pass

		if self.IsEDFPlus:
			annotation_idx = None
			for idx,s in enumerate(self.Signals):
				if s['Label'] == 'EDF Annotations':
					annotation_idx = idx
					break
			else:
				raise ValueError("File format is EDF+ but no 'EDF Annotations' signal found")

			siglen = []
			for s in self.Signals:
				siglen.append(s['NumSamples'])

			recordsize = sum(siglen)*2

			# Array of data frames (segments in WIFF)
			# self._data[0] is the first segment
			# self._data[0][0] is the first signal of the first segment
			# self._data[0][1] is the second signal of the first segment
			# self._data[1][0] is the first signal of the second segment
			# .........
			self._data = []

			for i in range(self.NumRecords):
				f.seek(numbytes + i*recordsize)
				# List contains all signal info in this data frame (WIFF segment)
				dataframe = []
				for sidx,l in enumerate(siglen):
					# Signal data for this particular signal for this data frame
					subsig = []

					# Pull out annotation TAL's instead of ordinary signal data
					if sidx == annotation_idx:
						try:
							_ = f.read(l*2)
							_ = __class__.parseTALs(_)
							dataframe.append(_)
						except ValueError as e:
							print("Caught parsing error (%s) for record %d, signal %d will skip since its just the EDF annotations signal" % (str(e), i, sidx))
					else:
						# Ordinary signal data: little-endian signed short (16-bit) integers
						for idx,k in enumerate(range(l)):
							v = struct.unpack("<h", f.read(2))[0]
							subsig.append(v)
						dataframe.append(subsig)

				# Add the signal data for this data frame
				self._data.append(dataframe)

		else:
			raise NotImplementedError

	@staticmethod
	def parseTALs(dat):
		ret = []
		#print(dat)

		while dat[0] != 0:
			i = dat.index(0)
			subdat = dat[0:i]
			# Advance to next potential TAL
			dat = dat[i+1:]

			if 21 in subdat:
				# has duration
				i = subdat.index(21)
				j = subdat.index(20)
				onset = subdat[0:i]
				duration = subdat[i:j]
				annots = subdat[j:].split(bytes([20]))
				#print(['ij', i, j, onset, duration, annots])
				annots = [_.decode('ascii') for _ in annots]
				del annots[-1]

				ret.append( (decimal.Decimal(onset.decode('ascii')), decimal.Decimal(duration.decode('ascii')), annots) )

			else:
				# no duration
				i = subdat.index(20)
				onset = subdat[0:i]
				annots = subdat[i+1:].split(bytes([20]))
				#print(['i', i, onset, duration, annots])
				annots = [_.decode('ascii') for _ in annots]
				del annots[-1]

				ret.append( (decimal.Decimal(onset.decode('ascii')), None, annots) )

		return ret

	@property
	def Format(self): return self._format
	@property
	def IsEDFPlus(self): return self._format.startswith("EDF+")

	@property
	def Signals(self): return self._signals

	@property
	def NumRecords(self): return self._num_records

	@property
	def NumSignals(self): return self._num_signals

	@property
	def Duration(self): return self._duration

	@property
	def Start(self): return self._start

	@contextlib.contextmanager
	def open(fname):
		with open(fname, 'rb') as f:
			o = EDFReader(f)
			yield o

	def writeWIFF(self, fname, props):
		with wiff.new(fname, props) as w:
			id_channelset = w.add_channelset(w.channel)

			frame_cnt = 0
			for frame in self._data:
				# Iterate over each data frame which translates to a single segment
				bb = wiff.blob_builder()

				# Iterate over each signal and push one data value from each single
				# into the blob builder to build up the frames of data
				for idx in range(len(frame[0])):
					for sig in range(len(self.Signals)):
						if self.Signals[sig]['Label'] == 'EDF Annotations':
							continue

						bb.add_i16(frame[sig][idx])

				# Store data for the entire segment in a blob
				id_blob = w.add_blob(bb.Bytes)

				# If 100 frames, then it would be 0-99 so subtrace 1 from the length
				w.add_segment(w.recording[1], w.channel, frame_cnt, frame_cnt + len(frame[0])-1, id_blob)

				# But this still is plus length as frame 100 is the next frame in the next segment
				frame_cnt += len(frame[0])

			w.add_meta_str(None, 'Recording.Software', 'iWorx LabScribe')
			w.add_meta_str(None, 'Recording.OriginalFilename', fname)
			w.add_meta_str(None, 'Recording.Type', 'EKG 6-lead')

def main():
	print(sys.argv)
	fname = sys.argv[1]

	wiff_fname = os.path.splitext(fname)[0] + '.wiff'

	print("Filename: %s" % fname)
	print("WIFF: %s" % wiff_fname)

	with EDFReader.open(fname) as f:
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
				'digitalminvalue': ch['DigitalMinimum'],
				'digitalmaxvalue': ch['DigitalMaximum'],
				'analogminvalue': ch['PhysicalMinimum'],
				'analogmaxvalue': ch['PhysicalMaximum'],
				'comment': '',
			})

		f.writeWIFF(wiff_fname, props)

if __name__ == '__main__':
	main()

