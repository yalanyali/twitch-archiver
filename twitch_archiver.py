#!/usr/bin/python

from __future__ import unicode_literals

import requests
import os
import threading
import time
import json
import sys
import subprocess
import datetime
import getopt
from pathlib import Path

import youtube_dl

import youtube_uploader as YT

# https://id.twitch.tv/oauth2/token?client_id=c710oiul44s9fvc88n2h0bhaijl9ao&client_secret=nelycobymdeifqur86ok09otpe1aqx&grant_type=client_credentials
class TwitchArchiver:
    def __init__(self):
        self.client_id = os.environ[
            'TWITCH_CLIENT_ID']  # throws error when not found
        self.ffmpeg_path = 'ffmpeg'
        self.youtubedl_path = 'youtube-dl'
        self.refresh = 5 * 60  # seconds
        self.root_path = "twitch-archive"
        self.username = ""
        self.keyword = ""
        self.delete_media_on_error = False

    def run(self):
        self.recorded_path = os.path.join(self.root_path, self.username)
        self.log("Checking.")
        self.loopcheck()

    def check_user(self):
        url = 'https://api.twitch.tv/helix/streams?user_login=' + self.username
        info = None
        status = None
        try:
            r = requests.get(url,
                             headers={
                             "Client-ID": self.client_id,
                             "Authorization": "Bearer if3euz3ilourooefvjzszuyxtcszj0"
                             },
                             timeout=15)
            info = r.json()['data']  # [0]
            if len(info) == 0:
                status = 1  # Error
            elif info[0]['type'] == 'live':
                if self.keyword:
                    if self.keyword.lower() not in info[0]['title'].lower():
                        status = 3  # live but bad
                    else:
                        status = 0  # live and good
                else:
                    status = 0  # live
        except requests.exceptions.RequestException as e:
            if e.response:
                if e.response.reason == 'Not Found' or e.response.reason == 'Bad Entity':
                    status = 2
        return status, info

    def loopcheck(self):
        while True:
            status, info = self.check_user()
            if status == 2:
                # self.log("Not found. Invalid username or typo.")
                time.sleep(self.refresh)
            elif status == 1:
                self.log(self.username +
                         " currently offline, checking again in " +
                         str(self.refresh) + " seconds.")
                time.sleep(self.refresh)
            elif status == 3:
                self.log(self.username + " online but streams: " +
                         info[0]['title'])
                time.sleep(self.refresh)
            elif status == 0:
                self.log(self.username +
                         " online. Stream recording in session.")
                filename = self.username + " - " + datetime.datetime.now(
                ).strftime("%d.%m.%Y %H:%M") + " - " + (info[0]['title']
                                                        or 'Stream') + ".mp4"

                # clean filename
                filename = "".join(
                    x for x in filename
                    if x.isalnum() or x in [" ", "-", "_", ".", ":"])

                recorded_filename = os.path.join(self.recorded_path, filename)

                # start youtube-dl process (blocking)
                try:
                    self.log('YOUTUBEDL DOWNLOADS')
                    ydl_opts = {
                        'outtmpl': recorded_filename,
                        'progress_hooks': [self.ytdl_callback],
                        'quiet': True
                    }
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        ydl.download(["https://twitch.tv/" + self.username])

                    self.log(
                        "Recording is done. Going back to checking while uploading."
                    )
                except Exception as e:
                    self.log("DEBUG " + str(e))
                    self.log("Dertler.")
                finally:
                    time.sleep(self.refresh)

    def ytdl_callback(self, d):
        if d['status'] == 'finished':
            # start uploader thread
            thread = threading.Thread(
                target=self.upload,
                args=(d['filename'], d['filename'].replace(".mp4", "").replace(
                    "twitch-archive/%s/" % self.username, "")))
            thread.start()

    def upload(self, filepath, title):
        self.log("UPLOADING FILE: " + filepath)
        args = YT.DEFAULT_ARGS
        args.file = filepath
        args.title = title
        args.description = title
        service = YT.get_authenticated_service(args)
        try:
            YT.initialize_upload(service, args)
            os.remove(filepath)
            self.log('UPLOADED AND DELETED')
        except Exception:
            self.log("Error while uploading.")
        if self.delete_media_on_error:
            os.remove(filepath)
            self.log('DELETED WITHOUT UPLOADING')

    def log(self, text):
        print(self.username + ': ' + text)


def main(argv):
    username_list = os.getenv('TWITCH_USER', '').lower().split(',')
    if len(username_list) == 0:
        print('No username given.')
        sys.exit()
    thread_list = []
    for username in username_list:
        twitch_archiver = TwitchArchiver()
        twitch_archiver.username, _, twitch_archiver.keyword = username.partition(
            ':')
        if (os.getenv('DELETE_MEDIA_ON_ERROR', '').lower() == 'true'):
            twitch_archiver.delete_media_on_error = True
        thread = threading.Thread(target=twitch_archiver.run)
        thread.start()
        # thread.join()
        thread_list.append(thread)
    # usage_message = 'twitch_archiver.py -u <username,username2...>'
    # try:
    #     opts, _ = getopt.getopt(argv, "hu:q:", ["username=username,username2..."])
    # except getopt.GetoptError:
    #     print(usage_message)
    #     sys.exit(2)
    # for opt, arg in opts:
    #     if opt == '-h':
    #         print(usage_message)
    #         sys.exit()
    #     elif opt in ("-u", "--username"):
    #         twitch_archiver.username = arg

    # twitch_archiver.run()


if __name__ == "__main__":
    main(sys.argv[1:])

