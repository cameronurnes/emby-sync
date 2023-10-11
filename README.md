# emby-sync

Running the server in docker:

`docker run --name emby-sync -e EMBY_SERVER='<emby_url>' -e SECRET_KEY='<emby_api_key>' -p 5000:5000 lastelement21/emby-sync:latest`


Runs on port 5000 in the container, publish to whatever you want


Requires several ENV variables to be passed to the container:

SECRET_KEY: This should be an API key for your emby server.

EMBY_SERVER: This should be the URL used to connect to your server.

(Optional) DEFAULT_ROOM: A room name which always exists. Default is 'Bacon Bar'

(Optional) INTERVAL: The interval of the synchronization loop, in seconds. Default '3.0' seconds.
Setting this shorter will yield a higher load on the Emby server, but on a low latency connection can give very good synchronization results.

(Optional) BUFFER: Set to add some buffer time if some of your clients have slower connections.  10000000 = 1s.  Default = 0

(Optional) SYNC_LIMIT: How far to allow clients to drift apart.  Not this is not meant to provide perfect sync and some time is required here. Default: 8s

Known Issue: Chromecasts cannot follow, but can lead.  Workaround by controlling the device casting to the Chromecast.

Known Issue: Currently playing display only works for movies

# Development
API reference:
[http://swagger.emby.media/?staticview=true#/SessionsService/](http://swagger.emby.media/?staticview=true#/SessionsService/)

## Start Development Server
```
python dev_start.py
```
For the dev server, the host and port can be defined by using environment variables:  
```
export HOST="0.0.0.0"
export PORT="5000"
python dev_start.py
```
