import csv
import json
import statistics
import sys

from alat_analisis import Catat

BERKAS = [
    ("GPT-6 Astra*", "hasil_model_gpt.jsonl"),
    ("Gemini 3.8 Flash*", "Hasil_Model_501_20260928_gemini.jsonl"),
    ("DeepSeek V4 (T)*", "Hasil_Model_501_20261003_deepseek_think.jsonl"),
    ("DeepSeek V4", "Hasil_Model_501_20261002_deepseek.jsonl"),
    ("Command A", "Hasil_Model_501_20260928_cohere.jsonl"),
]

HARGA = {
    "GPT-6 Astra*": (None, None),
    "Gemini 3.8 Flash*": (None, None),
    "DeepSeek V4 (T)*": (None, None),
    "DeepSeek V4": (None, None),
    "Command A": (None, None),
}
TANGGAL_CEK_HARGA = ""
HARGA_TAGIHAN = {k: None for k in HARGA}


def angka(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def main():
    if len(sys.argv) != 2:
        print("Argumen tidak lengkap.")
        return
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        sampel = [b["id"].strip() for b in csv.DictReader(f)]
    log = Catat("hasil_token_biaya.txt")
    hasil = []
    for nama, fn in BERKAS:
        rek = []
        with open(fn, encoding="utf-8") as f:
            for g in f:
                g = g.strip()
                if not g:
                    continue
                try:
                    rek.append(json.loads(g))
                except json.JSONDecodeError:
                    pass
        ok = [d for d in rek if not d.get("galat") and angka(d.get("tok_out")) is not None]
        akhir = {}
        for d in ok:
            akhir[str(d.get("id"))] = d
        sah = [akhir[u] for u in sampel if u in akhir]
        ti = [angka(d.get("tok_in")) or 0 for d in sah]
        to = [angka(d.get("tok_out")) or 0 for d in sah]
        ti_all = sum(angka(d.get("tok_in")) or 0 for d in ok)
        to_all = sum(angka(d.get("tok_out")) or 0 for d in ok)
        log("\n" + nama + "  (" + fn + ")")
        log("   baris log %d | berhasil %d | tanpa token/galat %d | unit sah %d/%d"
            % (len(rek), len(ok), len(rek) - len(ok), len(sah), len(sampel)))
        log("   501 jawaban sah : token masuk %s | keluar %s | median keluar %s | maks keluar %s"
            % (f"{sum(ti):,}", f"{sum(to):,}", statistics.median(to) if to else "-", max(to) if to else "-"))
        log("   semua berhasil  : token masuk %s | keluar %s" % (f"{ti_all:,}", f"{to_all:,}"))
        pin, pout = HARGA[nama]
        biaya = biaya_all = None
        if pin is not None and pout is not None:
            biaya = sum(ti) / 1e6 * pin + sum(to) / 1e6 * pout
            biaya_all = ti_all / 1e6 * pin + to_all / 1e6 * pout
            log("   perkiraan biaya (harga %s): US$%.2f (501 sah) | US$%.2f (semua panggilan)"
                % (TANGGAL_CEK_HARGA or "tanggal belum diisi", biaya, biaya_all))
        else:
            log("   harga belum diisi -> biaya tidak dihitung")
        if HARGA_TAGIHAN.get(nama) is not None:
            log("   TAGIHAN dashboard: US$%.2f" % HARGA_TAGIHAN[nama])
        hasil.append([nama, fn, len(rek), len(ok), len(sah), sum(ti), sum(to),
                      statistics.median(to) if to else "", max(to) if to else "",
                      ti_all, to_all, "" if biaya is None else round(biaya, 2),
                      "" if biaya_all is None else round(biaya_all, 2), HARGA_TAGIHAN.get(nama) or ""])

    with open("hasil_token_biaya.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run", "berkas", "baris_log", "berhasil", "unit_sah", "tok_in_sah", "tok_out_sah",
                    "median_out", "maks_out", "tok_in_semua", "tok_out_semua", "biaya_sah_usd",
                    "biaya_semua_usd", "tagihan_usd"])
        w.writerows(hasil)
    log("\nDitulis juga: hasil_token_biaya.csv")
    log.tutup()


if __name__ == "__main__":
    main()
