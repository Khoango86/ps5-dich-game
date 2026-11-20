"""Dịch Anh -> Việt.

Thứ tự thử:
1. Google Translate (qua deep-translator, không cần API key).
2. MyMemory (API trực tiếp, không cần key; nếu có email thì hạn mức
   50.000 ký tự/ngày thay vì 5.000 ký tự/ngày ẩn danh).

Kết quả được cache để tránh dịch lại cùng một câu. Mọi lỗi mạng đều được
bắt và trả về "" để pipeline có thể thử lại sau.
"""

from collections import OrderedDict

import requests
from deep_translator import GoogleTranslator

MYMEMORY_URL = "https://api.mymemory.translated.net/get"


class Translator:
    """Dịch EN->VI có cache, tự đổi sang dịch vụ dự phòng khi cần."""

    def __init__(self, cache_size=500, mymemory_email=None):
        self._cache = OrderedDict()
        self._cache_size = cache_size
        self._mymemory_email = mymemory_email
        self._google = GoogleTranslator(source="en", target="vi")

    @property
    def cache_size(self):
        return len(self._cache)

    def _translate_google(self, text):
        try:
            return self._google.translate(text) or ""
        except Exception:
            return ""

    def _translate_mymemory(self, text):
        """Gọi trực tiếp API MyMemory (deep-translator không hỗ trợ tham
        số email để tăng hạn mức)."""
        try:
            params = {"q": text, "langpair": "en|vi"}
            if self._mymemory_email:
                params["de"] = self._mymemory_email
            resp = requests.get(MYMEMORY_URL, params=params, timeout=10)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            translated = (data.get("responseData") or {}).get("translatedText") or ""
            # MyMemory trả cảnh báo hết hạn mức NGAY TRONG translatedText
            # nên phải lọc ra, nếu không app sẽ hiện cảnh báo như bản dịch.
            if "MYMEMORY WARNING" in translated or "QUERY LENGTH LIMIT" in translated:
                return ""
            return translated
        except Exception:
            return ""

    def translate(self, text):
        """Dịch một đoạn text sang tiếng Việt. Trả về "" nếu dịch thất bại."""
        text = (text or "").strip()
        if not text:
            return ""
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]

        result = self._translate_google(text)
        if not result.strip():
            result = self._translate_mymemory(text)
        result = result.strip()
        if result:
            self._cache[text] = result
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return result
