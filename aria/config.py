from pathlib import Path
import json

class Config():
    def __init__(self, config_file=None):
        self.config_file_path = config_file or "config/config.json"
        self.config_file = Path(self.config_file_path)
        self.config = None

        self.player_socket = None
        self.stream_socket = None
        self.db_endpoint = None
        self.cache_dir = None
        self.providers_config = None

        self.load_config()

    def load_config(self):
        with self.config_file.open('r') as f:
            self.config = json.load(f)

        self.player_socket = self.config.get('player_socket') or '/tmp/aria/player.sock'
        self.stream_socket = self.config.get('stream_socket') or '/tmp/aria/stream.sock'
        self.db_endpoint = self.config.get('db_endpoint') or 'http://dbapp:8080'
        self.cache_dir = self.config.get('cache_dir') or 'caches'
        self.providers_config = self.config.get('providers_config') or {}
