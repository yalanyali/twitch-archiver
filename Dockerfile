FROM python:3

RUN apt-get update && apt-get install ffmpeg -y

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

COPY . .

RUN pip install -r requirements.txt

CMD [ "python", "-u", "twitch_archiver.py" ]