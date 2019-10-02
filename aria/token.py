import json
from logging import getLogger
from pathlib import Path

from aria.utils import generate_key

log = getLogger(__name__)


class Token():
    def __init__(self, token_file=None):
        self.file_path = token_file or "config/token.json"
        self.file = Path(self.file_path)
        self.tokens = set()

        self.load()

    def load(self):
        if not self.file.exists():
            log.info("tokens.json not found. Creating...")
            self.save()

        parsed = {}
        try:
            with self.file.open('r') as f:
                parsed = json.load(f)
        except:
            log.error("Failed to load token.json: ", exc_info=True)
        
        if "tokens" not in parsed:
            log.error("Invalid token.json.")
            return

        self.tokens = set(parsed["tokens"])

    def save(self):
        # called from other thread
        try:
            with self.file.open('w') as f:
                json.dump({ "tokens": list(self.tokens) }, f, ensure_ascii=False, indent=4)
        except:
            log.error("Failed to save tokens.json: ", exc_info=True)

    def is_valid(self, token:str) -> bool:
        return token in self.tokens

    def generate(self) -> str:
        generated = generate_key()
        while generated in self.tokens:
            generated = generate_key()

        self.tokens.add(generated)
        self.save()
        return generated

    def revoke(self, token:str):
        try:
            self.tokens.remove(token)
        except:
            log.error("Token not found in tokens")
            