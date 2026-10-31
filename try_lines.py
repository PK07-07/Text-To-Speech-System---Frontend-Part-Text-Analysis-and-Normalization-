import sys
sys.stdout.reconfigure(encoding="utf-8")
from text_frontend import normalize

for line in open("my_sentences.txt", encoding="utf-8-sig"):
    line = line.rstrip("\n")
    if not line.strip():
        continue
    r = normalize(line, locale="en-US")  # use "en-IN" for Indian callers
    print(f"IN : {line}\nOUT: {r.normalized_text}\n     [{r.status}] {[(w.code, w.severity) for w in r.warnings]}\n")
