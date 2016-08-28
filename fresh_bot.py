# -*- coding: utf-8 -*-

import sys
import ssl
import wget
import pickle
import logging
import telegram
import requests
import collections
from time import sleep
from urllib2 import URLError
from os import remove, renames
from requests.exceptions import ReadTimeout, ConnectTimeout, SSLError


helptext = 'help:\n\'songlist\' - show new songs\n\'update\' - update songlist'

print dir(telegram)

reply_markup = telegram.ReplyKeyboardMarkup([['songlist', 'update', '1', '2'],
                                             ['3', '4', '5', '6', '7', '8'],
                                             ['9', '10', '11',
                                              '12', '13', '14'],
                                             ['15', '16', '17',
                                              '18', '19', '20']])
default_songs_count = 20
domain = 'oamusic'


def main():
    # Telegram Bot Authorization Token
    bot = telegram.Bot('129258075:AAFa3R8w_HiXAPVwczN3p8EgtrZjfIGBjIY')

    # get the first pending update_id, this is so we can skip over it in case
    # we get an "Unauthorized" exception.
    try:
        update_id = bot.getUpdates()[0].update_id
    except IndexError:
        update_id = None

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        print update.message.chat['first_name'] + ': ' + update.message.text

        if message:
            if message.lower() == 'songlist':
                songlist = get_songlist()
                if songlist is None:
                    bot.sendMessage(chat_id=chat_id,
                                    text='please, update songlist')
                else:
                    bot.sendMessage(chat_id=chat_id, text=songlist)
            elif message.lower() == 'update':
                message = update_song_list()
                bot.sendMessage(chat_id=chat_id, text=message)
                songlist = get_songlist()
                bot.sendMessage(chat_id=chat_id, text=songlist)
            elif message.isdigit():
                if 0 < int(message) < 21:
                    bot.sendMessage(chat_id=chat_id,
                                    text='wait a second..')
                    song = get_song(int(message))
                    if not song:
                        bot.sendMessage(chat_id=chat_id,
                                        text='please, update songlist')
                    else:
                        bot.sendAudio(chat_id=chat_id, audio=song)
                        song_name = song.name
                        song.close()
                        remove(song_name)
                else:
                    bot.sendMessage(chat_id=chat_id, text='incorrect number')
            else:
                bot.sendMessage(chat_id=chat_id, text=helptext,
                                reply_markup=reply_markup)
    return update_id


def get_songlist():
    ''' Загружает список песен из файла и
        конструирует список из названий песен. '''

    try:
        songlist = ''
        with open('songlist.pkl', 'rb') as f:
            songs = pickle.load(f)
        for i, song in enumerate(songs):
            songlist += '{}: {}\n'.format(i + 1, song[0])
        songlist += '\nIf you want to listen - type the number of the song'
        return songlist
    except IOError:
        return None


def update_song_list():
    ''' Обновляет список и загружает его на диск. '''

    urls, titles, offset = [], [], 0
    fresh = True
    while fresh:
        response = requests.get('https://api.vk.com/method/wall.get',
                                params={
                                    'domain': domain,
                                    'count': 50,
                                    'offset': offset
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
    songs = zip(titles, urls)
    print songs
    with open('songlist.pkl', 'wb') as f:
        pickle.dump(songs, f)
    return 'Songs were updated.'


def get_song(song_index):
    ''' Достает url песни с указанным индексом, скачивает ее и
        возвращает в виде файла. '''

    try:
        with open('songlist.pkl', 'rb') as f:
            songs = pickle.load(f)
            url = songs[song_index - 1][1]
        song_name = wget.download(url)
        song_name = song_name.encode('utf-8')
        song = open(song_name)
        return song
    except IOError:
        return None


if __name__ == '__main__':
    main()


