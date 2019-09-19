from pathlib import Path

from gmusicapi.clients import Mobileclient


auth_dir = Path.cwd()/'config'/'gpm'
auth_dir.mkdir(parents=True,exist_ok=True)

name = input("Enter name: ")
# sanitize
name = Path(name).name

auth_file = auth_dir/f"{name}.auth"
auth_file.touch()

try:
    Mobileclient.perform_oauth(storage_filepath=str(auth_file), open_browser=True)
    print('Logged in to Google successfully!')
except:
    print('Failed to login. Try again later...')
