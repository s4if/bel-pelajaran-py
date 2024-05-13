from pydub import AudioSegment
from pydub.playback import play
import schedule
from time import sleep
import toml
import sys

def play_audio(audio_file):
    sound = AudioSegment.from_file(audio_file)
    play(sound)
    
def rundown_bel(config_harian):
    sleep(0.5)
    c = 1
    for bel in config_harian:
        print("> {}: waktu [{}] - file [{}]".format(c, bel['jam'], bel['file']))
        sleep(0.5)
        c+=1
    
if __name__ == '__main__':
    # load config
    config_file = sys.argv[1]
    config = toml.load(config_file)
    
    # senin
    for bel in config['senin']:
        file = 'assets/' + bel['file']
        schedule.every().monday.at(bel['jam']).do(play_audio, audio_file=file)
        
    # selasa
    for bel in config['selasa']:
        file = 'assets/' + bel['file']
        schedule.every().tuesday.at(bel['jam']).do(play_audio, audio_file=file)
        
    # rabu
    if not 'rabu' in config.keys():
        config['rabu'] = config['selasa'].copy()
    for bel in config['rabu']:
        file = 'assets/' + bel['file']
        schedule.every().wednesday.at(bel['jam']).do(play_audio, audio_file=file)
        
    # kamis
    if not 'kamis' in config.keys():
        config['kamis'] = config['selasa'].copy()
    for bel in config['kamis']:
        file = 'assets/' + bel['file']
        schedule.every().thursday.at(bel['jam']).do(play_audio, audio_file=file)
        
    # jumat
    for bel in config['jumat']:
        file = 'assets/' + bel['file']
        schedule.every().friday.at(bel['jam']).do(play_audio, audio_file=file)
        
    # sabtu
    if not 'sabtu' in config.keys():
        config['sabtu'] = config['selasa'].copy()
    for bel in config['sabtu']:
        file = 'assets/' + bel['file']
        schedule.every().saturday.at(bel['jam']).do(play_audio, audio_file=file)
    
    # last Check Hari
    for hari in ('senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu'):
        print('|| Hari {}'.format(hari))
        rundown_bel(config[hari])
        print("||======================== \n")
        sleep(0.5)
    
    # Main loop to execute scheduled tasks
    while True:
        schedule.run_pending()
        sleep(1)