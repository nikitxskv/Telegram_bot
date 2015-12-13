# -*- coding: utf-8 -*-

import sys
import ssl
import wget
import pickle
import random
import logging
import telegram
import requests
from lxml import html
from time import sleep
from urllib2 import URLError
from os import remove, renames
from requests.exceptions import ReadTimeout, ConnectTimeout, SSLError


helptext = 'help:\n\'songlist\' - show new songs\n\'update\' - update songlist'

reply_markup = telegram.ReplyKeyboardMarkup([['songlist', 'update', '1', '2'],
                                             ['3', '4', '5', '6', '7', '8'],
                                             ['9', '10', '11',
                                              '12', '13', '14'],
                                             ['15', '16', '17',
                                              '18', '19', '20']])


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

    songs, page_number = [], 1
    while True:
        try:
            page = html.fromstring(requests.post('https://vk.com/oamusic',
                                                 timeout=5).text)
            break
        except (ReadTimeout, ConnectTimeout, SSLError, ssl.SSLError) as e:
            print(e)
    post_blocks = page.xpath('//div[@id="page_wall_posts"]' +
                             '/div[@class="post all own"]')
    while True:
        for post_block in post_blocks:
            audio_info = post_block.xpath('.//div[@class="wall_text"]' +
                                          '//div[@class="post_media ' +
                                          'clear_fix wall_audio"]/div')
            if len(audio_info) == 1:
                arr = []
                # Достаем название песни
                song_info = post_block.xpath('.//div[@class="area clear_fix"' +
                                             ']/table')[0]
                artist = song_info.xpath('.//div[@class="title_wrap fl_l"]' +
                                         '/b')[0].text_content()
                title = song_info.xpath('.//div[@class="title_wrap fl_l"]/sp' +
                                        'an[@class="title"]')[0].text_content()
                # Достаем ссылку для скачивания и id поста
                href = song_info.xpath('.//input')[0].attrib['value']
                song_id = post_block.attrib['id']
                # Смотрим, что бы аудио не повторялись и добавляем их в список
                if not songs or songs[-1][1] != href:
                    arr.append(artist + ' - ' + title[:-1])
                    arr.append(href)
                    songs.append(arr)
                if len(songs) == 20:
                    break
        if len(songs) == 20:
            break
        post = {'act': 'get_wall', 'al': '1', 'fixed': '107318', 'type': 'own',
                'offset': str(9 * page_number), 'owner_id': '-24807991'}
        while True:
            try:
                r = requests.post('https://vk.com/al_wall.php', data=post,
                                  timeout=5).text.replace('<>', '')[4:]
                break
            except (ReadTimeout, ConnectTimeout, SSLError, ssl.SSLError) as e:
                print(e)
        post_blocks = html.fromstring(r).xpath('./div[@class="post all own"]')
        page_number += 1

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
        song_name = wget.download(url, bar=None)
        song_name = song_name.encode('utf-8')
        song = open(song_name)
        return song
    except IOError:
        return None


if __name__ == '__main__':
    main()
