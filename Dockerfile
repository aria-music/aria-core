FROM python:3.8-buster

RUN apt-get update \
    && apt-get install -y \
    libopus0 \
    ffmpeg

COPY ./requirements.txt /usr/src/aria-core/requirements.txt
WORKDIR /usr/src/aria-core
RUN pip install -r requirements.txt

COPY . /usr/src/aria-core

CMD [ "python", "run.py" ]
