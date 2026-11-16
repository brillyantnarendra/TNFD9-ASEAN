import csv
import math
import random
import sys
from collections import Counter

RUN = [
    ("GPT-6 Astra*", "hasil_model_gpt.csv"),
    ("Gemini 3.8 Flash*", "gemini.csv"),
    ("DeepSeek V4 (T)*", "deepseek_think.csv"),
    ("DeepSeek V4", "deepseek.csv"),
    ("Command A", "cohere.csv"),
]
REASONING = ["GPT-6 Astra*", "Gemini 3.8 Flash*", "DeepSeek V4 (T)*"]
GERBANG = {"bukan alam", "bukan alam, iklim", "rusak"}


class Catat:

    def __init__(self, nama):
        self.f = open(nama, "w", encoding="utf-8")
        self.nama = nama

    def __call__(self, *a):
        s = " ".join(str(x) for x in a)
        print(s)
        self.f.write(s + "\n")

    def tutup(self):
        self.f.close()
        print("\nDitulis: %s" % self.nama)


def norm(t):
    t = (t or "").strip()
    if t.lower().startswith("rusak"):
        return "rusak"
    return t


def grup(t):
    t = norm(t)
    if t in ("A1", "A2", "A3", "A4"):
        return "A"
    if t in ("B1", "B2", "B3", "B4", "B5"):
        return "B"
    return "G"


def baca_banding(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]
    kol = {}
    for nama, akhir in RUN:
        c = [i for i, k in enumerate(kepala) if i >= 2 and k.lower().endswith(akhir.lower())]
        if len(c) != 1:
            print("!! Kolom berakhiran %r ditemukan %d kali di %s" % (akhir, len(c), path))
            print("   Kolom tersedia:", kepala)
            sys.exit(1)
        kol[nama] = c[0]
    ids = [b[0].strip() for b in baris]
    gold = {b[0].strip(): norm(b[1]) for b in baris}
    lab = {nama: {b[0].strip(): norm(b[i]) for b in baris} for nama, i in kol.items()}
    return ids, gold, lab


def baca_bobot(path, ids):
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = list(csv.DictReader(f))
    w = {b["id"].strip(): float(b["bobot"]) for b in r if b["id"].strip() in set(ids)}
    hilang = [u for u in ids if u not in w]
    if hilang:
        print("!! %d id tanpa bobot, contoh: %s" % (len(hilang), hilang[:5]))
        sys.exit(1)
    return w


def kappa(a, b):
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def bootstrap_kappa(a, b, ulang=2000, benih=20261109):
    rng = random.Random(benih)
    n = len(a)
    nilai = []
    for _ in range(ulang):
        ix = [rng.randrange(n) for _ in range(n)]
        k = kappa([a[i] for i in ix], [b[i] for i in ix])
        if not math.isnan(k):
            nilai.append(k)
    nilai.sort()
    return nilai[int(0.025 * len(nilai))], nilai[int(0.975 * len(nilai)) - 1]


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
