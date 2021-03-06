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
        self.redis_endpoint = None
        self.token_db = None
        self.cache_dir = None
        self.player_location = None
        self.stream_location = None
        self.web_location = None
        self.domain = None

        self.providers_config = None
        self.authenticators_config = None

        self.load_config()
        # TODO
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    def load_config(self):
        with self.config_file.open('r') as f:
            self.config = json.load(f)

        self.player_socket = self.config.get('player_socket') or '/tmp/aria/player.sock'
        self.stream_socket = self.config.get('stream_socket') or '/tmp/aria/stream.sock'
        self.db_endpoint = self.config.get('db_endpoint') or 'http://database:8080'
        self.redis_endpoint = self.config.get('redis_endpoint') or 'redis://core-redis'
        self.token_db = self.config.get('token_db') or 'sqlite://config/token.sqlite3'
        self.cache_dir = self.config.get('cache_dir') or 'caches'
        self.player_location = self.config.get('player_location') or 'https://aria.sarisia.cc'
        self.stream_location = self.config.get('stream_location') or 'https://aria.sarisia.cc/stream/'
        self.web_location = self.config.get('web_locaiton') or 'https://gaiji.pro'
        self.domain = self.config.get('domain') or 'gaiji.pro'

        self.providers_config = self.config.get('providers_config') or {}
        self.authenticators_config = self.config.get('authenticators_config') or {}
