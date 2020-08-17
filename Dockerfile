FROM python:3.6-alpine

RUN adduser -D emby-sync

WORKDIR /home/emby-sync

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn

COPY app app
COPY migrations migrations
COPY emby-sync.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP emby-sync.py

RUN chown -R emby-sync:emby-sync ./
USER emby-sync

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
