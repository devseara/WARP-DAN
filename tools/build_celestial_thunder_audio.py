"""Convert the credited NPS public-domain field recording into the native thunder cue."""
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'Inputs/CelestialDial/audio-source/nps-thunder.mp3'
expected='54d6a7fc85b5c7b0c65dd36ff3c5f398d698c37e733bfc98a234a6724c2d0a49'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
samples,rate=sf.read(source,dtype='float64',always_2d=True)
assert rate==44100
samples=samples.mean(axis=1)[int(2.9*rate):int(11.4*rate)]
# Preserve the natural crack/rolling decay, with only short boundary fades.
samples[:441]*=np.linspace(0,1,441)
samples[-int(1.5*rate):]*=np.linspace(1,0,int(1.5*rate))
samples*=.85/np.max(np.abs(samples))
# Band-limit before the exact 2:1 conversion to the established native PCM rate.
n=np.arange(-31,32,dtype='float64')
kernel=np.sinc(.45*n)*np.hamming(63);kernel/=kernel.sum()
samples=np.convolve(samples,kernel,mode='same')[::2]
path=ROOT/'Inputs/CelestialDial/boh_thunder_01.wav'
sf.write(path,samples,22050,subtype='PCM_16')
report={'source_sha256':expected,'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'start_seconds':2.9,'end_seconds':11.4,'rate':22050,'channels':1,'frames':len(samples),
        'source_page':'https://www.nps.gov/subjects/sound/sounds-thunder.htm',
        'download':'https://www.nps.gov/nps-audiovideo/legacy/mp3/nri/avElement/nri-Thunder.mp3',
        'credit':'National Park Service, Natural Sounds and Night Skies Division',
        'license':'Public domain','license_page':'https://www.nps.gov/subjects/sound/gallery.htm'}
path.with_suffix('.source.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
