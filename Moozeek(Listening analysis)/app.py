import json
import requests
import extract
import features
import model
import os
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import pickle
import numpy as np
from flask import Flask, request, redirect, g, render_template, Response, make_response
from flask_caching import Cache
from urllib.parse import quote
from math import pi

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# API Keys
client_id = "d42e92315e534b1797c66eecee8b4699"
client_secret = "1348bf0ad1614c0eb8ecfcecd66ba846"

# API URLs
auth_url = "https://accounts.spotify.com/authorize"
token_url = "https://accounts.spotify.com/api/token"
base_url = "https://api.spotify.com/v1"

# Redirect uri and authorization scopes
# redirect_uri = "https://myspotifydata.azurewebsites.net/home"
scope = "user-top-read user-read-recently-played playlist-read-collaborative playlist-read-private"

# UNCOMMENT TO USE FOR LOCAL TESTING
redirect_uri = "http://127.0.0.1:5000/home"

# Image folder configuration
app.config['UPLOAD_FOLDER'] = "/static/"

# Query parameters for authorization
auth_query = {
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "scope": scope,
    "show_dialog": "false",
    "client_id": client_id
}


# Returns a token needed to access the Spotify API
def generate_access_token():
    # Requests refresh and access tokens (POST)
    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
    }
    post_request = requests.post(token_url, data=code_payload)

    # Tokens returned to application
    response_data = json.loads(post_request.text)
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]
    return access_token


# GET a user's top artists
def get_top_artist_data(auth_header, time_range, limit):
    endpoint = "{}/me/top/artists?time_range={}&limit={}".format(base_url, time_range, limit)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    top_artist_data = extract.top_artists(data)
    return top_artist_data


# GET a user's top tracks
def get_top_tracks_data(auth_header, time_range, limit):
    endpoint = "{}/me/top/tracks?time_range={}&limit={}".format(base_url, time_range, limit)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    top_tracks_data = extract.top_tracks(data)
    return top_tracks_data


# GET a user's top tracks grouped by their top artists
def get_top_tracks_by_artist(auth_header):
    top_tracks = get_top_tracks_data(auth_header, 'long_term', '50')
    top_artists = get_top_artist_data(auth_header, 'long_term', '10')
    result = extract.top_tracks_by_artist(top_tracks, top_artists)
    return result


# GET a user's recent listening history
def get_recent_tracks_data(auth_header, limit):
    endpoint = "{}/me/player/recently-played?type=track&limit={}".format(base_url, limit)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    recent_tracks_data = extract.recent_tracks(data)
    return recent_tracks_data


# GET the track ids from the user's recent listening history
def get_recent_tracks_ids(auth_header, limit):
    endpoint = "{}/me/player/recently-played?type=track&limit={}".format(base_url, limit)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    recent_track_ids = extract.recent_track_ids(data)
    result = ','.join(recent_track_ids)
    return result


# GET the track ids for the user's top tracks
def get_top_tracks_ids(auth_header, time_range, limit):
    endpoint = "{}/me/top/tracks?time_range={}&limit={}".format(base_url, time_range, limit)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    top_tracks_id = extract.top_track_ids(data)
    result = ','.join(top_tracks_id)
    return result


# GET the artwork of tracks
def get_track_images(auth_header, track_ids):
    endpoint = "{}/tracks?ids={}".format(base_url, track_ids)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    track_images = extract.track_images(data)
    return track_images


# GET the images of artists
def get_artist_images(auth_header, artist_ids):
    endpoint = "{}/artists?ids={}".format(base_url, artist_ids)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    artist_images = extract.artist_images(data)
    return artist_images


# GET the image urls of the top tracks
def get_top_track_images(auth_header, tracks):
    lst = []
    for item in tracks:
        track_id = item[1]
        lst.append(track_id)
    track_ids = ','.join(lst)
    images = get_track_images(auth_header, track_ids)
    return images


# GET the image urls of the top artists
def get_top_artist_images(auth_header, artists):
    lst = []
    for item in artists:
        artist_id = item[1]
        lst.append(artist_id)
    artist_ids = ','.join(lst)
    images = get_artist_images(auth_header, artist_ids)
    return images


# GET the tracks from a playlist
def get_tracks_from_playlist(auth_header, list_id, person_type):
    endpoint = "{}/playlists/{}/tracks".format(base_url, list_id)
    response = requests.get(endpoint, headers=auth_header)
    data = json.loads(response.text)
    datapoints = get_dataframe(auth_header, data, person_type)
    return datapoints


# Function that can be called by a route based on term length
def display_top_tracks(term_length):
    # Get the access token from its cookie and use it to access data
    access_token = request.cookies.get('token')
    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    top_tracks_data = get_top_tracks_data(auth_header, term_length, '30')
    images = get_top_track_images(auth_header, top_tracks_data)
    return (top_tracks_data, images)


# Function that can be called by a route based on term length
def display_top_artists(term_length):
    # Get the access token from its cookie and use it to access data
    access_token = request.cookies.get('token')
    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    top_artist_data = get_top_artist_data(auth_header, term_length, '30')
    images = get_top_artist_images(auth_header, top_artist_data)
    return (top_artist_data, images)


# Function that can be called by a route based on term length
def display_top_tracks_by_artist(term_length):
    # Get the access token from its cookie and use it to access data
    access_token = request.cookies.get('token')
    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    data = get_top_tracks_by_artist(auth_header)
    lst = []
    for item in data:
        lst.append(item)
    images = get_top_artist_images(auth_header, lst)
    return (data, images)


# Initial route for user authentication with Spotify
@app.route("/")
def index():
    # Redirects the user to the Spotify login page (first thing that happens upon app launch)
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query.items()])
    authorization = "{}/?{}".format(auth_url, url_args)
    response = make_response(redirect(authorization))
    response.set_cookie('token', 'deletion', max_age=0)
    return response


# Homepage of application
@app.route("/home")
def display_top_data():
    with app.app_context():
        cache.clear()
    # Get an access token from its cookie or generate one if it doesn't exist yet
    access_token = request.cookies.get('token')
    if access_token == None:
        access_token = generate_access_token()

    # Use the token to get the necessary authorization header and then obtain data
    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    recent_tracks_data = get_recent_tracks_data(auth_header, '50')
    recent_track_ids = get_recent_tracks_ids(auth_header, '50')
    track_images = get_track_images(auth_header, recent_track_ids)

    # Store HTML rendering in a response and create a cookie for the access token
    response = make_response(
        render_template("index.html", recent=recent_tracks_data, images=track_images[0], links=track_images[1]))
    response.set_cookie('token', access_token, max_age=3600)
    return response


# Page for viewing top tracks in the past 1 month
@app.route("/top-tracks-short-term")
def display_top_tracks_short_term():
    data = display_top_tracks('short_term')
    return render_template("toptracks.html", top_tracks=data[0], images=data[1][0], short_link_status="active",
                           med_link_status="", long_link_status="", links=data[1][1])


# Page for viewing top tracks in the past 6 months
@app.route("/top-tracks-medium-term")
def display_top_tracks_medium_term():
    data = display_top_tracks('medium_term')
    return render_template("toptracks.html", top_tracks=data[0], images=data[1][0], short_link_status="",
                           med_link_status="active", long_link_status="", links=data[1][1])


# Page for viewing all time top tracks
@app.route("/top-tracks-long-term")
def display_top_tracks_long_term():
    data = display_top_tracks('long_term')
    return render_template("toptracks.html", top_tracks=data[0], images=data[1][0], short_link_status="",
                           med_link_status="", long_link_status="active", links=data[1][1])


# Page for viewing top artists in the past month
@app.route("/top-artists-short-term")
def display_top_artists_short_term():
    data = display_top_artists('short_term')
    return render_template("topartists.html", top_artists=data[0], images=data[1][0], short_link_status="active",
                           med_link_status="", long_link_status="", links=data[1][1])


# Page for viewing top artists in the past 6 months
@app.route("/top-artists-medium-term")
def display_top_artists_medium_term():
    data = display_top_artists('medium_term')
    return render_template("topartists.html", top_artists=data[0], images=data[1][0], short_link_status="",
                           med_link_status="active", long_link_status="", links=data[1][1])


# Page for viewing all time top artists
@app.route("/top-artists-long-term")
def display_top_artists_long_term():
    data = display_top_artists('long_term')
    return render_template("topartists.html", top_artists=data[0], images=data[1][0], short_link_status="",
                           med_link_status="", long_link_status="active", links=data[1][1])


# Page for viewing top tracks grouped by artist
@app.route("/top-tracks-by-artist")
def display_top_tracks_by_artist_short_term():
    data = display_top_tracks_by_artist('short_term')
    return render_template("toptracksbyartist.html", content=data[0], images=data[1][0], links=data[1][1])


# Page for Recommendation Engine
@app.route("/recommend/")
def recommend():
    # render the recommendation page
    return render_template('Recommendation.html')


@app.route("/recommend/result", methods=['POST'])
def result():
    # requesting the URL form the HTML form

    songDF = pd.read_csv("./data/allsong_data.csv")
    complete_feature_set = pd.read_csv("./data/complete_feature.csv")

    URL = request.form['URL']
    # using the extract function to get a features dataframe
    df = features.extract(URL)
    # retrieve the results and get as many recommendations as the user requested
    edm_top40 = model.recommend_from_playlist(songDF, complete_feature_set, df)
    number_of_recs = int(request.form['number-of-recs'])
    my_songs = []
    for i in range(number_of_recs):
        my_songs.append([str(edm_top40.iloc[i, 1]) + ' - ' + '"' + str(edm_top40.iloc[i, 4]) + '"',
                         "https://open.spotify.com/track/" + str(edm_top40.iloc[i, -6]).split("/")[-1]])
    return render_template('results.html', songs=my_songs)


# Logs the user out of the application
@app.route("/logout")
def logout():
    return redirect("https://www.spotify.com/logout/")


# This is done in order to prevent the browser from caching images
@app.after_request
def disable_cache(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate public, max-age=0"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r


# # Run the server (uncomment for local testing)
if __name__ == "__main__":
    app.run(debug=True)
