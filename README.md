# Program Bel Pembelajaran berbasis Python

## Cara Install
```bash
uv sync
```

## Cara Pakai

### Cek konfigurasi
Cek validitas konfigurasi dengan perintah
```bash
uv run python bel_pelajaran/cek_konfig.py [file konfig].toml
```

### Cek sound
Test sound dengan perintah
```bash
uv run python bel_pelajaran/cek_sound.py
```

### Jalankan bel
Jalankan bel dengan perintah
```bash
uv run python bel_pelajaran/main.py [file konfig].toml
```

Contoh:
```bash
uv run python bel_pelajaran/main.py konfig.toml
```

Kredit:
libs
- playsound3
- schedule
- toml

assets
- sumber download: http://knaencreative.blogspot.com/2017/08/download-sound-nada-bel-sekolah.html 