from pathlib import Path

import playsound3

ASSETS_DIR = Path(__file__).parent / "assets"


def play_audio(audiofile):
    playsound3.playsound(str(audiofile))


def check_sound():
    play_audio(str(ASSETS_DIR / "1.mp3"))


if __name__ == "__main__":
    check_sound()
