from datetime import datetime
from pathlib import Path

import toml

ASSETS_DIR = Path(__file__).parent / "assets"


def is_valid_time(time_str):
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False


def is_file_exist(filename):
    filepath = ASSETS_DIR / filename
    return filepath.is_file()


def check_config(config_file):
    config = toml.load(config_file)
    err_count = 0
    for hari in ("senin", "selasa", "rabu", "kamis", "jumat", "sabtu"):
        if hari not in config.keys():
            print("Notice: konfig hari", hari, "tidak ada.")
            continue

        config_harian = config[hari]
        for bel in config_harian:
            if not is_valid_time(bel["jam"]):
                print(
                    "Konfig waktu bel di hari",
                    hari,
                    "ada yang error. Silahkan diperbaiki!",
                )
                print("error di bagian => jam =", bel["jam"])
                err_count += 1
                break

            if not is_file_exist(bel["file"]):
                print("Error, file tidak ditemukan pada konfig hari", hari)
                print("nama file yang bermasalah:", bel["file"])
                err_count += 1
                break

    print("Jumlah total Error:", err_count)


if __name__ == "__main__":
    import sys

    config_file = sys.argv[1]
    check_config(config_file)
