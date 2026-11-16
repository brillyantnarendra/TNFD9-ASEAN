import sys
import os
import re
import csv
import math
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
SUPPORT_MIN = 10

KAND = {
    "id":      ["id", "id_unit", "idunit", "no", "nomor", "no_unit"],
    "kode":    ["kode", "kode_akhir", "kode_final", "kelas"],
    "catatan": ["catatan", "catatan_gerbang", "gerbang", "ket", "keterangan"],
    "galat":   ["galat", "error", "kesalahan"],
}


def bersih(v):
    return "" if v is None else str(v).strip()


def kunci(v):
    return bersih(v).lower().replace(" ", "_").replace("-", "_")


def bakukan_catatan(v):
    a = bersih(v)
    if a == "":
        return ""
    t = a.lower().replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t).strip().rstrip(". ").strip()
    if t.startswith("rusak") and "pulih" in t:
        return "rusak"
    if t == "rusak":
        return "rusak"
    if t.startswith("bukan alam") and "iklim" in t:
        return "bukan alam, iklim"
    if t.startswith("bukan alam"):
        return "bukan alam"
    if t.startswith("ragu") and "anteseden" in t:
        return RAGU
    return a


def bakukan_kode(v):
    a = bersih(v)
    return re.sub(r"\s+", "", a).upper() if a else ""


def label_efektif(kode, cat):
    if kode:
        return kode if kode in KELAS else None
    if cat in GERBANG:
        return cat
    return None


def baca_xlsx(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        for r in range(1, min(20, ws.max_row or 1) + 1):
            nilai = [kunci(c.value) for c in ws[r]]
            if any(n in KAND["kode"] for n in nilai):
                peta = {}
                for peran, kand in KAND.items():
                    for k in kand:
                        if k in nilai:
                            peta[peran] = nilai.index(k)
                            break
                out = {}
                for row in ws.iter_rows(min_row=r + 1, values_only=True):
                    if row is None:
                        continue

                    def sel(p):
                        i = peta.get(p)
                        return bersih(row[i]) if i is not None and i < len(row) else ""

                    vid = sel("id")
                    if not vid:
                        continue
                    lab = label_efektif(bakukan_kode(sel("kode")),
                                        bakukan_catatan(sel("catatan")))
                    if lab:
                        out[vid] = lab
                return out
    raise RuntimeError("kolom 'kode' tidak ditemukan di %s" % os.path.basename(path))


def baca_csv(path):
    out, galat, cacat = {}, 0, []
    with open(path, newline="", encoding="utf-8-sig") as f:
        baca = csv.DictReader(f)
        peta = {}
        kol = {kunci(h): h for h in (baca.fieldnames or [])}
        for peran, kand in KAND.items():
            for k in kand:
                if k in kol:
                    peta[peran] = kol[k]
                    break
        if "kode" not in peta or "id" not in peta:
            raise RuntimeError("kolom 'id' atau 'kode' tidak ditemukan di %s"
                               % os.path.basename(path))
        for baris in baca:
            vid = bersih(baris.get(peta["id"]))
            if not vid:
                continue
            if "galat" in peta and bersih(baris.get(peta["galat"])):
                galat += 1
                continue
            kode = bakukan_kode(baris.get(peta["kode"]))
            cat = bakukan_catatan(baris.get(peta.get("catatan"), ""))
            lab = label_efektif(kode, cat)
            if lab is None:
                cacat.append(vid)
                continue
            out[vid] = lab
    return out, galat, cacat


def prf(emas, duga, kelas):
    tp = sum(1 for g, d in zip(emas, duga) if g == kelas and d == kelas)
    fp = sum(1 for g, d in zip(emas, duga) if g != kelas and d == kelas)
    fn = sum(1 for g, d in zip(emas, duga) if g == kelas and d != kelas)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f, tp + fn


def macro_f1(emas, duga, kelas_hadir):
    fs = [prf(emas, duga, k)[2] for k in kelas_hadir]
    return sum(fs) / len(fs) if fs else 0.0


def micro_f1(emas, duga):
    return sum(1 for g, d in zip(emas, duga) if g == d) / len(emas)


def mcc_multikelas(emas, duga):
    kelas = sorted(set(emas) | set(duga))
    s = len(emas)
    c = sum(1 for g, d in zip(emas, duga) if g == d)
    t = {k: sum(1 for g in emas if g == k) for k in kelas}
    p = {k: sum(1 for d in duga if d == k) for k in kelas}
    atas = c * s - sum(p[k] * t[k] for k in kelas)
    b1 = s * s - sum(p[k] ** 2 for k in kelas)
    b2 = s * s - sum(t[k] ** 2 for k in kelas)
    if b1 <= 0 or b2 <= 0:
        return None
    return atas / math.sqrt(b1 * b2)


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


def cohen_kappa(x, y):
    n = len(x)
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    cx, cy = collections.Counter(x), collections.Counter(y)
    pe = sum((cx[k] / n) * (cy[k] / n) for k in set(cx) | set(cy))
    return po, (po - pe) / (1 - pe) if pe != 1 else None


def bootstrap(emas, duga, kelas_hadir, ulang, benih=20260922):
    rng = random.Random(benih)
    n = len(emas)
    mf, ak = [], []
    for _ in range(ulang):
        idx = [rng.randrange(n) for _ in range(n)]
        e = [emas[i] for i in idx]
        d = [duga[i] for i in idx]
        mf.append(macro_f1(e, d, kelas_hadir))
        ak.append(micro_f1(e, d))
    def sk(v):
        v.sort()
        return v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]
    return sk(mf), sk(ak)


def garis(judul):
    print()
    print("=" * 78)
    print(judul)
    print("=" * 78)


def nilai(nama, emas_peta, duga_peta, ulang, galat, cacat):
    ids = sorted(set(emas_peta) & set(duga_peta), key=lambda x: (len(x), x))
    garis("MODEL: %s" % nama)
    print("  Unit di gold standard        : %d" % len(emas_peta))
    print("  Unit di keluaran model       : %d" % len(duga_peta))
    print("  Dinilai (irisan)             : %d" % len(ids))
    if galat:
        print("  Baris bergalat, dilewati     : %d" % galat)
    if cacat:
        print("  Label model tidak sah        : %d  -> %s" %
              (len(cacat), ", ".join(cacat[:15]) + (" ..." if len(cacat) > 15 else "")))
    if not ids:
        print("  !! Irisan kosong."); return None

    emas = [emas_peta[i] for i in ids]
    duga = [duga_peta[i] for i in ids]
    kelas_hadir = sorted(set(emas) | set(duga),
                         key=lambda k: (KELAS.index(k) if k in KELAS else 90, k))

    ak = micro_f1(emas, duga)
    mf = macro_f1(emas, duga, kelas_hadir)
    mcc = mcc_multikelas(emas, duga)
    po, kap = cohen_kappa(emas, duga)

    print()
    print("  RINGKAS")
    print("  -------")
    print("  Akurasi / micro-F1           : %.4f  (%d/%d tepat)"
          % (ak, sum(1 for a, b in zip(emas, duga) if a == b), len(ids)))
    print("  macro-F1 (semua kelas hadir) : %.4f" % mf)
    if mcc is not None:
        print("  MCC multikelas               : %.4f" % mcc)
    print("  kappa Cohen model vs emas    : %.4f" % kap)

    (mf_lo, mf_hi), (ak_lo, ak_hi) = bootstrap(emas, duga, kelas_hadir, ulang)
    print("  SK 95%% macro-F1              : [%.4f, %.4f]  (%d ulangan)" % (mf_lo, mf_hi, ulang))
    print("  SK 95%% akurasi               : [%.4f, %.4f]" % (ak_lo, ak_hi))

    print()
    print("  PER KELAS  (support = jumlah di gold standard)")
    print("  %-22s %8s %8s %8s %8s" % ("kelas", "presisi", "recall", "F1", "support"))
    kuat = []
    for k in kelas_hadir:
        p, r, f, sup = prf(emas, duga, k)
        tanda = "" if sup >= SUPPORT_MIN else "   (support < %d)" % SUPPORT_MIN
        print("  %-22s %8.3f %8.3f %8.3f %8d%s" % (k, p, r, f, sup, tanda))
        if sup >= SUPPORT_MIN:
            kuat.append(f)
    if kuat:
        print("  %-22s %8s %8s %8.3f %8s" %
              ("macro-F1 (support>=%d)" % SUPPORT_MIN, "", "", sum(kuat) / len(kuat), ""))

    print()
    print("  MATRIKS KEBINGUNGAN  (baris = emas, kolom = model)")
    lab = kelas_hadir
    print("  %-20s %s" % ("", " ".join("%6s" % (k[:6]) for k in lab)))
    for g in lab:
        baris = [sum(1 for a, b in zip(emas, duga) if a == g and b == d) for d in lab]
        print("  %-20s %s" % (g[:20], " ".join("%6d" % v for v in baris)))

    print()
    print("  SALAH TERBANYAK  (emas -> model)")
    salah = collections.Counter((a, b) for a, b in zip(emas, duga) if a != b)
    for (a, b), n in salah.most_common(12):
        print("    %-22s -> %-22s %4d" % (a, b, n))

    print()
    print("  KEPUTUSAN GERBANG  (rusak / bukan alam / bukan alam, iklim)")
    ge = [1 if e in GERBANG else 0 for e in emas]
    gd = [1 if d in GERBANG else 0 for d in duga]
    tp = sum(1 for a, b in zip(ge, gd) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(ge, gd) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(ge, gd) if a == 1 and b == 0)
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    print("    gerbang menurut emas       : %d" % sum(ge))
    print("    gerbang menurut model      : %d" % sum(gd))
    print("    presisi / recall / F1      : %.3f / %.3f / %.3f" % (pr, rc, f1))
    po2, kap2 = cohen_kappa([str(v) for v in ge], [str(v) for v in gd])
    print("    kappa keputusan gerbang    : %.4f" % kap2)

    return {"nama": nama, "ids": ids, "duga": duga_peta}


def utama():
    arg = sys.argv[1:]
    emas = None
    model = []
    ulang = 5000
    keluar = None
    hanya = None
    i = 0
    while i < len(arg):
        a = arg[i]
        if a == "--emas":
            i += 1; emas = arg[i]
        elif a == "--model":
            i += 1; model.append(arg[i])
        elif a == "--ulang":
            i += 1; ulang = int(arg[i])
        elif a == "--keluar":
            i += 1; keluar = arg[i]
        elif a == "--hanya-id":
            i += 1; hanya = arg[i]
        else:
            print("Argumen tidak dikenal: %s" % a); return
        i += 1

    if not emas or not model:
        print("Argumen tidak lengkap."); return
    for p in [emas] + model:
        if not os.path.exists(p):
            print("Tidak ditemukan: %s" % p); return

    try:
        emas_peta = baca_xlsx(emas) if emas.lower().endswith((".xlsx", ".xlsm")) \
            else baca_csv(emas)[0]
    except RuntimeError as e:
        print("!! %s" % e); return

    if hanya:
        if not os.path.exists(hanya):
            print("Tidak ditemukan: %s" % hanya); return
        pilih = set()
        with open(hanya, newline="", encoding="utf-8-sig") as f:
            baca = csv.DictReader(f)
            kol = next((h for h in (baca.fieldnames or []) if kunci(h) in KAND["id"]), None)
            if kol is None:
                print("Kolom id tidak ditemukan di %s" % hanya); return
            for b in baca:
                v = bersih(b.get(kol))
                if v:
                    pilih.add(v)
        sebelum = len(emas_peta)
        emas_peta = {k: v for k, v in emas_peta.items() if k in pilih}
        print("Dibatasi pada %d id dari %s (gold standard: %d -> %d)"
              % (len(pilih), os.path.basename(hanya), sebelum, len(emas_peta)))
        print()

    hasil = []
    for p in model:
        try:
            if p.lower().endswith((".xlsx", ".xlsm")):
                duga, galat, cacat = baca_xlsx(p), 0, []
            else:
                duga, galat, cacat = baca_csv(p)
        except RuntimeError as e:
            print("!! %s: %s" % (os.path.basename(p), e)); continue
        h = nilai(os.path.basename(p), emas_peta, duga, ulang, galat, cacat)
        if h:
            hasil.append(h)

    if len(hasil) >= 2:
        garis("KESEPAKATAN ANTARMODEL  (tidak bergantung gold standard manusia)")
        bersama = set(hasil[0]["ids"])
        for h in hasil[1:]:
            bersama &= set(h["ids"])
        bersama = sorted(bersama)
        if bersama:
            kol = [[h["duga"][i] for h in hasil] for i in bersama]
            a = krippendorff_alpha(kol)
            if a is not None:
                print("  alpha Krippendorff antar %d model : %.4f   (n=%d unit)"
                      % (len(hasil), a, len(bersama)))
                print()
        for a, b in itertools.combinations(hasil, 2):
            ids = sorted(set(a["ids"]) & set(b["ids"]))
            x = [a["duga"][i] for i in ids]
            y = [b["duga"][i] for i in ids]
            po, kap = cohen_kappa(x, y)
            print("  %-28s vs %-28s n=%d  Po=%.4f  kappa=%.4f"
                  % (a["nama"][:28], b["nama"][:28], len(ids), po, kap))

    if keluar and hasil:
        ids = sorted(set(emas_peta), key=lambda x: (len(x), x))
        with open(keluar, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "emas"] + [h["nama"] for h in hasil])
            for i in ids:
                w.writerow([i, emas_peta.get(i, "")] +
                           [h["duga"].get(i, "") for h in hasil])
        print()
        print("  Label per unit ditulis ke: %s" % keluar)
    print()


if __name__ == "__main__":
    utama()
