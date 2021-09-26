# emby-sync


`docker run --name emby-sync -e EMBY_SERVER='<emby_url>' -e SECRET_KEY='<emby_api_key>' -p 5000:5000 lastelement21/emby-sync:latest`


Runs on port 5000 in the container, publish to whatever you want


Requires several ENV variables to be passed to the container:

SECRET_KEY: This should be an API key for your emby server.

EMBY_SERVER: This should be the URL used to connect to your server.

(Optional) DEFAULT_ROOM: A room name which always exists. Default is 'Bacon Bar'

Known Issue: Chromecasts cannot follow, but can lead.  Workaround by controlling the device casting to the Chromecast.

# Development
API reference:
[http://swagger.emby.media/?staticview=true#/SessionsService/](http://swagger.emby.media/?staticview=true#/SessionsService/)