from typing import Dict
from core.interfaces import TranslatorProtocol
from translations.en import translations as en_translations
from translations.ru import translations as ru_translations

TRANSLATIONS: Dict[str, Dict] = {
    "en": en_translations,
    "ru": ru_translations,
}

class DictTranslator(TranslatorProtocol):
    def __init__(self, lang_code: str = "en"):
        self.lang_code = lang_code
        self.translations = TRANSLATIONS.get(lang_code, TRANSLATIONS["en"])

    def tr(self, key: str) -> str:
        return self.translations.get(key, key)