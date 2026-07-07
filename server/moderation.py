"""
moderation.py
-------------
Keyword and heuristic-based content filtering for doubt submissions.
No ML/NLP — purely rule-based, suitable for LAN classroom use.
"""

import json
import os
import re
import threading
from typing import Optional

BANNED_WORDS_FILE = os.path.join(os.path.dirname(__file__), "data", "banned_words.json")
_lock = threading.Lock()


def _ensure_store():
    os.makedirs(os.path.dirname(BANNED_WORDS_FILE), exist_ok=True)
    if not os.path.exists(BANNED_WORDS_FILE):
        default_banned = [
            "fuck", "shit", "ass", "bitch", "damn", "crap", "dick",
            "bastard", "piss", "slut", "whore", "cunt",
        ]
        with open(BANNED_WORDS_FILE, "w") as f:
            json.dump(default_banned, f, indent=2)


def _load_banned() -> list:
    _ensure_store()
    with _lock:
        with open(BANNED_WORDS_FILE, "r") as f:
            return json.load(f)


MIN_DOUBT_LENGTH = 5
MAX_CONSECUTIVE_UPPER = 8
MAX_REPEAT_CHAR = 8


def _check_profanity(text: str, banned_words: list) -> Optional[str]:
    lower = text.lower()
    for word in banned_words:
        # Match standard word
        if re.search(r'\b' + re.escape(word) + r'\b', lower):
            return f"profanity: '{word}'"
        
        # Match obfuscated word with separators like spaces, hyphens, asterisks, dots
        # e.g., f-u-c-k, f*u*c*k, f u c k
        if len(word) > 2:
            pattern = r'\b' + r'[\s\.\-_*]?'.join(re.escape(c) for c in word) + r'\b'
            if re.search(pattern, lower):
                return f"profanity: '{word}'"
    return None


def _check_spam_heuristics(text: str) -> Optional[str]:
    if len(text) < MIN_DOUBT_LENGTH:
        return "too_short"

    upper_count = sum(1 for c in text if c.isupper())
    if len(text) > 0 and upper_count / len(text) > 0.7 and len(text) > 15:
        return "excessive_caps"

    for i in range(len(text) - MAX_REPEAT_CHAR + 1):
        segment = text[i:i + MAX_REPEAT_CHAR]
        if len(set(segment)) == 1 and segment[0] not in " .,!?":
            return "repeated_characters"

    return None


def _check_duplicate(text: str, username: str, existing_doubts: list) -> Optional[str]:
    for doubt in existing_doubts:
        if doubt.get("username") == username and doubt.get("text") == text:
            return "duplicate"
    return None


def check_doubt(text: str, username: str, existing_doubts: list = None) -> dict:
    """
    Run all moderation checks on a doubt.
    Returns: { "flagged": bool, "flag": Optional[str] }
    """
    banned_words = _load_banned()

    profanity_flag = _check_profanity(text, banned_words)
    if profanity_flag:
        return {"flagged": True, "flag": profanity_flag}

    spam_flag = _check_spam_heuristics(text)
    if spam_flag:
        return {"flagged": True, "flag": spam_flag}

    if existing_doubts is not None:
        dup_flag = _check_duplicate(text, username, existing_doubts)
        if dup_flag:
            return {"flagged": True, "flag": dup_flag}

    return {"flagged": False, "flag": None}
