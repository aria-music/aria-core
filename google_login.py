from gmusicapi.clients import Mobileclient
from pathlib import Path

config_dir = Path.cwd()/'config'
auth_file = config_dir/'google.auth'

config_dir.mkdir(exist_ok=True)
auth_file.touch()
try:
    Mobileclient.perform_oauth(storage_filepath=str(auth_file), open_browser=True)
    print('Logged in to Google successfully!')
except:
    print('Failed to login. Try again later...')
