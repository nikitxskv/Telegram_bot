# -*- coding: utf-8 -*-

import sys
import ssl
import wget
import pickle
import logging
import telegram
import requests
import os
import threading
import collections
from time import sleep
from urllib2 import URLError
from os import remove, renames
from my_settings import vk_api_token, vk_user_id, telegram_api_token
from requests.exceptions import ReadTimeout, ConnectTimeout, SSLError

helptext = 'help:\n\'Songlist\' - show new songs, \n\'My\' - show my songs\nAlso you can type the title of song for search.'

reply_markup_1 = telegram.ReplyKeyboardMarkup([['Menu', '1', '2'],
                                             ['3', '4', '5', '6', '7', '8'],
                                             ['9', '10', '11', '12', '13', '14'],
                                             ['15', '16', '17', '18', '19', '20']])

reply_markup_2 = telegram.ReplyKeyboardMarkup([['Songlist', 'My']], resize_keyboard=True)

default_songs_count = 20
domain = 'oamusic'

offset = {}

def main():
    # Telegram Bot Authorization Token
    bot = telegram.Bot(telegram_api_token)

    # get the first pending update_id, this is so we can skip over it in case
    # we get an "Unauthorized" exception.
    try:
        update_id = bot.getUpdates()[0].update_id
    except IndexError:
        update_id = None

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    while True:
        try:
            update_id = echo(bot, update_id)
        except telegram.TelegramError as e:
            # These are network problems with Telegram.
            if e.message in ("Bad Gateway", "Timed out"):
                sleep(1)
            elif e.message == "Unauthorized":
                # The user has removed or blocked the bot.
                update_id += 1
            else:
                raise e
        except URLError as e:
            # These are network problems on our end.
            sleep(1)


def echo(bot, update_id):

    for update in bot.getUpdates(offset=update_id, timeout=10):
        chat_id = update.message.chat_id
        update_id = update.update_id + 1
        message = update.message.text
        with open('user_log.txt', 'a+') as f:
            s = update.message.chat['first_name'].encode('utf-8') + ': ' + update.message.text.encode('utf-8') + '\n'
            f.write(s)
        if message:
            print message.lower()
            if message.lower() in ["songlist", "my"]:
                update_song_list(message.lower())
                bot.sendMessage(chat_id=chat_id, text=get_songlist(), reply_markup=reply_markup_1)
            elif message.isdigit() and 0 < int(message) < 21:
                bot.sendMessage(chat_id=chat_id, text='wait a second..')
                d = threading.Thread(target=send_song, args=(bot, chat_id, int(message)))
                d.start()
            elif message.lower() == 'menu':
                bot.sendMessage(chat_id=chat_id, text=helptext, reply_markup=reply_markup_2)
            else:
                update_song_list("search", message.lower())
                bot.sendMessage(chat_id=chat_id, text=get_songlist(), reply_markup=reply_markup_1)
    return update_id


def send_song(bot, chat_id, song_id):
    song = get_song(song_id)
    if not song:
        bot.sendMessage(chat_id=chat_id, text='Song isn\'t available')
    else:
        bot.sendAudio(chat_id=chat_id, audio=song)
        song_name = song.name
        song.close()
        remove(song_name)

def get_songlist():
    ''' Загружает список песен из файла и
        конструирует список из названий песен. '''

    try:
        songlist = ''
        with open('songlist.pkl', 'rb') as f:
            songs = pickle.load(f)
        for i, song in enumerate(songs):
            songlist += '{}: {}\n'.format(i + 1, song[0].encode('utf-8'))
        return songlist if songlist else "No results"
    except IOError:
        return None


def update_song_list(audio_place, query='famous'):
    ''' Обновляет список и загружает его на диск. '''
    if audio_place == "songlist":
        urls, titles, offset = [], [], 0
        fresh = True
        while fresh:
            response = requests.get('https://api.vk.com/method/wall.get',
                                    params={
                                        'domain': domain,
                                        'count': 50,
                                        'offset': offset,
                                        'access_token': vk_api_token
                                    })
            offset += 50
            for post in response.json()['response']:
                try:
                    counter = collections.Counter()
                    for attachment in post['attachments']:
                        counter[attachment['type']] += 1
                        if attachment['type'] == 'audio':
                            audio = attachment['audio']
                    if counter['audio'] == 1:
                        if len(urls) == default_songs_count:
                            fresh = False
                            break
                        urls.append(audio['url'])
                        titles.append(audio['artist'] + ' - ' + audio['title'])
                        # print('{} songs are collect.'.format(len(urls)), end='\r')
                except (TypeError, AttributeError) as e:
                    pass
    elif audio_place == "my":
        urls, titles, offset = [], [], 0
        response = requests.get('https://api.vk.com/method/audio.get',
                                params={
                                    'owner_id': vk_user_id,
                                    'count': 20,
                                    'offset': offset,
                                    'access_token': vk_api_token
                                })
        for audio in response.json()["response"][1:]:
            urls.append(audio['url'])
            titles.append(audio['artist'] + ' - ' + audio['title'])
    elif audio_place == "search":
        urls, titles, offset = [], [], 0
        response = requests.get('https://api.vk.com/method/audio.search',
                                params={
                                    'q': query,
                                    'auto_complete': 1,
                                    'sort': 2,
                                    'search_own': 1,
                                    'count': 20,
                                    'offset': offset,
                                    'access_token': vk_api_token,
                                    'v': 3
                                })
        for audio in response.json()["response"][1:]:
            urls.append(audio['url'])
            titles.append(audio['artist'] + ' - ' + audio['title'])
    # if  titles:
    songs = zip(titles, urls)
    # else:
    #     songs = zip(["No results"], [""])
    with open('songlist.pkl', 'wb') as f:
        pickle.dump(songs, f)
    return 'Songs were updated.'


def get_song(song_index):
    ''' Достает url песни с указанным индексом, скачивает ее и
        возвращает в виде файла. '''

    try:
        with open('songlist.pkl', 'rb') as f:
            songs = pickle.load(f)
            # print songs
            url = songs[song_index - 1][1]
        song_name = wget.download(url)
        song_name = song_name.encode('utf-8')
        os.rename(song_name, "lol.mp3")
        song = open("lol.mp3")
        # song = open(song_name)
        return song
    except IOError:
        return None


if __name__ == '__main__':
    main()


