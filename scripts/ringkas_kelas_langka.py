import csv
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore")
sys.argv, _argv = sys.argv[:1], sys.argv
import hitung_keandalan as hk
sys.argv = _argv

from alat_analisis import Catat


def n(t):
    t = (t or "").strip().lower()
    return "rusak" if t.startswith("rusak") else t


def main():
    if len(sys.argv) != 5:
        print("Argumen tidak lengkap.")
        return
    lab = [hk.baca_lembar(p)[0] for p in sys.argv[1:4]]
    nama = ["coder1", "coder2", "coder3"]
    with open(sys.argv[4], newline="", encoding="utf-8") as f:
        kunci = list(csv.DictReader(f))
    log = Catat("hasil_kelas_langka.txt")
    for peran, kelas in (("target_A1", "a1"), ("target_GB", "rusak")):
        uu = [k for k in kunci if k["peran"] == peran]
        log("\n%s (%d unit)" % (peran, len(uu)))
        semua = 0
        jml = Counter()
        for k in uu:
            u = k["id"]
            ls = [n(L.get(u) or L.get(int(u)) if isinstance(L, dict) else "") for L in lab]
            cocok = sum(1 for x in ls if x == kelas)
            jml[cocok] += 1
            semua += cocok == 3
            log("   id %-5s  %s" % (u, " | ".join("%s=%s" % (a, b or "-") for a, b in zip(nama, ls))))
        log("   ketiga pengode memberi %s: %d dari %d unit | sebaran jumlah pengode yang setuju: %s"
            % (kelas.upper(), semua, len(uu), dict(sorted(jml.items()))))
    ids = [k["id"] for k in kunci]
    def ambil(L, u):
        return n(L.get(u) or L.get(int(u)) or "")
    unit_labels = {u: [ambil(L, u) for L in lab] for u in ids if all(ambil(L, u) for L in lab)}
    a = hk.krippendorff_alpha(list(unit_labels.values()))
    lo, hi, q = hk.bootstrap_alpha(unit_labels, ulang=5000)
    log("\nAlpha Krippendorff 3 pengode, %d unit: %.3f  SK 95%% [%.3f, %.3f]"
        % (len(unit_labels), a, lo, hi))
    for (i, x), (j, y) in [((0, "coder1"), (1, "coder2")), ((0, "coder1"), (2, "coder3")), ((1, "coder2"), (2, "coder3"))]:
        from alat_analisis import kappa
        log("   kappa %s-%s: %.3f" % (x, y, kappa([v[i] for v in unit_labels.values()], [v[j] for v in unit_labels.values()])))
    log.tutup()


if __name__ == "__main__":
    main()
