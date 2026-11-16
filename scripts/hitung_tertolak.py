import csv
import re
import sys
from collections import Counter

import openpyxl

from alat_analisis import Catat, wilson

TIDAK_ALAM = {"bukan alam", "bukan alam iklim", "bukan alam, iklim", "rusak"}


def main():
    if len(sys.argv) != 4:
        print("Argumen tidak lengkap.")
        return
    ws = openpyxl.load_workbook(sys.argv[1], data_only=True)["Kode"]
    kode = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        kode[int(r[0])] = (str(r[5]).strip() if r[5] is not None else "")
    with open(sys.argv[2], newline="", encoding="utf-8") as f:
        strata = {int(b["no"]): b["strata"] for b in csv.DictReader(f)}
    teks = open(sys.argv[3], encoding="utf-8").read()
    N = {"one_peripheral_term": int(re.search(r"one_peripheral_term\s+\(1 istilah pinggiran\): (\d+)", teks).group(1)),
         "no_term": int(re.search(r"no_term \(0 istilah pinggiran\): (\d+)", teks).group(1))}
    log = Catat("hasil_tertolak.txt")
    kosong = [no for no, k in kode.items() if not k]
    if kosong:
        log("!! %d unit belum dikode (no: %s)."
            % (len(kosong), kosong[:15]))
    total_alam = total_pilar = 0.0
    for s in ("one_peripheral_term", "no_term"):
        uu = [no for no in kode if strata.get(no) == s and kode[no]]
        n = len(uu)
        if n == 0:
            continue
        alam = [no for no in uu if kode[no].lower() not in TIDAK_ALAM]
        pilar = [no for no in uu if kode[no].upper().startswith("A")]
        pa, pp = len(alam) / n, len(pilar) / n
        la, ha = wilson(len(alam), n)
        lp, hp = wilson(len(pilar), n)
        log("\n%s: ukuran strata %d | dikode %d" % (s, N[s], n))
        log("   sebaran kode: %s" % dict(Counter(kode[no] for no in uu).most_common()))
        log("   berisi alam : %d/%d = %.1f%% [%.1f, %.1f] -> taksiran %.0f unit [%.0f, %.0f]"
            % (len(alam), n, 100 * pa, 100 * la, 100 * ha, pa * N[s], la * N[s], ha * N[s]))
        log("   isi pilar A : %d/%d = %.1f%% [%.1f, %.1f] -> taksiran %.0f unit [%.0f, %.0f]"
            % (len(pilar), n, 100 * pp, 100 * lp, 100 * hp, pp * N[s], lp * N[s], hp * N[s]))
        total_alam += pa * N[s]
        total_pilar += pp * N[s]
    log("\nTaksiran titik total yang terlewat filter: berisi alam %.0f unit, isi pilar %.0f unit" % (total_alam, total_pilar))
    log("Pembanding: 2.084 unit kandidat lolos filter (sekitar 390 di antaranya isi pilar: 18.7% berbobot menurut gold)")
    log.tutup()


if __name__ == "__main__":
    main()
