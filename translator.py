import json
import os

class Translator:
    def __init__(self, lang_code="en"):
        self.translations = {}
        self.lang_code = lang_code
        self.load_translations()

    def load_translations(self):
        lang_file = os.path.join("lang", f"{self.lang_code}.json")
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Translation file not found: {lang_file}")

    def tr(self, key: str) -> str:
        return self.translations.get(key, key)