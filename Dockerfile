FROM python:3.6-buster

RUN apt-get update \
    && apt-get install -y \
    libopus0 \
    ffmpeg

COPY . /usr/src/aria-core
WORKDIR /usr/src/aria-core
RUN pip install -r requirements.txt

VOLUME ./config ./caches

CMD [ "python", "run.py" ]
