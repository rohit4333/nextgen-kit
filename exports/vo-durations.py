from scipy.io import wavfile
from pathlib import Path
for i in range(1,9):
    p=Path(r"C:\Users\rohit\OneDrive\Documents\Default Project\exports\vo")/f"vo-s{i}.wav"
    sr,d=wavfile.read(str(p)); print(i, round(len(d)/sr,2), "s", d.shape)
