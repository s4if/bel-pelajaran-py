# Bel Pembelajaran

Bel sekolah otomatis berbasis Python. Menggantikan bel manual/rusak dengan
jadwal harian (senin–sabtu) yang membunyikan file suara pada jam tertentu.

Dibangun ulang agar **andal berjalan sendiri seharian penuh** dan siap
dikembangkan menjadi aplikasi GUI lintas-platform (Windows + Linux).

---

## Status

Fase **0 (pengerasan mesin)** dan **1 (pemisahan layer)** selesai. Implementasi **Fase 2 / Step 0–6** sudah selesai: backend Qt Multimedia, event loop CLI, editor jadwal, status live, pratinjau suara, dan kontrol volume sudah tersedia. Mesin sudah:

- memutar suara secara **non-blocking** (suara panjang tidak akan menunda/men-skip bel berikutnya),
- **tahan error** — satu file rusak/hilang tidak akan menghentikan jadwal seharian,
- mencatat **log** ke konsol + file pada folder state standar platform
  (Linux: `$XDG_STATE_HOME/bel-pelajaran/logs/`, Windows: `%LOCALAPPDATA%\\bel-pelajaran\\logs\\`),
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
│   ├── audio.py         # AudioBackend + QtMultimediaBackend (async Qt audio)
│   ├── scheduler.py     # mesin: arm + tick/run, anti-crash
│   ├── gui/             # aplikasi Qt, controller QTimer, dan tabel jadwal
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
 (TOML/file)      (BellScheduler)     (QtMultimediaBackend)
                         ↑                    ↑
                    GUI memakai          bisa diganti NullBackend
                    QTimer main-thread    (test / --dry-run)
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
pip install -e ".[qt]"   # audio Qt Multimedia
pip install pytest pyinstaller   # hanya jika perlu testing/packaging
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

# GUI: kelola jadwal, Mulai/Berhenti, pratinjau suara, volume, dan system tray
uv run bel-gui
# atau: uv run python -m app.gui
```

Menekan tombol **minimize** atau **close (×)** menyembunyikan aplikasi ke system
tray; scheduler tetap berjalan. Untuk benar-benar berhenti, pilih **Aplikasi →
Keluar Sepenuhnya** atau menu **Keluar Sepenuhnya** pada ikon tray. Aplikasi akan
meminta konfirmasi sebelum menghentikan bell dan menawarkan Simpan/Buang/Batal
jika jadwal masih memiliki perubahan yang belum disimpan. Banner error dapat
ditutup kapan saja lewat tombol **×** di sisi kanan pemberitahuan.

Jadwal baru dari **Simpan Sebagai…** disimpan di folder konfigurasi standar
platform: `$XDG_CONFIG_HOME/bel-pelajaran/schedules/` di Linux (default
`~/.config`) atau `%APPDATA%\\bel-pelajaran\\schedules\\` di Windows. Folder
MP3 dapat diganti melalui **Aplikasi → Folder Suara…**. Path absolutnya
disimpan di file TOML jadwal dan dipakai oleh dropdown suara, pratinjau, startup
self-test, dan scheduler. Gunakan **Folder Bawaan** untuk menyimpan nilai kosong
dan kembali ke `assets/`. Jadwal tetap dapat dibuka jika folder/file hilang agar
nama suara tidak terhapus; pemeriksaan file dilakukan sebelum Start dan sebelum
mengedit baris terkait.

Atau tanpa install: `uv run python -m app start configs/konfig.toml`.

### Format konfigurasi

```toml
# Wajib path absolut jika diisi. Kosong memakai assets/ bawaan.
sound_dir = ""
# sound_dir = "D:/Bel Sekolah/suara"       # contoh Windows
# sound_dir = "/opt/bel-sekolah/suara"    # contoh Linux

[[senin]]
jam  = "07:00"                         # HH:MM (24 jam)
file = "upacara_kurang_5_menit.mp3"    # nama file di sound_dir

[[selasa]]
jam  = "07:00"
file = "1.mp3"
# Hari yang tidak ditulis tidak memiliki bell.
```

Nilai `file` tetap berupa nama file saja. `sound_dir` harus kosong atau berupa
path absolut; path relatif dan folder yang hilang dilaporkan sebagai banner
error tanpa membuang nilai `file`.

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
  --hidden-import PySide6.QtMultimedia \
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
- [ ] **Fase 2** — GUI lintas-platform (PySide6). Step 0–6 selesai: editor lengkap, Start/Stop, status live, countdown, pratinjau suara, volume, startup audio self-test, folder suara yang dapat dikonfigurasi, SVG app/tray icon, minimize-to-tray, serta guard perubahan/stop. Berikutnya: packaging; multi-config tetap stretch goal.
- [ ] Pertimbangkan ganti `schedule` → APScheduler (recover job terlewat, lebih tangguh terhadap perubahan jam).
- [ ] Mode ujian sebagai toggle runtime (bukan ganti file konfigurasi).
- [ ] Jadwalkan sebagai service/autostart (bertahan restart & tidur mesin).

---

## Kredit

- Pustaka: [Qt Multimedia](https://doc.qt.io/qtforpython-6/overviews/qtmultimedia-audiooverview.html) (audio), [schedule](https://github.com/dbader/schedule)
- Suara asal: <http://knaencreative.blogspot.com/2017/08/download-sound-nada-bel-sekolah.html>
