# Bel Pembelajaran

Bel sekolah otomatis berbasis Python. Menggantikan bel manual/rusak dengan
jadwal harian (senin–sabtu) yang membunyikan file suara pada jam tertentu.

Dibangun ulang agar **andal berjalan sendiri seharian penuh** dan siap
dikembangkan menjadi aplikasi GUI lintas-platform (Windows + Linux).

---

## Status

Fase **0 (pengerasan mesin)** dan **1 (pemisahan layer)** selesai. Implementasi **Fase 2 / Step 0–6 dan otomasi packaging Step 8** sudah tersedia: backend Qt Multimedia, event loop CLI, editor jadwal, status live, pratinjau suara, kontrol volume, serta builder EXE/DEB/AppImage. Validasi artefak pada mesin bersih tetap wajib dilakukan sebelum rilis. Mesin sudah:

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
├── scripts/             # builder EXE, DEB, dan AppImage
├── packaging/linux/     # desktop entry + AppStream metainfo untuk paket Linux
├── run.py               # launcher tipis CLI lama
├── run_gui.py           # entrypoint GUI untuk PyInstaller
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
uv run bel start configs/konfig.toml --force     # tetap jalan meski ada error validasi
uv run bel start configs/konfig.toml -v          # logging DEBUG

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

## Membuat paket rilis

Build diotomatisasi oleh `scripts/build_packages.py`. PyInstaller **bukan**
cross-compiler: EXE harus dibuat pada Windows native, sedangkan `.deb` dan
AppImage harus dibuat pada Linux. Semua perintah dijalankan dari root proyek.

### Windows — EXE (folder/onedir)

Build harus dijalankan di Windows native (cmd/PowerShell, **bukan WSL**).
PyInstaller tidak bisa cross-compile dari Linux.

**1. Persiapan sekali saja**

- Install [Git for Windows](https://git-scm.com/download/win).
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) — di
  PowerShell:

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

  Tidak perlu memasang Python manual: uv membaca `.python-version` dan
  mengunduh Python 3.12 otomatis saat `uv sync`.
- Setelah instalasi, buka jendela PowerShell **baru** agar `uv` masuk ke `PATH`.

**2. Clone dan build**

```powershell
git clone https://github.com/s4if/bel-pelajaran-py.git
cd bel-pelajaran-py
uv sync --all-extras --group dev          # venv + seluruh dependensi + PyInstaller
uv run python scripts/build_packages.py windows
```

Build memakan beberapa menit saat pertama kali (PyInstaller mem-payload Qt).
Semua yang dibutuhkan bundle — `assets/` (termasuk `.ico`), `configs/`, dan
`run_gui.py` — sudah ada di repo, jadi clone bersih cukup untuk build.

**3. Hasil dan uji cepat**

Hasil: `dist\windows\bel-pelajaran\bel-pelajaran.exe`. Seluruh folder
`bel-pelajaran\` adalah satu aplikasi dan harus didistribusikan bersama; EXE
bergantung pada file internal di sebelahnya. Python dan Qt tidak perlu dipasang
di komputer tujuan.

Sebelum disebarkan, jalankan sekali di mesin build: aplikasi terbuka, self-test
audio sukses, Mulai/Berhenti dan tray bekerja. Catatan: EXE belum ditandatangani
code-signing, jadi Windows SmartScreen dapat menampilkan peringatan saat
pertama dijalankan — pilih **Run anyway**.

Untuk build ulang setelah `git pull`, cukup ulangi dua perintah terakhir
(`uv sync --all-extras --group dev` memastikan dependensi baru ikut terpasang).

### Linux — Debian `.deb`

Prerequisite build pada Debian/Ubuntu:

```bash
sudo apt install dpkg-dev
uv sync --all-extras --group dev
uv run python scripts/build_packages.py deb
```

Hasil: `dist/linux/bel-pelajaran_<versi>_<arsitektur>.deb`.

### Linux — AppImage

Unduh `appimagetool` resmi dari rilis AppImageKit, jadikan executable, lalu:

```bash
chmod +x ~/Downloads/appimagetool-x86_64.AppImage
uv sync --all-extras --group dev
uv run python scripts/build_packages.py appimage \
  --appimagetool ~/Downloads/appimagetool-x86_64.AppImage
```

Hasil: `dist/linux/Bel-Pembelajaran-<versi>-<arsitektur>.AppImage`.
Untuk membuat kedua format Linux dari satu build PyInstaller:

```bash
uv run python scripts/build_packages.py linux --appimagetool /path/appimagetool
```

Paket Linux menaruh program di `/usr/lib/bel-pelajaran`, resource factory
di `/usr/share/bel-pelajaran`, serta desktop entry, ikon SVG hicolor, dan
AppStream metainfo (di `/usr/share/applications`, `/usr/share/icons/hicolor`,
`/usr/share/metainfo`) agar aplikasi muncul di menu dan software center.
AppImage menggunakan susunan yang sama di dalam image. Launcher mengatur
`BEL_PELAJARAN_RESOURCE_DIR`; Windows menyimpan resource
di bundle PyInstaller.

Saat GUI pertama kali dibuka, `configs/konfig.toml` bawaan disalin menjadi
jadwal pengguna (`~/.config/bel-pelajaran/schedules/konfig.toml` atau
`%APPDATA%\\bel-pelajaran\\schedules\\konfig.toml`). File yang sudah ada tidak
pernah ditimpa. Resource instalasi dianggap read-only dan tombol **Simpan** akan
mengarahkan jadwal factory ke **Simpan Sebagai…**.

> Bangun AppImage pada distribusi Linux tertua yang akan didukung karena glibc
> dari host build menentukan kompatibilitas. Qt Multimedia/plugin FFmpeg tetap
> wajib diuji pada image sekolah yang sebenarnya.

### Validasi clean-machine wajib

Untuk setiap artefak, gunakan VM/PC tanpa Python dan Qt terpasang, lalu periksa:

1. aplikasi terbuka dari menu/double-click;
2. jadwal default tersalin pada first run;
3. edit + Simpan bertahan setelah restart dan tidak mengubah direktori instalasi;
4. self-test audio tidak menampilkan error dan MP3 terdengar;
5. Mulai/Berhenti serta system tray bekerja;
6. `.deb` dapat dihapus dengan package manager dan AppImage tetap portabel.

---

## Roadmap

- [x] **Fase 0** — pengerasan: audio non-blocking, error handling, logging, path portabel, validasi menyeluruh, tes.
- [x] **Fase 1** — pemisahan layer (config / engine / audio) agar bisa dipakai GUI.
- [ ] **Fase 2** — GUI lintas-platform (PySide6). Step 0–6 selesai; otomasi Step 8 menghasilkan EXE Windows, `.deb`, dan AppImage Linux serta menyalin jadwal factory pada first run. Yang tersisa sebelum menandai fase selesai adalah validasi clean-machine Windows/Linux; multi-config tetap stretch goal.
- [ ] Pertimbangkan ganti `schedule` → APScheduler (recover job terlewat, lebih tangguh terhadap perubahan jam).
- [ ] Mode ujian sebagai toggle runtime (bukan ganti file konfigurasi).
- [ ] Jadwalkan sebagai service/autostart (bertahan restart & tidur mesin).

---

## Kredit

- Pustaka: [Qt Multimedia](https://doc.qt.io/qtforpython-6/overviews/qtmultimedia-audiooverview.html) (audio), [schedule](https://github.com/dbader/schedule)
- Suara asal: <http://knaencreative.blogspot.com/2017/08/download-sound-nada-bel-sekolah.html>
