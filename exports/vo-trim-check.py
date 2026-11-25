import numpy as np
from scipy.io import wavfile
from pathlib import Path
root=Path(r"C:\Users\rohit\OneDrive\Documents\Default Project\exports\vo")
starts={1:.25,2:6.35,3:13.35,4:21.0,5:29.6,6:39.5,7:48.5,8:54.25}
for i in range(1,9):
    sr,d=wavfile.read(str(root/f"vo-s{i}.wav"))
    x=d.astype(np.float32)/32768.0
    pk=np.max(np.abs(x)); thr=max(0.008, pk*0.02)
    idx=np.where(np.abs(x)>thr)[0]
    lead=idx[0]/sr; trail=(len(x)-1-idx[-1])/sr
    print(f"s{i}: total {len(x)/sr:.2f}s lead {lead:.2f} trail {trail:.2f} speech {len(x)/sr-lead-trail:.2f}s  start {starts[i]} -> end {starts[i]+len(x)/sr:.2f}")
