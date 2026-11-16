import csv, json, os, random, re, sys, time, collections

try:
    import requests
except ImportError:
    print("requests belum terpasang.  python -m pip install requests")
    sys.exit(1)

KELAS = {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "B5"}
CATATAN = {"", "rusak", "rusak, pulih-manual", "bukan alam",
           "bukan alam, iklim", "ragu - anteseden hilang"}

MODEL = [
    {"label": "deepseek_think", "gaya": "openai",
     "url": "https://api.deepseek.com/chat/completions",
     "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
     "kunci": "DEEPSEEK_API_KEY",
     "tambahan": {"thinking": {"type": "enabled"}}},
]


VARIAN = {"deepseek_think": {"token": "max_tokens", "tanpa_suhu": True}}
TERAKHIR = {}
TERCACHE = {}


def _badan(cfg, sistem, pengguna, batas, v):
    if cfg["gaya"] == "anthropic":
        b = {"model": cfg["model"], "max_tokens": batas,
             "system": sistem,
             "messages": [{"role": "user", "content": pengguna}]}
        if not v.get("tanpa_suhu"):
            b["temperature"] = 0
        if cfg.get("tambahan"):
            b.update(cfg["tambahan"])
        return b

    b = {"model": cfg["model"],
         "messages": [{"role": "system", "content": sistem},
                      {"role": "user", "content": pengguna}]}
    b[v.get("token", "max_completion_tokens")] = batas
    if not v.get("tanpa_suhu"):
        b["temperature"] = 0
    if cfg.get("tambahan"):
        b.update(cfg["tambahan"])
    return b


def panggil(cfg, sistem, pengguna, batas=4000):
    kunci = os.environ.get(cfg["kunci"])
    if not kunci:
        raise RuntimeError("%s belum ada di environment." % cfg["kunci"])

    label = cfg["label"]

    jeda = cfg.get("jeda", 0)
    if jeda:
        lalu = TERAKHIR.get(label)
        if lalu is not None:
            sisa = jeda - (time.time() - lalu)
            if sisa > 0:
                time.sleep(sisa)
        TERAKHIR[label] = time.time()
    v = VARIAN.setdefault(label, {})

    if cfg["gaya"] == "anthropic":
        h = {"x-api-key": kunci, "anthropic-version": "2023-06-01",
             "content-type": "application/json"}
    else:
        h = {"Authorization": "Bearer " + kunci,
             "content-type": "application/json"}

    for _ in range(4):
        r = requests.post(cfg["url"], headers=h,
                          json=_badan(cfg, sistem, pengguna, batas, v),
                          timeout=180)
        if r.status_code < 400:
            break

        pesan, kode = r.text[:400], ""
        try:
            e = r.json().get("error", {})
            pesan = e.get("message") or pesan
            kode = e.get("code") or e.get("type") or ""
        except Exception:
            pass
        t = pesan.lower()

        if r.status_code == 400 and "max_completion_tokens" in t and \
                "not supported" in t and v.get("token") != "max_tokens":
            v["token"] = "max_tokens"
            print("   [%s] beralih ke max_tokens" % label)
            continue
        if r.status_code == 400 and "max_tokens" in t and \
                "max_completion_tokens" in t and v.get("token") != "max_completion_tokens":
            v["token"] = "max_completion_tokens"
            print("   [%s] beralih ke max_completion_tokens" % label)
            continue
        if r.status_code == 400 and "temperature" in t and not v.get("tanpa_suhu"):
            v["tanpa_suhu"] = True
            print("   [%s] model menolak temperature; dijalankan pada nilai "
                  "bawaan." % label)
            continue

        raise RuntimeError("HTTP %d  %s  %s" % (r.status_code, kode, pesan))
    else:
        raise RuntimeError("Perundingan parameter gagal empat kali untuk %s."
                           % label)

    d = r.json()
    if cfg["gaya"] == "anthropic":
        teks = "".join(p.get("text", "") for p in d.get("content", []))
        pakai = d.get("usage", {})
        masuk = pakai.get("input_tokens")
        keluar = pakai.get("output_tokens")
        alasan = d.get("stop_reason")
    else:
        pil = d["choices"][0]
        teks = pil["message"].get("content") or ""
        pakai = d.get("usage", {})
        masuk = pakai.get("prompt_tokens")
        keluar = pakai.get("completion_tokens")
        alasan = pil.get("finish_reason")
        rinci = (pakai.get("prompt_tokens_details")
                 or pakai.get("input_tokens_details") or {})
        if not rinci and pakai.get("prompt_cache_hit_tokens") is not None:
            rinci = {"cached_tokens": pakai.get("prompt_cache_hit_tokens")}
        TERCACHE[cfg["label"]] = TERCACHE.get(cfg["label"], 0) + \
            (rinci.get("cached_tokens") or 0)

    if alasan in ("length", "max_tokens") or not teks.strip():
        raise RuntimeError(
            "Jawaban kosong atau terpotong (finish_reason=%s, token keluar=%s)."
            % (alasan, keluar))

    return teks, masuk, keluar


def pilih_baris(baris, n):
    sel = collections.defaultdict(list)
    for b in baris:
        sel[b.get("jenis", "prosa")].append(b)
    urut = [j for j in ("prosa", "tabel", "gambar") if sel[j]]
    if not urut:
        return baris[:n]

    jatah = {j: min(len(sel[j]), max(3, round(n * len(sel[j]) / len(baris))))
             for j in urut}
    while sum(jatah.values()) > n:
        j = max(urut, key=lambda k: jatah[k])
        if jatah[j] <= 1:
            break
        jatah[j] -= 1
    while sum(jatah.values()) < n:
        j = min(urut, key=lambda k: jatah[k] / max(1, len(sel[k])))
        if jatah[j] >= len(sel[j]):
            break
        jatah[j] += 1

    acak = random.Random(20260922)
    out = []
    for j in urut:
        isi = sel[j][:]
        acak.shuffle(isi)
        out += isi[:jatah[j]]
    acak.shuffle(out)
    return out


def panggil_ulang(cfg, sistem, pengguna, batas=4000, coba=4):
    tunggu = 5
    for i in range(coba):
        try:
            return panggil(cfg, sistem, pengguna, batas)
        except RuntimeError as e:
            t = str(e).lower()
            if ("insufficient_quota" in t or "billing" in t
                    or "exceeded your current quota" in t):
                raise
            if ("http 429" in t or "http 5" in t) and i < coba - 1:
                time.sleep(tunggu); tunggu *= 2; continue
            raise


def urai(teks):
    if teks is None:
        return None
    t = teks.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def periksa(kirim_id, jawab):
    salah = []
    if jawab is None:
        return ["tidak dapat diurai sebagai JSON"]
    if str(jawab.get("id")) != str(kirim_id):
        salah.append("id berbeda: dikirim %s, kembali %s"
                     % (kirim_id, jawab.get("id")))
    kode = (jawab.get("code") or "").strip()
    cat = (jawab.get("note") or "").strip()
    bukti = (jawab.get("evidence") or "").strip()
    if kode and kode not in KELAS:
        salah.append("kode di luar daftar: %r" % kode)
    if cat and cat not in CATATAN:
        salah.append("catatan di luar daftar: %r" % cat)
    if not kode and not cat:
        salah.append("kode dan catatan dua-duanya kosong")
    if cat in ("rusak", "bukan alam", "bukan alam, iklim") and (kode or bukti):
        salah.append("gerbang %r tetapi kode atau bukti terisi" % cat)
    if kode and not cat and not bukti:
        salah.append("kode terisi tetapi kalimat bukti kosong")
    if bukti.count(".") > 3:
        salah.append("kalimat bukti tampak lebih dari satu kalimat")
    return salah


def utama(csv_sampel, berkas_prompt, n=20, batas=4000):
    if not MODEL:
        print("Daftar MODEL kosong.")
        sys.exit(1)

    sistem = open(berkas_prompt, encoding="utf-8").read()
    with open(csv_sampel, newline="", encoding="utf-8") as f:
        baris = list(csv.DictReader(f))

    pilih = pilih_baris(baris, n)
    jns = collections.Counter(b.get("jenis", "prosa") for b in pilih)
    print("uji asap pada %d baris — %s\n"
          % (len(pilih), "  ".join("%s %d" % kv for kv in sorted(jns.items()))))

    lapor = {}
    for cfg in MODEL:
        label = cfg["label"]
        print("=" * 60)
        print("%s  (%s)" % (label, cfg["model"]))
        print("=" * 60)
        hasil = [{}, {}]
        gagal, detik, tok_in, tok_out = [], 0.0, 0, 0

        for putaran in (0, 1):
            for b in pilih:
                teks = "id: %s\nblock_type: %s\n\npassage:\n%s" % (
                    b["id"], b.get("jenis", "prose"),
                    b.get("teks") or b.get("teks_paragraf", ""))
                t0 = time.time()
                try:
                    keluar, mi, mo = panggil_ulang(cfg, sistem, teks, batas)
                except Exception as e:
                    gagal.append("id %s putaran %d: %s" % (b["id"], putaran + 1, e))
                    hasil[putaran][b["id"]] = None
                    continue
                detik += time.time() - t0
                tok_in += mi or 0
                tok_out += mo or 0
                j = urai(keluar)
                hasil[putaran][b["id"]] = j
                if putaran == 0:
                    for s in periksa(b["id"], j):
                        gagal.append("id %s: %s" % (b["id"], s))

        n_kirim = 2 * len(pilih)
        n_jawab = sum(1 for p_ in hasil for i in p_ if p_[i] is not None)
        n_sah = sum(1 for i in hasil[0]
                    if hasil[0][i] is not None and not periksa(i, hasil[0][i]))
        ada_jawaban = n_jawab > 0

        beda = [i for i in hasil[0]
                if hasil[0].get(i) is not None and hasil[1].get(i) is not None
                and hasil[0][i].get("code") != hasil[1][i].get("code")]

        per = 0.0

        def ya(kondisi):
            return "ya" if kondisi else "TIDAK"

        print("  0. panggilan berhasil   : %d dari %d" % (n_jawab, n_kirim))
        if not ada_jawaban:
            print("     TIDAK SATU PUN PANGGILAN BERHASIL.")
        else:
            print("  1. terurai dan sah      : %d dari %d" % (n_sah, len(pilih)))
            print("  2. id cocok             : %s"
                  % ya(not any("id berbeda" in g for g in gagal)))
            print("  3. tanpa kegagalan urai : %s"
                  % ya(not any("diurai" in g for g in gagal)))
            print("  4. dua putaran sama     : %s"
                  % ("ya" if not beda else "TIDAK \u2014 %d baris berubah: %s"
                     % (len(beda), ", ".join(map(str, beda[:8])))))
            per = detik / max(1, n_jawab)
            print("  5. %.2f detik per baris \u2014 501 baris \u2248 %.0f menit per model"
                  % (per, per * 501 / 60))
            print("     token masuk %s, keluar %s untuk %d panggilan berhasil"
                  % (format(tok_in, ","), format(tok_out, ","), n_jawab))
            print("     501 baris \u2248 %s token masuk, %s token keluar"
                  % (format(round(tok_in / n_jawab * 501), ","),
                     format(round(tok_out / n_jawab * 501), ",")))
            c = TERCACHE.get(label, 0)
            if tok_in:
                print("  6. tercache            : %s dari %s token masuk (%.0f%%)"
                      % (format(c, ","), format(tok_in, ","), 100.0 * c / tok_in))

        if gagal:
            sebab = collections.Counter()
            for g in gagal:
                sebab[g.split(": ", 1)[-1][:160]] += 1
            print("\n  MASALAH \u2014 %d kejadian, %d sebab berbeda:"
                  % (len(gagal), len(sebab)))
            for teks_sebab, jml in sebab.most_common(8):
                print("    %3dx  %s" % (jml, teks_sebab))
        else:
            print("\n  Tidak ada masalah.")
        print()

        lapor[label] = {"gagal": gagal, "beda": beda,
                        "detik_per_baris": per,
                        "token_in": tok_in, "token_out": tok_out,
                        "jawaban": hasil[0]}

    with open("uji_asap_hasil.json", "w", encoding="utf-8") as f:
        json.dump(lapor, f, ensure_ascii=False, indent=1)
    print("uji_asap_hasil.json ditulis.")


if __name__ == "__main__":
    arg = sys.argv[1:]
    posisi, n, batas, i = [], 20, 4000, 0
    while i < len(arg):
        if arg[i] == "--n" and i + 1 < len(arg):
            n = int(arg[i + 1]); i += 2
        elif arg[i] == "--batas" and i + 1 < len(arg):
            batas = int(arg[i + 1]); i += 2
        else:
            posisi.append(arg[i]); i += 1
    if len(posisi) != 2:
        print("Argumen tidak lengkap."); sys.exit(1)
    utama(posisi[0], posisi[1], n, batas)
