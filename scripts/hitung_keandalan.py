import sys
import os
import re
import csv
import random
import itertools
import collections

try:
    from openpyxl import load_workbook
except ImportError:
    print("openpyxl belum terpasang.  py -m pip install openpyxl")
    sys.exit(1)

KELAS = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5"]
GERBANG = ["rusak", "rusak, pulih-manual", "bukan alam", "bukan alam, iklim"]
RAGU = "ragu - anteseden hilang"

KANDIDAT = {
    "id":      ["id", "id_unit", "idunit", "no", "nomor", "no_unit"],
    "kode":    ["kode", "kode_akhir", "kode_final", "kode_koder", "kelas"],
    "catatan": ["catatan", "catatan_gerbang", "gerbang", "ket", "keterangan"],
    "bukti":   ["kalimat_bukti", "bukti", "kutipan", "kalimat"],
}


def bersih(v):
    return "" if v is None else str(v).strip()


def kunci(v):
    return bersih(v).lower().replace(" ", "_").replace("-", "_")


def bakukan_catatan(v):
    asli = bersih(v)
    if asli == "":
        return ""
    t = asli.lower().replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t).strip().rstrip(". ").strip()
    if t.startswith("rusak") and "pulih" in t:
        return "rusak, pulih-manual"
    if t == "rusak":
        return "rusak"
    if t.startswith("bukan alam") and "iklim" in t:
        return "bukan alam, iklim"
    if t.startswith("bukan alam"):
        return "bukan alam"
    if t.startswith("ragu") and "anteseden" in t:
        return RAGU
    return asli


def bakukan_kode(v):
    a = bersih(v)
    return re.sub(r"\s+", "", a).upper() if a else ""


SKEMA = ("penuh", "ab", "pilar")


def petakan_skema(lab, skema):
    if skema == "penuh":
        return lab
    if lab not in KELAS:
        return "GERBANG"
    if skema == "ab":
        return "A" if lab[0] == "A" else "B"
    if skema == "pilar":
        return lab if lab[0] == "A" else "B"
    return lab


def cari_header(ws, batas=20):
    for r in range(1, min(batas, ws.max_row or 1) + 1):
        nilai = [kunci(c.value) for c in ws[r]]
        if any(n in KANDIDAT["kode"] for n in nilai):
            return r, nilai
    return None, None


def baca_lembar(path, lebur=False):
    wb = load_workbook(path, data_only=True, read_only=True)
    target = None
    for ws in wb.worksheets:
        r, nilai = cari_header(ws)
        if r:
            target = (ws, r, nilai)
            break
    if not target:
        raise RuntimeError("tidak menemukan baris header yang memuat kolom 'kode' "
                           "(lembar: %s)" % ", ".join(w.title for w in wb.worksheets))
    ws, baris_header, nilai = target

    peta_kol = {}
    for peran, kand in KANDIDAT.items():
        for k in kand:
            if k in nilai:
                peta_kol[peran] = nilai.index(k)
                break
    for wajib in ("id", "kode", "catatan"):
        if wajib not in peta_kol:
            raise RuntimeError("kolom '%s' tidak ditemukan di %s" % (wajib, os.path.basename(path)))

    label, ragu, cacat = {}, {}, []
    for r, row in enumerate(ws.iter_rows(min_row=baris_header + 1, values_only=True),
                            start=baris_header + 1):
        if row is None:
            continue

        def sel(peran):
            i = peta_kol.get(peran)
            return bersih(row[i]) if i is not None and i < len(row) else ""

        vid = sel("id")
        kode = bakukan_kode(sel("kode"))
        cat = bakukan_catatan(sel("catatan"))
        if not (vid or kode or cat):
            continue
        if not vid:
            cacat.append("baris %d tanpa id" % r)
            continue

        if kode:
            if kode not in KELAS:
                cacat.append("id %s: kode tidak sah %r" % (vid, kode))
                continue
            if cat in GERBANG:
                cacat.append("id %s: BERTENTANGAN - kode %s tetapi catatan %r "
                             "(dipakai kodenya)" % (vid, kode, cat))
            lab = kode
        elif cat in GERBANG:
            lab = "GERBANG" if lebur else cat
        elif cat == RAGU:
            cacat.append("id %s: 'ragu' tetapi kode kosong" % vid)
            continue
        elif cat:
            cacat.append("id %s: catatan tidak sah %r" % (vid, cat))
            continue
        else:
            continue

        if vid in label and label[vid] != lab:
            cacat.append("id %s muncul dua kali dengan label berbeda" % vid)
        label[vid] = lab
        ragu[vid] = (cat == RAGU)

    return label, ragu, os.path.basename(path), cacat


def krippendorff_alpha(kolom):
    o = collections.Counter()
    for labs in kolom:
        m = len(labs)
        if m < 2:
            continue
        for a, b in itertools.permutations(labs, 2):
            o[(a, b)] += 1.0 / (m - 1)
    if not o:
        return None
    n_c = collections.Counter()
    for (a, b), v in o.items():
        n_c[a] += v
    n = sum(n_c.values())
    if n <= 1:
        return None
    do = sum(v for (a, b), v in o.items() if a != b)
    de = sum(n_c[a] * n_c[b] for a in n_c for b in n_c if a != b) / (n - 1.0)
    if de == 0:
        return 1.0 if do == 0 else None
    return 1.0 - do / de


def scott_pi(x, y):
    n = len(x)
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    gab = collections.Counter(x) + collections.Counter(y)
    pe = sum((v / (2.0 * n)) ** 2 for v in gab.values())
    return (po - pe) / (1 - pe) if pe != 1 else None


def cohen_kappa(x, y):
    n = len(x)
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    cx, cy = collections.Counter(x), collections.Counter(y)
    pe = sum((cx[k] / n) * (cy[k] / n) for k in set(cx) | set(cy))
    k = (po - pe) / (1 - pe) if pe != 1 else None
    return po, pe, k


def pabak(po, n_kat):
    if n_kat < 2:
        return None
    c = 1.0 / n_kat
    return (po - c) / (1 - c)


def byrt_pi_bi(x, y, kat):
    n = len(x)
    hasil = []
    for k in kat:
        a = sum(1 for p, q in zip(x, y) if p == k and q == k)
        d = sum(1 for p, q in zip(x, y) if p != k and q != k)
        b = sum(1 for p, q in zip(x, y) if p == k and q != k)
        c = sum(1 for p, q in zip(x, y) if p != k and q == k)
        if a + b + c == 0:
            continue
        pi = abs(a - d) / float(n)
        bi = abs(b - c) / float(n)
        po = (a + d) / float(n)
        hasil.append((k, a + b, a + c, po, pi, bi))
    return hasil


def landis_koch(a):
    if a is None:
        return "-"
    if a < 0.00:
        return "lebih buruk dari acak"
    if a < 0.21:
        return "kecil (slight)"
    if a < 0.41:
        return "lumayan (fair)"
    if a < 0.61:
        return "sedang (moderate)"
    if a < 0.81:
        return "kuat (substantial)"
    return "hampir sempurna"


AMIN = (0.90, 0.80, 0.70, 0.667, 0.60, 0.50)


def _alpha_dari_pasangan(pasangan):
    o = collections.Counter()
    for a, b, m in pasangan:
        w = 1.0 / (m - 1)
        o[(a, b)] += w
        o[(b, a)] += w
    if not o:
        return None
    n_c = collections.Counter()
    for (a, b), v in o.items():
        n_c[a] += v
    n = sum(n_c.values())
    if n <= 1:
        return None
    do = sum(v for (a, b), v in o.items() if a != b)
    de = sum(n_c[a] * n_c[b] for a in n_c for b in n_c if a != b) / (n - 1.0)
    if de == 0:
        return 1.0 if do == 0 else None
    return 1.0 - do / de


def bootstrap_alpha(unit_labels, ulang=5000, benih=20260922):
    pasangan = []
    for labs in unit_labels.values():
        m = len(labs)
        if m < 2:
            continue
        for a, b in itertools.combinations(labs, 2):
            pasangan.append((a, b, m))
    if not pasangan:
        return None, None, None
    rng = random.Random(benih)
    N = len(pasangan)
    nilai = []
    for _ in range(ulang):
        ambil = [pasangan[rng.randrange(N)] for _ in range(N)]
        a = _alpha_dari_pasangan(ambil)
        if a is not None:
            nilai.append(a)
    if len(nilai) < 100:
        return None, None, None
    nilai.sort()
    lo = nilai[int(0.025 * len(nilai))]
    hi = nilai[min(len(nilai) - 1, int(0.975 * len(nilai)))]
    q = {am: sum(1 for v in nilai if v < am) / float(len(nilai)) for am in AMIN}
    return lo, hi, q


def garis(judul):
    print()
    print("=" * 74)
    print(judul)
    print("=" * 74)


def utama():
    arg = sys.argv[1:]
    emas = None
    koder = []
    ulang = 5000
    lebur = False
    skema = "penuh"
    keluar = None
    i = 0
    while i < len(arg):
        a = arg[i]
        if a == "--emas":
            i += 1; emas = arg[i]
        elif a == "--koder":
            i += 1; koder.append(arg[i])
        elif a == "--ulang":
            i += 1; ulang = int(arg[i])
        elif a == "--lebur":
            lebur = True
        elif a == "--skema":
            i += 1; skema = arg[i]
            if skema not in SKEMA:
                print("Skema harus salah satu dari: %s" % ", ".join(SKEMA)); return
        elif a == "--keluar":
            i += 1; keluar = arg[i]
        else:
            print("Argumen tidak dikenal: %s" % a); return
        i += 1

    if not emas or not koder:
        print("Argumen tidak lengkap.")
        return

    berkas = [emas] + koder
    lembar = []
    for p in berkas:
        if not os.path.exists(p):
            print("Tidak ditemukan: %s" % p); return
        try:
            lembar.append(baca_lembar(p, lebur=lebur))
        except RuntimeError as e:
            print("!! %s: %s" % (os.path.basename(p), e)); return

    garis("BERKAS DAN CACAT BENTUK")
    for lab, rg, nama, cacat in lembar:
        print("  %-46s %5d unit berlabel" % (nama, len(lab)))
        for c in cacat[:12]:
            print("        !! %s" % c)
        if len(cacat) > 12:
            print("        !! ... (+%d lagi)" % (len(cacat) - 12))

    irisan = set(lembar[0][0])
    for lab, _, _, _ in lembar[1:]:
        irisan &= set(lab)
    ids = sorted(irisan, key=lambda x: (len(x), x))

    garis("HIMPUNAN UNIT")
    for lab, _, nama, _ in lembar:
        print("  %-46s %5d" % (nama, len(lab)))
    print("  %-46s %5d   <== dipakai" % ("IRISAN (unit berlabel di semua berkas)", len(ids)))
    kurang = [nama for lab, _, nama, _ in lembar if len(lab) != len(ids)]
    if kurang:
        print("  %s memuat unit di luar irisan."
              % ", ".join(kurang))
    if not ids:
        print("  !! Irisan kosong."); return

    if skema != "penuh":
        for lab, _, _, _ in lembar:
            for k in list(lab):
                lab[k] = petakan_skema(lab[k], skema)

    kolom = {nama: [lab[i] for i in ids] for lab, _, nama, _ in lembar}
    nama_semua = [nama for _, _, nama, _ in lembar]

    garis("SKEMA YANG DIPAKAI: %s" % skema.upper())
    print({"penuh": "  9 kelas + tiap gerbang sebagai kategori sendiri",
           "ab": "  A (A1-A4) / B (B1-B5) / GERBANG  -> 3 kategori",
           "pilar": "  A1 A2 A3 A4 terpisah + B dilebur + GERBANG -> 6 kategori"}[skema])

    garis("SEBARAN LABEL")
    kat = sorted({v for c in kolom.values() for v in c},
                 key=lambda k: (KELAS.index(k) if k in KELAS else 90 + len(k), k))
    lebar = max(len(k) for k in kat) + 2
    print("  %-*s %s" % (lebar, "label", "  ".join("%12s" % n[:12] for n in nama_semua)))
    for k in kat:
        print("  %-*s %s" % (lebar, k, "  ".join(
            "%12d" % kolom[n].count(k) for n in nama_semua)))
    print("  %-*s %s" % (lebar, "TOTAL", "  ".join("%12d" % len(ids) for _ in nama_semua)))

    garis("ALPHA KRIPPENDORFF  (utama, %d koder, metrik nominal)" % len(lembar))
    unit_labels = {i: [lab[i] for lab, _, _, _ in lembar] for i in ids}
    alpha = krippendorff_alpha(list(unit_labels.values()))
    print("  n unit          : %d" % len(ids))
    print("  n kategori      : %d" % len(kat))
    print("  alpha           : %.4f" % alpha)
    print("  tafsiran        : %s  (Landis & Koch)" % landis_koch(alpha))
    lo, hi, q = bootstrap_alpha(unit_labels, ulang=ulang)
    if lo is not None:
        print("  SK 95%% bootstrap : [%.4f, %.4f]" % (lo, hi))
        print("                     %d ulangan, PASANGAN PENILAIAN diambil ulang" % ulang)
        print("                     (prosedur Hayes & Krippendorff 2007)")
        print()
        print("  q = peluang alpha sebenarnya BERADA DI BAWAH alpha_min")
        print("      %-10s %s" % ("alpha_min", "q"))
        for am in AMIN:
            print("      %-10.3f %.4f" % (am, q[am]))

    garis("KAPPA COHEN BERPASANGAN  (diagnosis) + DEKOMPOSISI BYRT")
    for a, b in itertools.combinations(nama_semua, 2):
        x, y = kolom[a], kolom[b]
        po, pe, k = cohen_kappa(x, y)
        pb = pabak(po, len(kat))
        pi_sc = scott_pi(x, y)
        print()
        print("  %s  vs  %s" % (a, b))
        print("    sepakat        : %d / %d" % (sum(1 for p, q in zip(x, y) if p == q), len(x)))
        print("    Po             : %.4f" % po)
        print("    Pe             : %.4f" % pe)
        print("    kappa Cohen    : %.4f   (%s)" % (k, landis_koch(k)))
        print("    Scott pi       : %.4f" % pi_sc)
        print("    PABAK          : %.4f   ((Po - 1/k)/(1 - 1/k), k=%d)" % (pb, len(kat)))
        rinci = byrt_pi_bi(x, y, kat)
        if rinci:
            print("    PI dan BI per kategori (satu-lawan-sisanya):")
            print("      %-22s %5s %5s %7s %7s %7s" % ("kategori", "n(A)", "n(B)", "Po", "PI", "BI"))
            for k2, na, nb, po2, pi2, bi2 in rinci:
                print("      %-22s %5d %5d %7.3f %7.3f %7.3f" % (k2, na, nb, po2, pi2, bi2))

    garis("KETAKSEPAKATAN TERBANYAK  (pasangan label, semua pasangan koder)")
    beda = collections.Counter()
    for i in ids:
        labs = unit_labels[i]
        for p, q in itertools.combinations(labs, 2):
            if p != q:
                beda[tuple(sorted((p, q)))] += 1
    if not beda:
        print("  Tidak ada ketaksepakatan.")
    else:
        for (p, q), n in beda.most_common(20):
            print("  %-22s <-> %-22s %4d" % (p, q, n))
        print()
        print("  Unit yang ketiga koder berbeda semua:")
        tiga = [i for i in ids if len(set(unit_labels[i])) == len(unit_labels[i]) >= 3]
        print("    %s" % (", ".join(tiga) if tiga else "tidak ada"))

    garis("PENANDA 'ragu - anteseden hilang'  (dilaporkan terpisah)")
    for lab, rg, nama, _ in lembar:
        print("  %-46s %5d unit" % (nama, sum(1 for i in ids if rg.get(i))))
    kol_ragu = [[1 if rg.get(i) else 0 for lab, rg, _, _ in lembar] for i in ids]
    a_ragu = krippendorff_alpha([[str(v) for v in r] for r in kol_ragu])
    if a_ragu is not None:
        print("  alpha penanda ragu : %.4f" % a_ragu)

    if keluar:
        with open(keluar, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id"] + nama_semua + ["sepakat_semua"])
            for i in ids:
                labs = unit_labels[i]
                w.writerow([i] + labs + [int(len(set(labs)) == 1)])
        print()
        print("  Label per unit ditulis ke: %s" % keluar)

    print()


if __name__ == "__main__":
    utama()
