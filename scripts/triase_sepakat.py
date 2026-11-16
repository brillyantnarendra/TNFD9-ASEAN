import sys
import csv
import math
from collections import Counter

REASONING = ["hasil_model_gpt.csv", "gemini.csv", "deepseek_think.csv"]
NONREASONING = ["deepseek.csv", "cohere.csv"]
KOLOM_ID_SAMPEL = None
KOLOM_BOBOT = None


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def cari_kolom(kepala, pola):
    c = [i for i, k in enumerate(kepala) if i >= 2 and k.lower().endswith(pola.lower())]
    if len(c) != 1:
        print("!! Kolom berakhiran %r ditemukan %d kali. Kolom tersedia:" % (pola, len(c)))
        for k in kepala:
            print("   ", k)
        sys.exit(1)
    return c[0]


def main():
    if len(sys.argv) < 2:
        print("Pakai: py triase_sepakat.py banding_5model_501.csv [sampel.csv]")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        kepala = next(r)
        baris = [b for b in r if b]
    ir = [cari_kolom(kepala, p) for p in REASONING]
    inr = [cari_kolom(kepala, p) for p in NONREASONING]
    print("Run reasoning   :", ", ".join(kepala[i] for i in ir))
    print("Run non-reasoning:", ", ".join(kepala[i] for i in inr))

    bobot = None
    if len(sys.argv) >= 3:
        with open(sys.argv[2], newline="", encoding="utf-8-sig") as f:
            rs = csv.reader(f)
            ks = next(rs)
            bs = [b for b in rs if b]
        ids = {b[0].strip() for b in baris}
        if KOLOM_ID_SAMPEL:
            i_id = ks.index(KOLOM_ID_SAMPEL)
        else:
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
        print("Bobot dibaca untuk %d unit, jumlah %.1f" % (len(bobot), sum(bobot.values())))

    n = len(baris)
    print("Unit: %d\n" % n)
    hasil = []

    def analisis(judul, idx):
        print("=" * 72)
        print(judul)
        print("=" * 72)
        kel = {"semua sepakat": [], "mayoritas (bukan semua)": [], "tanpa mayoritas": []}
        benar_mayoritas = 0
        sisa_salah = Counter()
        for b in baris:
            gold = b[1].strip()
            lab = [b[i].strip() for i in idx]
            top, cnt = Counter(lab).most_common(1)[0]
            if cnt == len(idx):
                kel["semua sepakat"].append((b[0].strip(), gold, top))
                if top != gold:
                    sisa_salah[(gold, top)] += 1
            elif cnt * 2 > len(idx):
                kel["mayoritas (bukan semua)"].append((b[0].strip(), gold, top))
            else:
                kel["tanpa mayoritas"].append((b[0].strip(), gold, None))
            if cnt * 2 > len(idx) and top == gold:
                benar_mayoritas += 1
        print("%-26s %6s %8s %9s  %-17s %s" % ("Kelompok", "n", "cakupan", "akurasi", "SK Wilson 95%", "berbobot (cakupan / akurasi)"))
        for nama, isi in kel.items():
            m = len(isi)
            if m == 0:
                continue
            k = sum(1 for _, g, t in isi if t == g)
            lo, hi = wilson(k, m)
            teks_w = ""
            if bobot:
                W = sum(bobot.values())
                w = sum(bobot[u] for u, _, _ in isi)
                wk = sum(bobot[u] for u, g, t in isi if t == g)
                teks_w = "%5.1f%% / %s" % (100 * w / W, ("%5.1f%%" % (100 * wk / w)) if nama != "tanpa mayoritas" else "    -")
            akur = "%7.1f%%" % (100 * k / m) if nama != "tanpa mayoritas" else "      -"
            sk = "[%4.1f, %4.1f]" % (100 * lo, 100 * hi) if nama != "tanpa mayoritas" else ""
            print("%-26s %6d %7.1f%% %9s  %-17s %s" % (nama, m, 100 * m / n, akur, sk, teks_w))
            hasil.append([judul, nama, m, round(m / n, 4),
                          round(k / m, 4) if nama != "tanpa mayoritas" else "",
                          round(lo, 4) if nama != "tanpa mayoritas" else "",
                          round(hi, 4) if nama != "tanpa mayoritas" else ""])
        print("\nVoting mayoritas (unit tanpa mayoritas dihitung salah): akurasi %.1f%% (%d/%d)"
              % (100 * benar_mayoritas / n, benar_mayoritas, n))
        tunggal = [(kepala[i], sum(1 for b in baris if b[i].strip() == b[1].strip()) / n) for i in idx]
        for nm, a in tunggal:
            print("   run tunggal %-45s %.1f%%" % (nm[-45:], 100 * a))
        print("\nKesalahan yang tersisa pada unit 'semua sepakat' (gold -> label bersama):")
        tot = sum(sisa_salah.values())
        for (g, t), c in sisa_salah.most_common(8):
            print("   %-20s -> %-20s %3d" % (g, t, c))
        print("   total salah meski semua sepakat: %d dari %d" % (tot, len(kel["semua sepakat"])))
        print()

    analisis("TIGA RUN REASONING (GPT-6 Astra, Gemini, DeepSeek thinking)", ir)
    analisis("KELIMA RUN (pembanding)", ir + inr)

    with open("triase_sepakat_hasil.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["himpunan", "kelompok", "n", "cakupan", "akurasi", "wilson_bawah", "wilson_atas"])
        w.writerows(hasil)
    print("Ditulis: triase_sepakat_hasil.csv")


if __name__ == "__main__":
    main()
