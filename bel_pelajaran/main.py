import sys
from pathlib import Path
from time import sleep

import playsound3
import schedule
import toml

from bel_pelajaran.database import has_config, load_config, save_config

ASSETS_DIR = Path(__file__).parent.parent / "assets"


def play_audio(audio_file):
    playsound3.playsound(str(audio_file))


def rundown_bel(config_harian):
    sleep(0.1)
    c = 1
    for bel in config_harian:
        print("> {}: waktu [{}] - file [{}]".format(c, bel["jam"], bel["file"]))
        sleep(0.1)
        c += 1


def main():
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        config = toml.load(config_file)
        save_config(config)
    else:
        if not has_config():
            print("Error: No schedule configuration found in database.")
            print(
                "Please provide a config file: uv run python -m bel_pelajaran.main <config.toml>"
            )
            sys.exit(1)
        config = load_config()

    for bel in config["senin"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().monday.at(bel["jam"]).do(play_audio, audio_file=file)

    for bel in config["selasa"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().tuesday.at(bel["jam"]).do(play_audio, audio_file=file)

    if "rabu" not in config.keys():
        config["rabu"] = config["selasa"].copy()
    for bel in config["rabu"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().wednesday.at(bel["jam"]).do(play_audio, audio_file=file)

    if "kamis" not in config.keys():
        config["kamis"] = config["selasa"].copy()
    for bel in config["kamis"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().thursday.at(bel["jam"]).do(play_audio, audio_file=file)

    for bel in config["jumat"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().friday.at(bel["jam"]).do(play_audio, audio_file=file)

    if "sabtu" not in config.keys():
        config["sabtu"] = config["selasa"].copy()
    for bel in config["sabtu"]:
        file = ASSETS_DIR / bel["file"]
        schedule.every().saturday.at(bel["jam"]).do(play_audio, audio_file=file)

    for hari in ("senin", "selasa", "rabu", "kamis", "jumat", "sabtu"):
        print("|| Hari {}".format(hari))
        rundown_bel(config[hari])
        print("||======================== \n")
        sleep(0.5)

    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == "__main__":
    main()
