import sys
import csv
import math
from collections import Counter

REASONING = ["hasil_model_gpt.csv", "gemini.csv", "deepseek_think.csv"]
GERBANG = {"bukan alam", "bukan alam, iklim", "rusak", "rusak, pulih-manual"}
KOLOM_BOBOT = None


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def main():
    if len(sys.argv) < 3:
        print("Pakai: py triase_aturan.py banding_5model_501.csv sampel.csv")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]
    idx = []
    for p in REASONING:
        c = [i for i, k in enumerate(kepala) if i >= 2 and k.lower().endswith(p.lower())]
        if len(c) != 1:
            print("!! Kolom %r ditemukan %d kali" % (p, len(c)))
            return
        idx.append(c[0])

    with open(sys.argv[2], newline="", encoding="utf-8-sig") as f:
        rs = csv.reader(f)
        ks = next(rs)
        bs = [b for b in rs if b]
    ids = {b[0].strip() for b in baris}
    skor = [sum(1 for b in bs if b[i].strip() in ids) for i in range(len(ks))]
    i_id = max(range(len(ks)), key=lambda i: skor[i])
    if KOLOM_BOBOT:
        i_w = ks.index(KOLOM_BOBOT)
    else:
        c = [i for i, k in enumerate(ks) if "bobot" in k.lower() or "weight" in k.lower()]
        if len(c) != 1:
            print("!! Kolom bobot tidak tunggal. Kolom:", ks)
            return
        i_w = c[0]
    bobot = {b[i_id].strip(): float(b[i_w]) for b in bs if b[i_id].strip() in ids}

    unit = []
    for b in baris:
        uid, gold = b[0].strip(), b[1].strip()
        lab = [b[i].strip() for i in idx]
        top, cnt = Counter(lab).most_common(1)[0]
        unit.append({"w": bobot[uid], "gold": gold,
                     "sepakat": cnt == 3, "label": top,
                     "salah": not (cnt >= 2 and top == gold)})
    N, W = len(unit), sum(u["w"] for u in unit)
    E = sum(u["salah"] for u in unit)
    EW = sum(u["w"] for u in unit if u["salah"])
    print("Unit %d, bobot %.1f, kesalahan voting mayoritas %d (%.1f%%)\n" % (N, W, E, 100 * E / N))

    aturan = [
        ("R1 tidak disepakati", lambda u: not u["sepakat"]),
        ("R2 R1 + sepakat A3", lambda u: (not u["sepakat"]) or u["label"] == "A3"),
        ("R3 R1 + sepakat gerbang", lambda u: (not u["sepakat"]) or u["label"] in GERBANG),
        ("R4 R1 + A3 + gerbang", lambda u: (not u["sepakat"]) or u["label"] == "A3" or u["label"] in GERBANG),
    ]
    print("%-25s %15s %19s %26s" % ("Aturan", "beban tinjau", "kesalahan tertangkap", "akurasi label otomatis"))
    print("%-25s %7s %7s %9s %9s %10s %15s" % ("", "sampel", "bobot", "sampel", "bobot", "sampel", "SK Wilson 95%"))
    out = []
    for nama, f in aturan:
        tinjau = [u for u in unit if f(u)]
        otom = [u for u in unit if not f(u)]
        b_n = len(tinjau) / N
        b_w = sum(u["w"] for u in tinjau) / W
        t_n = sum(u["salah"] for u in tinjau) / E
        t_w = sum(u["w"] for u in tinjau if u["salah"]) / EW
        k = sum(1 for u in otom if not u["salah"])
        lo, hi = wilson(k, len(otom))
        aw = sum(u["w"] for u in otom if not u["salah"]) / sum(u["w"] for u in otom)
        print("%-25s %6.1f%% %6.1f%% %8.1f%% %8.1f%% %9.1f%%  [%4.1f, %4.1f]   (berbobot %.1f%%)"
              % (nama, 100 * b_n, 100 * b_w, 100 * t_n, 100 * t_w, 100 * k / len(otom), 100 * lo, 100 * hi, 100 * aw))
        out.append([nama, len(tinjau), round(b_n, 4), round(b_w, 4), round(t_n, 4), round(t_w, 4),
                    len(otom), round(k / len(otom), 4), round(lo, 4), round(hi, 4), round(aw, 4)])

    print("\nKesalahan yang masih lolos di bawah R4 (gold -> label otomatis):")
    sisa = Counter((u["gold"], u["label"]) for u in unit
                   if u["salah"] and not aturan[3][1](u))
    for (g, t), c in sisa.most_common(8):
        print("   %-20s -> %-20s %3d" % (g, t, c))
    print("   total: %d" % sum(sisa.values()))

    with open("triase_aturan_hasil.csv", "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["aturan", "n_tinjau", "beban_sampel", "beban_bobot", "tertangkap_sampel",
                    "tertangkap_bobot", "n_otomatis", "akurasi_otomatis", "wilson_bawah",
                    "wilson_atas", "akurasi_otomatis_bobot"])
        w.writerows(out)
    print("\nDitulis: triase_aturan_hasil.csv")


if __name__ == "__main__":
    main()
