import toml
from datetime import datetime
from os import path
import sys

def is_valid_time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M')  # Assuming the time format is HH:MM
        return True
    except ValueError:
        return False

def is_file_exist(filename):
    filepath = 'assets/'+filename
    if(path.isfile(filepath)):
        return True
    return False
    
# todo: Check Config, pastikan jam dan integritas file di konfig sesuai!
config_file = sys.argv[1]
config = toml.load(config_file)
err_count = 0
for hari in ('senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu'):
    if hari not in config.keys():
        print('Notice: konfig hari',hari,'tidak ada.')
        continue
    
    config_harian = config[hari]
    for bel in config_harian:
        if not is_valid_time(bel['jam']):
            print('Konfig waktu bel di hari', hari, 'ada yang error. Silahkan diperbaiki!')
            print('error di bagian => jam =', bel['jam'])
            err_count+=1
            break
        
        if not is_file_exist(bel['file']):
            print('Error, file tidak ditemukan pada konfig hari', hari)
            print('nama file yang bermasalah:', bel['file'])
            err_count+=1
            break
        
        
print('Jumlah total Error:',err_count)
    
