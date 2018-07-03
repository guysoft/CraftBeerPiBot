#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A telegram bot that pulls information from CraftBeerPi

@author Guy Sheffer (GuySoft) <guysoft at gmail dot com>
"""
from telegram.ext import Updater
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, Filters, ConversationHandler, RegexHandler
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ReplyKeyboardMarkup
from emoji import emojize
import logging
from configparser import ConfigParser
from collections import OrderedDict
import os
import json
import glob
import sys
from urllib.request import urlopen, URLError
import time
import pytz
import subprocess
import requests
from sqlalchemy import create_engine
from database import insert_new_user_to_db, mysql_init_db, has_user, restricted

DIR = os.path.dirname(__file__)


def ini_to_dict(path):
    """ Read an ini path in to a dict

    :param path: Path to file
    :return: an OrderedDict of that path ini data
    """
    config = ConfigParser()
    config.read(path)
    return_value = OrderedDict()
    for section in reversed(config.sections()):
        return_value[section] = OrderedDict()
        section_tuples = config.items(section)
        for itemTurple in reversed(section_tuples):
            return_value[section][itemTurple[0]] = itemTurple[1]
    return return_value


def run_command(command, blocking=True):
    p = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if blocking:
        return [p.stdout.read().decode("utf-8"), p.stderr.read().decode("utf-8")]
    return


def get_timezones():
    return_value = {}
    for tz in pytz.common_timezones:
        c = tz.split("/")
        if len(c) > 1:
            if c[0] not in return_value.keys():
                return_value[c[0]] = []
            return_value[c[0]].append(c[1])

        for i in ["GMT"]:
            if i in return_value.keys():
                return_value.pop(i)

    return return_value


class TelegramCallbackError(Exception):
    def __init__(self, message=""):
        self.message = message


def build_callback(data):
    return_value = json.dumps(data)
    if len(return_value) > 64:
        raise TelegramCallbackError("Callback data is larger tan 64 bytes")
    return return_value


def handle_cancel(update):
    query = update.message.text
    if query == "Close" or query == "/cancel":
        reply = "Perhaps another time"
        update.message.reply_text(reply)
        return reply
    return None


class Bot:
    def __init__(self, token, craftbeerpi_url):
        self.engine = create_engine(get_uri(settings))
        self.selected_continent = ""
        self.craftbeerpi_url = craftbeerpi_url

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        self.TIMEZONE_CONTINENT, self.TIMEZONE_TIME = range(2)

        # Add conversation handler with the states TIMEZONE_CONTINENT, TIMEZONE_TIME
        set_timezone_handler = ConversationHandler(
            entry_points=[CommandHandler('timezone', self.set_timezone)],
            states={
                self.TIMEZONE_CONTINENT: [
                    RegexHandler('^(' + "|".join(get_timezones().keys()) + '|/cancel)$', self.timezone_continent)],

                self.TIMEZONE_TIME: [RegexHandler('^(.*)$', self.timezone_time)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(set_timezone_handler)

        help_handler = CommandHandler('help', self.help)
        self.dispatcher.add_handler(help_handler)

        time_handler = CommandHandler('time', self.time)
        self.dispatcher.add_handler(time_handler)

        status_handler = CommandHandler('status', self.status)
        self.dispatcher.add_handler(status_handler)

        toggle_kettle_1_handler = CommandHandler('toggle_kettle_1', self.toggle_kettle_1)
        self.dispatcher.add_handler(toggle_kettle_1_handler)

        self.SET_KETTLE_1_TEMP = range(1)
        set_kettle_1_handler = ConversationHandler(
            entry_points=[CommandHandler('set_kettle_1', self.start_set_kettle_1)],
            states={

                self.SET_KETTLE_1_TEMP: [RegexHandler('^(.*)$', self.set_kettle_1)]
            },
            fallbacks=[]
        )

        self.dispatcher.add_handler(set_kettle_1_handler)

        self.dispatcher.add_error_handler(self.error_callback)

        return

    def set_temp(self, pid, temp):
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        r = requests.post(self.craftbeerpi_url + '/api/kettle/' + str(int(pid)) + "/targettemp", data=json.dumps({'temp': int(temp)}), headers=headers)
        print(r.text)
        return

    def start(self, bot, update):
        if not has_user(self.engine, update.message.from_user.id):
            insert_new_user_to_db(self.engine, update.message.from_user.id, update.message.from_user.full_name)
        bot.send_message(chat_id=update.message.chat_id,
                         text="I'm a bot to do stuff with CraftBeerPi, please type /help for info"
                              "Please add yourself as an admin in the web interface to control the bot at:"
                              "http://craftbeerpi.local:5001")
        return

    @restricted
    def set_timezone(self, bot, update):
        keyboard = []

        for continent in sorted(get_timezones().keys()):
            keyboard.append([InlineKeyboardButton(continent)])

        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        update.message.reply_text('Please select a continent, or /cancel to cancel:', reply_markup=reply_markup)
        return self.TIMEZONE_CONTINENT

    def timezone_continent(self, bot, update):
        reply = handle_cancel(update)
        if reply is None:
            keyboard = []
            self.selected_continent = update.message.text
            for continent in sorted(get_timezones()[self.selected_continent]):
                keyboard.append([InlineKeyboardButton(continent)])
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            update.message.reply_text('Please select a timezone, or /cancel to cancel:', reply_markup=reply_markup)

            return self.TIMEZONE_TIME
        return ConversationHandler.END

    def timezone_time(self, bot, update):
        reply = handle_cancel(update)
        if reply is None:
            timezone = self.selected_continent + "/" + update.message.text

            timezone_script = os.path.join(DIR, "set_timezone.sh")

            if os.path.isfile(os.path.join("/usr/share/zoneinfo/", timezone)):
                print(run_command(["sudo", timezone_script, timezone]))
                update.message.reply_text(emojize(":clock4: ", use_aliases=True) + 'Timezone set set to: ' + timezone)
            else:
                update.message.reply_text(
                    emojize(":no_entry_sign: ", use_aliases=True) + 'Timezone file does not exist: ' + timezone)

            return ConversationHandler.END
        return ConversationHandler.END

    def cancel(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Perhaps another time")
        return

    @restricted
    def toggle_kettle_1(self, bot, update):
        r = requests.post(self.craftbeerpi_url + '/api/kettle/1/automatic', data={'id': '1'})
        bot.send_message(chat_id=update.message.chat_id, text="Kettle states:" + self.get_kettles_state())
        return

    @restricted
    def start_set_kettle_1(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Input Kettle Temp:")
        return self.SET_KETTLE_1_TEMP

    def set_kettle_1(self, bot, update):
        temp = update.message.text.strip()
        self.set_temp(1, temp)
        bot.send_message(chat_id=update.message.chat_id, text="Kettle temp set\n" + self.get_kettles_state())
        return ConversationHandler.END

    @restricted
    def get_kettles_state(self):
        return_value = []
        r = requests.get(self.craftbeerpi_url + '/api/kettle/state')
        kettles = json.loads(r.text)
        for i in kettles.keys():
            state = kettles[i]["automatic"]
            target_temp = str(kettles[i]["target_temp"])
            if state:
                state = "on"
            else:
                state = "off"
            return_value.append(i + " " + state + ", \u2316: " + target_temp + "C")
        return "\n".join(return_value)


    def error_callback(self, bot, update, error):
        try:
            raise error
        except Unauthorized as e:
            # remove update.message.chat_id from conversation list
            pass
        except BadRequest:
            # handle malformed requests - read more below!
            pass
        except TimedOut:
            # handle slow connection problems
            pass
        except NetworkError:
            # handle other connection problems
            pass
        except ChatMigrated as e:
            # the chat_id of a group has changed, use e.new_chat_id instead
            pass
        except TelegramError:
            # handle all other telegram related errors
            pass
        return

    def help(self, bot, update):
        icon = emojize(":information_source: ", use_aliases=True)
        text = icon + " The following commands are available:\n"

        commands = [["/status", "Check temps status"],
                    ["/timezone", "Set the timezone (only works if sudo requires no password)"],
                    ["/time", "Print time and timezone on device"],
                    ["/toggle_kettle_1", "toggle starting the first PID"],
                    ["/set_kettle_1", "set target temp on kettle 1"],
                    ["/help", "Get this message"]
                    ]

        for command in commands:
            text += command[0] + " " + command[1] + "\n"

        bot.send_message(chat_id=update.message.chat_id, text=text)

    @restricted
    def time(self, bot, update):
        reply, _ = run_command(["date"])
        bot.send_message(chat_id=update.message.chat_id, text=reply)
        return

    @restricted
    def status(self, bot, update):
        reply = ""
        reply += "\nPID status :\n"
        reply += self.get_kettles_state() + "\n\n"

        r = requests.get(self.craftbeerpi_url + '/api/thermometer/last')
        thermometers = json.loads(r.text)

        reply += "Temps status :\n"
        for key in thermometers.keys():
            reply += emojize(":thermometer: " + str(key) + ": " + str(thermometers[key]) + "C\n",
                             use_aliases=True)


        bot.send_message(chat_id=update.message.chat_id, text=reply)
        return

    def run(self):
        self.updater.start_polling()
        return


def check_connectivity(reference):
    try:
        urlopen(reference, timeout=1)
        return True
    except URLError:
        return False


def wait_for_internet():
    while not check_connectivity("https://api.telegram.org"):
        print("Waiting for internet")
        time.sleep(1)


if __name__ == "__main__":
    from common import get_config, CONFIG_PATH, get_uri_without_db, get_uri
    from webserver import webserver

    settings = get_config()

    mysql_init_db(get_uri_without_db(settings), settings)
    webserver.init_db(get_uri(settings))

    if not CONFIG_PATH:
        print("Error, no config file")
        sys.exit(1)

    if ("main" not in settings) or ("token" not in settings["main"]):
        print("Error, no token in config file")

    wait_for_internet()

    a = Bot(settings["main"]["token"], settings)
    a.run()
    print("Bot Started")

    webserver.run()
    print("Webserver started")

