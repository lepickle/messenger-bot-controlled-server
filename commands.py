import psutil, subprocess, platform
import os
from config import *

def get_free_space_mb():
    """Return folder/drive free space (in megabytes)."""
    gb_conv = 1000000000
    disk_results = {}
    disk_usage = psutil.disk_usage('/')
    disk_results['free'] = disk_usage.free / gb_conv
    disk_results['used'] = disk_usage.used / gb_conv
    return disk_results

def get_system_temperature():
    sensors = psutil.sensors_temperatures()
    results = {}
    for val in sensors['coretemp']:
        results[val.label] = val.current
    return results

def get_torrent_list():
	raw_torrent_input = subprocess.check_output("deluge-console info", shell=True)
	clean_torrent_input = raw_torrent_input
	return clean_torrent_input
