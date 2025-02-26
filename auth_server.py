from datetime import datetime, timedelta
import multiprocessing, subprocess
import os
from pathlib import Path
import signal
import threading
import time
import logging
import webbrowser

import requests, urllib, base64, json
from flask import Flask, redirect, request, jsonify
from werkzeug.serving import make_server

from kozubenko.env import Env
from kozubenko.timer import Timer
from kozubenko.utils import Utils


def worker():
    app = Flask(__name__)

    @app.route('/')
    def home():
        return '<div><a href="http://127.0.0.1:8080/login">LOGIN</a></div>'

    @app.route('/login')
    def login():
        Env.load()

        return 'LOGIN'

        params = {
            'response_type': 'code',
            'client_id': Env.vars['client_id'],
            'scope': Env.vars['scope'],
            'redirect_uri': Env.vars['redirect_uri'],
            'state': Utils.get_randomized_string(16)
        }

        print('redirecting...')
        
        return redirect('https://accounts.spotify.com/authorize?' + urllib.parse.urlencode(params))

    @app.route('/callback')
    def callback():
        Env.load()

        return 'CALLBACK'

        code = request.args.get('code', None)
        state = request.args.get('state', None)

        if not state:
            return redirect('/#' + urllib.parse.urlencode({'error': 'state_mismatch'}))
        
        token_url = 'https://accounts.spotify.com/api/token'

        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + base64.b64encode(f'{Env.vars['client_id']}:{Env.vars['client_secret']}'.encode()).decode('utf-8')
        }

        data = {
            'code': code,
            'redirect_uri': Env.vars['redirect_uri'],
            'grant_type': 'authorization_code'
        }

        response = requests.post(token_url, headers=headers, data=data, json=True)
        timestamp = response.headers['date']

        if response.status_code == 200:
            token_info = response.json()

            env_dir = r'.\.env'
            Path(env_dir).mkdir(parents=True, exist_ok=True)

            with open(fr'{env_dir}\spotify_auth_token.json', 'w') as json_file:
                json.dump(token_info, json_file)
            
            with open(fr'{env_dir}\spotify_auth_token_readable.json', 'w') as json_file:
                json.dump(token_info, json_file, indent=4)

            Env.save('access_token', token_info['access_token'])
            Env.save('refresh_token', token_info['refresh_token'])
            token_expiration = datetime.now() + timedelta(seconds=int(token_info['expires_in']))
            Env.save('token_expiration', token_expiration.strftime('%Y-%m-%d %H:%M'))

            return jsonify(token_info)
        else:
            print(f'/CallBack endpoint hit. response.status_code == {response.status_code}')
            return jsonify({'error': 'Failed to get token'}), response.status_code
        
    server = make_server('127.0.0.1', 8080, app)
    ctx = app.app_context()
    ctx.push()

    server.serve_forever()

def start_local_http_server():
    global server_process

    server_process = multiprocessing.Process(target=worker, name="LocalServerProcess")
    server_process.start()
    # print('Started LocalServerProcess, serving: http://127.0.0.1:8080')

def stop_local_http_server():
    server_process.terminate()

# Requires 'if __name__ == '__main__':' guard clause from called
def validate_token(reject=False):
    Env.load()
    token_expiration_str = Env.vars.get('token_expiration', None)
    
    if token_expiration_str is None or reject is True:
        request_token()
        return

    expiration = datetime.strptime(token_expiration_str, '%Y-%m-%d %H:%M')
    now = datetime.now()
    
    if now > expiration - timedelta(minutes=3):
        refresh_token()

def request_token():
    start_local_http_server()

    print('You need a Spotify Authorization Code to use this program. Please get one by logging in at: http://127.0.0.1:8080')
    input('When redirected to success page, Press Enter to continue...')

    stop_local_http_server()

def refresh_token():
    Env.load()
    refresh_token = Env.vars.get('refresh_token', None)
    url = 'https://accounts.spotify.com/api/token'

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + base64.b64encode(f'{Env.vars['client_id']}:{Env.vars['client_secret']}'.encode()).decode('utf-8')
    }

    body = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    response = requests.post(url, headers=headers, data=body)

    if response.status_code == 200:
        response_data = response.json()
        Env.save('access_token', response_data['access_token'])
        token_expiration = datetime.now() + timedelta(seconds=int(response_data['expires_in']))
        Env.save('token_expiration', token_expiration.strftime('%Y-%m-%d %H:%M'))
        if 'refresh_token' in response_data:
            Env.save('refresh_token', response_data['refresh_token'])
    else:
        RuntimeError(f'refresh_token() not implemented for response.status_code == {response.status_code}.')
