# Bel Pembelajaran

Bel sekolah otomatis berbasis Python. Menggantikan bel manual/rusak dengan
jadwal harian (senin–sabtu) yang membunyikan file suara pada jam tertentu.

Dibangun ulang agar **andal berjalan sendiri seharian penuh** dan siap
dikembangkan menjadi aplikasi GUI lintas-platform (Windows + Linux).

---

## Status

Fase **0 (pengerasan mesin)** dan **1 (pemisahan layer)** selesai. Mesin sudah:

- memutar suara secara **non-blocking** (suara panjang tidak akan menunda/men-skip bel berikutnya),
- **tahan error** — satu file rusak/hilang tidak akan menghentikan jadwal seharian,
- mencatat **log** ke konsol + file (`~/.bel-pelajaran/logs/bel.log`),
- memvalidasi konfigurasi dan melaporkan **semua** error sekaligus,
- resolusi path yang sama untuk mode `uv run` maupun **exe hasil PyInstaller**.

> Lihat bagian **Roadmap** untuk GUI dan pengembangan selanjutnya.

---

## Struktur Proyek

```
bel-pelajaran-py/
├── app/                 # kode aplikasi (package)
│   ├── paths.py         # resolusi path (kerja di dev + exe)  ← groundwork PyInstaller
│   ├── models.py        # Bell, Timetable (dataclass)
│   ├── config.py        # baca + validasi TOML (pakai tomllib bawaan Python)
│   ├── audio.py         # AudioBackend + PygameBackend (non-blocking, mp3 tanpa ffmpeg)
│   ├── scheduler.py     # mesin: arm + run, anti-crash, bisa jalan di thread (untuk GUI)
│   ├── logging_setup.py # log konsol + file rotasi
│   ├── cli.py           # perintah `bel`
│   └── __main__.py      # `python -m app`
├── configs/             # file jadwal .toml
├── assets/              # file suara .mp3
├── tests/               # pytest
├── run.py               # launcher tipis (juga entrypoint PyInstaller)
├── pyproject.toml       # konfigurasi proyek (uv) — sumber kebenaran
├── uv.lock              # lockfile uv
└── requirements.txt     # runtime-only (di-generate dari pyproject)
```

### Layer (Fase 1)

```
 config source ─→ scheduler engine ─→ audio backend
 (TOML/file)      (BellScheduler)     (PygameBackend)
                         ↑                    ↑
                    GUI nanti bisa       bisa diganti NullBackend
                    pakai thread          (test / --dry-run)
```

---

## Instalasi (pakai uv)

Butuh Python **3.11–3.13** (3.12 direkomendasikan; uv akan ambil otomatis).

```bash
uv sync                 # buat venv + install semua dependensi
```

Tanpa uv:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"   # atau: pip install -r requirements.txt
```

## Pakai

```bash
uv run bel --help
uv run bel check configs/konfig.toml        # validasi + tampilkan rundown
uv run bel sounds                           # daftar suara di assets/
uv run bel test-sound 1.mp3                 # putar satu suara (cek audio)

uv run bel start configs/konfig.toml        # jalankan bel (Ctrl+C untuk berhenti)
uv run bel start configs/konfig.toml --dry-run   # simulasi: jadwal jalan tanpa suara
uv run bel start configs/konfig.toml --volume 0.8
```

Atau tanpa install: `uv run python -m app start configs/konfig.toml`.

### Format konfigurasi

```toml
[[senin]]
jam  = "07:00"                         # HH:MM (24 jam)
file = "upacara_kurang_5_menit.mp3"    # nama file di assets/

[[selasa]]
jam  = "07:00"
file = "1.mp3"
# rabu/kamis/sabtu tidak ditulis -> otomatis ikut "selasa"
```

Lihat `configs/example.toml` dan `configs/konfig.toml`.

---

## Membangun jadi EXE (PyInstaller)

Groundwork-nya sudah ada: `app/paths.py` mendeteksi `sys._MEIPASS` saat dibekukan,
jadi folder `assets/` & `configs/` otomatis ditemukan baik dari source maupun dari exe.

```bash
uv run pyinstaller \
  --name bel \
  --noconfirm \
  --add-data "assets:assets" \
  --add-data "configs:configs" \
  --hidden-import pygame \
  run.py
```

- `--add-data "src:dest"` — `src` di mesin ini, `dest` di dalam bundle.
  Pemisah `:` di Linux/macOS, gunakan `;` di Windows (`"assets;assets"`).
- Hasil: `dist/bel/` (folder, direkomendasikan) atau tambahkan `--onefile` untuk satu file.

> Di Windows, jalankan dari **cmd/PowerShell** (bukan WSL) supaya exe-nya native Windows.

---

## Roadmap

- [x] **Fase 0** — pengerasan: audio non-blocking, error handling, logging, path portabel, validasi menyeluruh, tes.
- [x] **Fase 1** — pemisahan layer (config / engine / audio) agar bisa dipakai GUI.
- [ ] **Fase 2** — GUI lintas-platform (kandidat: PySide6 atau Flet). Mesin sudah punya `start_in_thread()` untuk dipanggil dari event loop GUI.
- [ ] Pertimbangkan ganti `schedule` → APScheduler (recover job terlewat, lebih tangguh terhadap perubahan jam).
- [ ] Mode ujian sebagai toggle runtime (bukan ganti file konfigurasi).
- [ ] Jadwalkan sebagai service/autostart (bertahan restart & tidur mesin).

---

## Kredit

- Pustaka: [pygame](https://www.pygame.org/) (audio), [schedule](https://github.com/dbader/schedule)
- Suara asal: <http://knaencreative.blogspot.com/2017/08/download-sound-nada-bel-sekolah.html>
