#!python2
import os, sys, re, json, urllib.request, configparser
import ctypes
import platform
from flask import Flask, request
from pymessenger import Bot
from datetime import datetime
from config import Config
from commands import *

config = None
app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    #webhook verificaiton
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == config['Messenger']['VERIFICATION_TOKEN']:
            return "Verification token mismatch, 403"
        return request.args["hub.challenge"],200
    return "Hello, World", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    log(data)
    try:
        if data['object'] == 'page':
            for entry in data['entry']:
                for messaging_event in entry['messaging']:
                    #IDs
                    sender_id = messaging_event['sender']['id']
                    recipient_id = messaging_event['recipient']['id']

                    if messaging_event.get('message'):
                        if "text" in messaging_event['message']:
                            bot.send_text_message(sender_id, parse_command(sender_id, messaging_event['message']['text']))
                        else:
                            bot.send_text_message(sender_id, "Sorry, I don't respond to non-text messages yet")
    except BaseException as e:
        print("EXCEPTION FOUND: "+str(e))
        bot.send_text_message(sender_id, "Sorry, there was an error in the server. If you are the admin, please check the logs")
        log_to_file(str(e))
    return "ok", 200


def get_full_status():
    space = get_free_space_mb()
    temps = get_system_temperature()
    temp_message = ""
    for val in temps:
        temp_message += "\t%s: %s\n" % (val, temps[val])
    message = "Free Space: %s \nCore Temps: \n%s" % (space['free'], temp_message)
    return message

def get_temps_message():
    temps = get_system_temperature()
    temp_message = ""
    for val in temps:
        temp_message += "\t%s: %s\n" % (val, temps[val])
    message = "Core Temps: \n%s" % temp_message
    return message

def get_disk_usage_message():
    space = get_free_space_mb()
    message = "Free Space: %s" % space['free']
    return message

def get_torrent_list_message():
    data = subprocess.check_output("deluge-console \"connect 127.0.0.1:58846 "+config['Deluge']['name']+" "+config['Deluge']['pass']+"; info\"", shell=True)
    data = json.dumps(data.decode("utf-8"))#convert to utf 8 due to byte sequence output
    data = re.split(r"\\n", data)
    message = ""
    for string in data:
        if re.match(r"Name: ([\W\w\s]*)", string):
            message += "\n\n" + re.match(r"Name: ([\W\w\s]*)", string).group(1) + "\n"
        elif re.match(r"State: (\w*)", string):
            message += "State: " + re.match(r"State: (\w*)", string).group(1) + " "
        elif re.match(r"Progress: (\d*\.?\d*%)", string):
            message += re.match(r"Progress: (\d*\.?\d*%)", string).group(1)
    return message

def add_torrent_file(message):
    file_url = re.match(r"(\w*) (\w*) ((http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)|(magnet:\?xt=urn:[a-z0-9\S]*))", message).group(3)
    torrent_directory = ""
    if ("magnet" in file_url):
        torrent_directory = file_url
    else:
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        urllib.request.urlretrieve(file_url, torrent_directory)
        torrent_directory = config['Deluge']['torrent_directory']
    message = "Download successful, adding to torrent"
    data = subprocess.check_output("deluge-console \"connect 127.0.0.1:58846 mark pass; add "+torrent_directory+"\"", shell=True)
    return message

def is_valid_server_command(message, keyword):
    server_command = re.match(r"(\w*) (\w*)", message)
    if server_command.group(2) == keyword:
        return True
    else:
        return False

def say_hello(sender_id):
    return_message = ""
    sender_name = bot.get_user_info(sender_id, ["first_name", "last_name"])
    if name_exists(sender_name):
        return_message = "Hello, "+sender_name['first_name']
        log_to_file(sender_name['first_name']+" "+sender_name['last_name'] + " said hello")
    else:
        return_message = "Sorry, unrecognized user"
        log_to_file("Unrecognized "+ sender_name['first_name']+" "+sender_name['last_name'])
    return return_message

def parse_command(sender_id, message):
    orig_message = re.match(r"(\w*)", message)
    command_type = orig_message.group(1).lower()
    return_message = None
    reg_match = get_second_arg(message)
    if command_type == "server":
        if reg_match == "status":
            return_message = get_full_status()
            log_to_file("Full status report requested")
        elif reg_match == "temps":
            return_message = get_temps_message()
            log_to_file("Temperatures report requested")
        elif reg_match == "usage":
            return_message = get_disk_usage_message()
            log_to_file("Disk usage report requested")
    elif command_type == "torrent":
        if reg_match == "list":
            return_message = get_torrent_list_message()
            log_to_file("Torrent list requested")
        elif reg_match == "add":
            return_message = add_torrent_file(message)
            log_to_file("A Torrent file has been added")
    elif command_type == "hello" or command_type == "hi":
        return_message = say_hello(sender_id)
    else:
        return_message = "Invalid command: %s" % orig_message.group(1)
    return return_message

def name_exists(sender_name):
    result = False
    for name in names:
        joined_name_from_file = name['last_name']+" "+name['first_name']
        joined_sender_name = name['last_name']+ " "+ name['first_name']
        if joined_name_from_file == joined_sender_name:
            result = True
            break
    return result

def get_second_arg(message):
    try:
        return re.match(r"(\w*) (\w*)", message).group(2)
    except:
        return ""

def get_config_ini():
    config = configparser.ConfigParser()
    config_file = config.read('config.ini')
    if "Messenger" not in config or "Deluge" not in config or len(config_file) == 0:
        config['Messenger'] = {}
        config['Messenger']['PAGE_ACCESS_TOKEN'] = ''
        config['Messenger']['VERIFICATION_TOKEN'] = ''
        config['Deluge'] = {}
        config['Deluge']['name'] = ''
        config['Deluge']['password'] = ''
        config['Deluge']['torrent_directory'] = ''
        with open('config.ini', 'w+') as configfile:
            config.write(configfile)
    return config

def get_names():
    with open('names.json') as data:
        names = json.load(data)
    #
    # names = None
    # if os.path.exists("names.json"):
    #     print("file exists")
    #     with open('names.json') as data:
    #         names = json.load(data)
    # else:
    #     print("File not exist")
    #     data = [{
    #         'last_name': "Last Name",
    #         'first_name': "First Name"
    #     }]
    #     with open('names.json', 'w+') as outfile:
    #         json.dumps(data, outfile)
    return names


def log_to_file(message):
    f = open('logs.txt', 'a')
    f.write(message+ " " +str(datetime.today()) +"\n")

def log(message):
    print(message)
    sys.stdout.flush()

if __name__ == "__main__":
    config = get_config_ini()
    bot = Bot(config['Messenger']['PAGE_ACCESS_TOKEN'])
    names = get_names()
    app.run(debug = True, port = 80)
