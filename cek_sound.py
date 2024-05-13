from  pydub import AudioSegment
from pydub.playback import play

def play_audio(audiofile):
    sound = AudioSegment.from_file(audiofile)
    play(sound)
    
if __name__ == "__main__" :
    play_audio('assets/1.mp3')