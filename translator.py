import os
import sys
import json

class Translator:
    def __init__(self, lang_code="en"):
        self.lang_code = lang_code
        self.translations = {}
        self.load_translations()

    def load_translations(self):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)

        lang_file = os.path.join(base_path, "lang", f"{self.lang_code}.json")

        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Translation file not found: {lang_file}")

    # def load_translations(self):
    #     lang_file = os.path.join("lang", f"{self.lang_code}.json")
    #     try:
    #         with open(lang_file, "r", encoding="utf-8") as f:
    #             self.translations = json.load(f)
    #     except FileNotFoundError:
    #         raise FileNotFoundError(f"Translation file not found: {lang_file}")

    def tr(self, key: str) -> str:
        return self.translations.get(key, key)