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

class TwitchArchiver:
    def __init__(self):
        self.client_id = os.environ[
            'TWITCH_CLIENT_ID']  # throws error when not found
        self.client_secret = os.environ[
            'TWITCH_CLIENT_SECRET']  # throws error when not found
        self.ffmpeg_path = 'ffmpeg'
        self.youtubedl_path = 'youtube-dl'
        self.refresh = 3 * 60  # seconds
        self.root_path = "twitch-archive"
        self.username = ""
        self.keyword = ""
        self.delete_media_on_error = False
        self.access_token = ""

    def run(self):
        self.recorded_path = os.path.join(self.root_path, self.username)
        self.log("Checking.")
        self.check_loop()

    def check_user(self):
        url = 'https://api.twitch.tv/helix/streams?user_login=' + self.username
        info = None
        status = None
        try:
            r = requests.get(url,
                             headers={
                                 "Client-ID": self.client_id,
                                 "Authorization": "Bearer " + self.access_token
                             },
                             timeout=15)

            # Auth check
            if ("status" in r.json() and r.json()["status"] == 401):
                self.refresh_token()
                status = "TOKEN"
                return status, info

            info = r.json()['data']  # [0]
            if len(info) == 0:
                status = "OFFLINE"  # Error
            elif info[0]['type'] == 'live':
                if self.keyword:
                    if self.keyword.lower() not in info[0]['title'].lower():
                        status = "LIVE_BUT_FILTERED"  # live but bad
                    else:
                        status = "LIVE" # live and good
                else:
                    status = "LIVE"
        except requests.exceptions.RequestException as e:
            if e.response:
                if e.response.reason == 'Not Found' or e.response.reason == 'Bad Entity':
                    status = "NOT_FOUND"
        return status, info

    def check_loop(self):
        while True:
            status, info = self.check_user()
            if status == "NOT_FOUND":
                self.log("Not found. Invalid username or typo.")
                time.sleep(self.refresh)
            elif status == "OFFLINE":
                self.log(f"{self.username} currently offline, checking again in {str(self.refresh)} seconds.")
                time.sleep(self.refresh)
            elif status == "TOKEN":
                self.log("TOKEN REFRESHED")
                time.sleep(2)
            elif status == "LIVE_BUT_FILTERED":
                self.log(f"{self.username} online but streams: {info[0]['title']}")
                time.sleep(self.refresh)
            elif status == "LIVE":
                self.log(f"{self.username} online. Stream recording in session.")
                filename = f"""{self.username} - {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")} - {(info[0]['title'] or 'Stream')}.mp4"""

                # clean filename
                filename = "".join(
                    x for x in filename
                    if x.isalnum() or x in [" ", "-", "_", ".", ":"])

                recorded_filename = os.path.join(self.recorded_path, filename)

                # start youtube-dl process (blocking process)
                try:
                    self.log('YOUTUBEDL DOWNLOADS')
                    ydl_opts = {
                        'outtmpl': recorded_filename,
                        'progress_hooks': [self.ytdl_callback],
                        'quiet': True
                    }
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"https://twitch.tv/{self.username}"])

                    self.log(
                        "Recording is done. Going back to checking while uploading."
                    )
                except Exception as e:
                    self.log(f"DEBUG {str(e)}")
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
        self.log(f"UPLOADING FILE: {filepath}")
        args = YT.DEFAULT_ARGS
        args.file = filepath
        args.title = (title[:97] + '...') if len(title) > 100 else title # Titles can have max 100 characters
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

    def refresh_token(self):
        url = f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials"
        info = None
        try:
            r = requests.post(url, timeout=15)
            print(r.json())
            self.access_token = r.json()["access_token"]
        except Exception as e:
            self.log(f"TOKEN REFRESH ERROR{e}")

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
        twitch_archiver.username, _, twitch_archiver.keyword = username.partition(':')
        if (os.getenv('DELETE_MEDIA_ON_ERROR', '').lower() == 'true'):
            twitch_archiver.delete_media_on_error = True
        thread = threading.Thread(target=twitch_archiver.run)
        thread.start()
        # thread.join()
        thread_list.append(thread)


if __name__ == "__main__":
    main(sys.argv[1:])
