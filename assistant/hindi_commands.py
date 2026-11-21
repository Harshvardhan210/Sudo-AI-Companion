"""
Understands Hindi and Hinglish commands (Roman letters or Devanagari) by turning
them into the English commands the assistant already knows.

    "volume ko kam kar do"          -> "volume down"
    "notepad kholo"                 -> "open notepad"
    "नोटपैड खोलो"                    -> "open notepad"
    "chrome band karo"              -> "close chrome"
    "5 minute baad yaad dilao"      -> "remind me in 5 minutes"
    "work routine shuru karo"       -> "run work routine"
    "aaj ki date kya hai"           -> "what is today's date"

Plain English commands are never changed (to_english() returns None for them),
so "search python" still searches your files.
"""

import re


# ----------------------------------------------------------------------------
# Devanagari -> Roman
# ----------------------------------------------------------------------------

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Several Devanagari words that mean one thing (checked before single words)
DEVANAGARI_PHRASES = [
    ("यू ट्यूब", "youtube"), ("यूट्यूब", "youtube"), ("वी एस कोड", "vs code"),
    ("वीएस कोड", "vs code"), ("विजुअल स्टूडियो कोड", "vs code"),
    ("गूगल क्रोम", "chrome"), ("हो गया", "hogaya"), ("हो गई", "hogaya"),
    ("हो गयी", "hogaya"), ("स्टैक ओवरफ्लो", "stack overflow"),
    ("व्हाट्सएप वेब", "whatsapp web"), ("माइक्रोसॉफ्ट एज", "edge"),
]

DEVANAGARI_WORDS = {
    # actions
    "खोलो": "kholo", "खोल": "khol", "खोलिए": "kholiye", "खोलना": "kholna", "ओपन": "open",
    "बंद": "band", "बन्द": "band", "क्लोज": "close", "करो": "karo", "कर": "kar",
    "करें": "kare", "करना": "karna", "कीजिए": "kijiye", "कीजिये": "kijiye",
    "दो": "do", "दे": "de", "दीजिए": "dijiye", "चालू": "chalu", "चलाओ": "chalao",
    "चला": "chala", "शुरू": "shuru", "बजाओ": "bajao", "सुनाओ": "sunao",
    "सर्च": "search", "खोजो": "khojo", "ढूंढो": "dhundo", "ढूँढो": "dhundo",
    "जोड़ो": "jodo", "जोड़": "jod", "लिखो": "likho", "लिखना": "likhna",
    "दिखाओ": "dikhao", "दिखा": "dikha", "बताओ": "batao", "बता": "bata",
    "बनाओ": "banao", "बना": "bana", "नया": "naya", "नई": "nayi", "सेव": "save",
    "हटाओ": "hatao", "मिटाओ": "mitao", "डिलीट": "delete", "पूरा": "pura",
    "बदलो": "badlo", "बोलो": "bolo", "सुनो": "suno",
    # volume / sound
    "वॉल्यूम": "volume", "वोल्यूम": "volume", "आवाज़": "awaaz", "आवाज": "awaaz",
    "साउंड": "sound", "म्यूट": "mute", "अनम्यूट": "unmute", "चुप": "chup",
    "कम": "kam", "घटाओ": "ghatao", "धीरे": "dheere", "बढ़ाओ": "badhao",
    "बढाओ": "badhao", "बढ़ा": "badha", "ज़्यादा": "zyada", "ज्यादा": "zyada",
    "तेज़": "tez", "तेज": "tez",
    # things
    "नोट": "note", "नोट्स": "notes", "टास्क": "task", "टास्क्स": "tasks",
    "काम": "kaam", "रूटीन": "routine", "रिमाइंडर": "reminder", "याद": "yaad",
    "दिलाओ": "dilao", "दिलाना": "dilana", "अलार्म": "alarm",
    "मिनट": "minute", "घंटा": "ghanta", "घंटे": "ghante", "सेकंड": "second",
    "सेकेंड": "second", "बाद": "baad", "आधा": "aadha", "डेढ़": "dedh", "ढाई": "dhai",
    "बजे": "baje", "समय": "samay", "टाइम": "time", "तारीख": "tarikh",
    "तारीख़": "tarikh", "तिथि": "tithi", "आज": "aaj", "बैटरी": "battery",
    "लॉक": "lock", "रीस्टार्ट": "restart", "शटडाउन": "shutdown",
    "कंप्यूटर": "computer", "कम्प्यूटर": "computer", "लैपटॉप": "laptop",
    "नमस्ते": "namaste", "नमस्कार": "namaskar", "मदद": "madad",
    "गाना": "gaana", "गाने": "gaane", "गीत": "geet", "वीडियो": "video",
    # small words
    "में": "mein", "पर": "par", "पे": "pe", "को": "ko", "का": "ka", "की": "ki",
    "के": "ke", "से": "se", "लिए": "liye", "मुझे": "mujhe", "क्या": "kya",
    "कितने": "kitne", "कितना": "kitna", "है": "hai", "हैं": "hain", "हो": "ho",
    "और": "aur", "अब": "ab", "जरा": "jara", "ज़रा": "zara", "प्लीज": "please",
    # numbers
    "एक": "ek", "तीन": "teen", "चार": "char", "पांच": "paanch", "पाँच": "paanch",
    "छह": "chhe", "छः": "chhe", "सात": "saat", "आठ": "aath", "नौ": "nau",
    "दस": "das", "ग्यारह": "gyarah", "बारह": "barah", "पंद्रह": "pandrah",
    "पन्द्रह": "pandrah", "बीस": "bees", "तीस": "tees", "चालीस": "chalis",
    "पचास": "pachaas", "साठ": "saath",
    # apps, sites, folders
    "नोटपैड": "notepad", "नोटपेड": "notepad", "क्रोम": "chrome", "गूगल": "google",
    "जीमेल": "gmail", "व्हाट्सएप": "whatsapp", "वॉट्सऐप": "whatsapp",
    "व्हाट्सऐप": "whatsapp", "कैलकुलेटर": "calculator", "कैल्कुलेटर": "calculator",
    "स्पॉटिफाई": "spotify", "डिस्कॉर्ड": "discord", "टेलीग्राम": "telegram",
    "एक्सेल": "excel", "वर्ड": "word", "पावरपॉइंट": "powerpoint", "पेंट": "paint",
    "फायरफॉक्स": "firefox", "एज": "edge", "गिटहब": "github", "लिंक्डइन": "linkedin",
    "इंस्टाग्राम": "instagram", "फेसबुक": "facebook", "ट्विटर": "twitter",
    "अमेज़न": "amazon", "अमेजन": "amazon", "फ्लिपकार्ट": "flipkart",
    "नेटफ्लिक्स": "netflix", "नौकरी": "naukri", "विकिपीडिया": "wikipedia",
    "चैटजीपीटी": "chatgpt", "डेस्कटॉप": "desktop", "डाउनलोड्स": "downloads",
    "डाउनलोड": "downloads", "डॉक्यूमेंट्स": "documents", "पिक्चर्स": "pictures",
    "म्यूजिक": "music", "वीडियोज़": "videos", "कोड": "code", "वीएस": "vs",
}

_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh",
    "ज": "j", "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
    "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p",
    "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l",
    "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
_NUKTA_CONSONANTS = {"क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f"}
_VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
           "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o"}
_MATRAS = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "े": "e", "ै": "ai",
           "ो": "o", "ौ": "au", "ृ": "ri", "ॉ": "o", "ं": "n", "ँ": "n", "ः": "h"}
_VIRAMA = "्"
_NUKTA = "़"


def _romanize_token(token):
    """Rough Devanagari -> Roman spelling for words that are not in the dictionary."""

    out = []
    i = 0

    while i < len(token):
        ch = token[i]
        nxt = token[i + 1] if i + 1 < len(token) else ""

        if nxt == _NUKTA and ch + _NUKTA in _NUKTA_CONSONANTS:
            roman, step = _NUKTA_CONSONANTS[ch + _NUKTA], 2
        elif ch in _CONSONANTS:
            roman, step = _CONSONANTS[ch], 1
        elif ch in _VOWELS:
            out.append(_VOWELS[ch])
            i += 1
            continue
        elif ch in _MATRAS:
            out.append(_MATRAS[ch])
            i += 1
            continue
        else:
            out.append(ch)
            i += 1
            continue

        out.append(roman)
        i += step

        after = token[i] if i < len(token) else ""
        if after == _VIRAMA:
            i += 1                          # joined consonants: no vowel
        elif after in _MATRAS:
            pass                            # the vowel sign follows
        elif i < len(token):
            out.append("a")                 # inherent "a" inside a word
        # at the end of a word the inherent "a" is dropped

    return "".join(out)


def has_devanagari(text):
    return bool(_DEVANAGARI.search(text))


def _clean(text):
    """Lowercase, ASCII digits, punctuation removed (Devanagari letters kept)."""

    text = text.lower().translate(_DIGITS)
    text = re.sub(r"[\u0964\u0965]", " ", text)                      # danda marks
    text = re.sub(r"[^\w\s'\u0900-\u097F]", " ", text)
    return " ".join(text.split())


def romanize_text(text):
    """Spell Hindi text with English letters (used for routine names)."""

    tokens = _tokens(text)
    return " ".join(normal for normal, _ in tokens)


def _tokens(text):
    """
    Split text into (normal, display) pairs.
    normal  - Roman form used to match rules
    display - what to show/keep in names (Devanagari words that are not in the
              dictionary stay as they were said)
    """

    text = _clean(text)

    for phrase, roman in DEVANAGARI_PHRASES:
        text = text.replace(phrase, " " + roman + " ")

    text = re.sub(r"\bho gaya\b|\bho gayi\b|\bho gai\b|\bho gya\b", " hogaya ", text)

    pairs = []

    for word in text.split():
        if has_devanagari(word):
            if word in DEVANAGARI_WORDS:
                roman = DEVANAGARI_WORDS[word]
                pairs.append((roman, roman))
            else:
                pairs.append((_romanize_token(word), word))
        else:
            pairs.append((word, word))

    return pairs


# ----------------------------------------------------------------------------
# Word lists (Roman Hinglish spellings, including common variants)
# ----------------------------------------------------------------------------

HINDI_MARKERS = {
    "kar", "karo", "kariye", "kijiye", "kijie", "kare", "karna", "karein", "kardo",
    "krdo", "kro", "kholo", "khol", "kholiye", "kholna", "kholdo", "ko", "kam", "kum",
    "badhao", "badha", "badhaao", "dikhao", "dikha", "batao", "bata", "hatao", "mitao",
    "banao", "bana", "chalao", "chalu", "shuru", "likho", "jodo", "yaad", "awaaz",
    "awaz", "aawaz", "kya", "kitne", "kitna", "baje", "tez", "dheere", "bajao", "sunao",
    "dhundo", "dhoondo", "khojo", "mein", "liye", "mujhe", "aaj", "baad", "hogaya",
    "namaste", "namaskar", "madad", "gaana", "gana", "samay", "tarikh", "dilao",
    "dilana", "naya", "nayi", "bolo", "badlo", "hai", "chup", "pura", "poora",
}

OPEN_WORDS = {"khol", "kholo", "kholiye", "kholna", "kholdo", "kholen", "kholiyega", "khulo", "kholu", "open", "opan", "launch"}
CLOSE_WORDS = {"band", "bandh", "bund", "close", "quit"}
START_WORDS = {"chalu", "shuru", "start", "run", "chalao", "chala", "chalaiye", "begin"}
PLAY_WORDS = {"bajao", "baja", "bajana", "play", "sunao", "suna", "chalao", "chala"}
SEARCH_WORDS = {"search", "khojo", "khoj", "khojiye", "dhundo", "dhoondo", "dhundh", "dhundhiye", "find"}
ADD_WORDS = {"add", "jodo", "jod", "daalo", "dalo", "likho", "likh", "likhna", "likhiye", "create"}
SHOW_WORDS = {"dikhao", "dikha", "dikhaiye", "dikhana", "batao", "bata", "show", "dekho", "dekhna", "list"}
DELETE_WORDS = {"delete", "hatao", "hata", "hatana", "mita", "mitao", "remove"}
SAVE_WORDS = {"save", "sahej", "sahejo", "sejo"}
CREATE_WORDS = {"banao", "bana", "banana", "create", "naya", "nayi", "naye", "new"}
DONE_WORDS = {"hogaya", "complete", "completed", "done", "pura", "poora", "khatam", "finish", "finished"}

REMINDER_WORDS = {"reminder", "remind", "yaad", "yad", "dilao", "dilana", "dila", "alarm"}
ROUTINE_WORDS = {"routine", "routines", "rutin"}
NOTE_WORDS = {"note", "notes", "nots"}
TASK_WORDS = {"task", "tasks", "todo", "kaam", "kaams"}
VOLUME_WORDS = {"volume", "awaaz", "awaz", "aawaz", "avaaz", "sound", "vol"}

DOWN_WORDS = {"kam", "kum", "ghata", "ghatao", "dheere", "dheera", "dhire", "neeche", "down", "decrease", "low", "halka", "halki", "slow"}
UP_WORDS = {"badha", "badhao", "badhaao", "tez", "zyada", "jyada", "zyaada", "unchi", "up", "increase", "high", "loud", "jor"}
MUTE_WORDS = {"mute", "chup", "band", "silent", "khamosh", "off"}
UNMUTE_WORDS = {"unmute", "chalu", "on", "khol", "kholo"}

UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1, "sekand": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60, "mint": 60, "minat": 60,
    "ghanta": 3600, "ghante": 3600, "ghanta": 3600, "hour": 3600, "hours": 3600, "hr": 3600,
}
NUMBER_WORDS = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4,
    "four": 4, "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "che": 6, "chhah": 6,
    "six": 6, "saat": 7, "seven": 7, "aath": 8, "eight": 8, "nau": 9, "nine": 9,
    "das": 10, "ten": 10, "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14,
    "pandrah": 15, "solah": 16, "satrah": 17, "athaarah": 18, "unnis": 19, "bees": 20,
    "pachees": 25, "tees": 30, "chalis": 40, "paintalis": 45, "pachaas": 50,
    "pachas": 50, "saath": 60, "sath": 60,
}
_HALF_WORDS = {"aadha": 0.5, "adha": 0.5, "half": 0.5, "dedh": 1.5, "derh": 1.5, "dhai": 2.5, "dhaai": 2.5}

# Words that carry no meaning for a command
FILLERS = {
    "kar", "karo", "kariye", "kijiye", "kijie", "kare", "karna", "karein", "krdo", "kro",
    "kardo", "karen", "do", "de", "dijiye", "dijie", "dena", "diye", "please", "plz",
    "pls", "zara", "jara", "mujhe", "mere", "meri", "mera", "liye", "ke", "ko", "ki",
    "ka", "se", "par", "pe", "mein", "me", "mai", "main", "hai", "hain", "tha", "thi",
    "ho", "na", "toh", "to", "bhi", "zaroor", "ek", "ye", "yeh", "woh", "wo", "isko",
    "usko", "abhi", "jaldi", "yaar", "bhai", "wala", "wali", "wale", "kya", "kuch",
    "kuchh", "aap", "tum", "the", "a", "an", "ab", "aur", "namaste",
}

_NOISE_FOR_TARGET = {"app", "application", "folder", "website", "site", "window", "windows", "program", "software"}


def _clean_words(pairs, *remove_sets, extra=()):
    """Display words that are left after removing command words and fillers."""

    words = []
    for normal, display in pairs:
        if normal in FILLERS or normal in extra or normal in _NOISE_FOR_TARGET:
            continue
        if any(normal in s for s in remove_sets):
            continue
        words.append(display)
    return words


def _has(normals, words):
    return any(n in words for n in normals)


def _number_of(token):
    if token.isdigit():
        return int(token)
    return NUMBER_WORDS.get(token)


def _first_number(normals):
    for n in normals:
        value = _number_of(n)
        if value is not None:
            return value
    return None


# ----------------------------------------------------------------------------
# Time ("5 minute baad", "aadha ghanta", "ek ghante")
# ----------------------------------------------------------------------------

def _parse_duration(normals):
    """Returns (total seconds or None, set of word positions used)."""

    total = 0.0
    used = set()
    found = False

    for i, token in enumerate(normals):
        nxt = normals[i + 1] if i + 1 < len(normals) else ""

        if token in _HALF_WORDS and nxt in UNIT_SECONDS:
            total += _HALF_WORDS[token] * UNIT_SECONDS[nxt]
            used.update({i, i + 1})
            found = True
            continue

        if i in used:
            continue

        value = _number_of(token)
        if value is not None and nxt in UNIT_SECONDS:
            total += value * UNIT_SECONDS[nxt]
            used.update({i, i + 1})
            found = True

    return (int(total) if found else None), used


def _format_duration(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = []

    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return " ".join(parts)


# ----------------------------------------------------------------------------
# Rules
# ----------------------------------------------------------------------------

def _known_targets():
    """Names of apps and websites the assistant knows (to tell "chrome chalao" from "song chalao")."""

    names = set()

    try:
        from features.app_closer import APP_ALIASES
        names.update(APP_ALIASES)
    except Exception:
        pass

    try:
        from features.web_tools import KNOWN_SITES
        names.update(KNOWN_SITES)
    except Exception:
        pass

    return names


def _rule_volume(pairs, normals):
    if _has(normals, VOLUME_WORDS):
        if "unmute" in normals or (_has(normals, UNMUTE_WORDS) and not _has(normals, {"band", "mute"})):
            return "unmute volume"
        if _has(normals, MUTE_WORDS):
            return "mute volume"
        if _has(normals, DOWN_WORDS):
            return "volume down"
        if _has(normals, UP_WORDS):
            return "volume up"
        return None

    if "unmute" in normals:
        return "unmute volume"
    if "mute" in normals or "chup" in normals:
        return "mute volume"

    return None


def _rule_voice(pairs, normals):
    speaks = {"bolo", "bol", "bolna", "speak", "baat", "boliye"}

    if _has(normals, {"dheere", "dhire", "slow"}) and _has(normals, speaks):
        return "speak slower"

    if _has(normals, {"tez", "fast", "jaldi"}) and _has(normals, speaks):
        return "speak faster"

    if _has(normals, VOLUME_WORDS | {"voice"}) and _has(normals, {"badlo", "badal", "change", "badalna"}):
        return "change voice"

    return None


def _rule_reminder(pairs, normals):
    if not _has(normals, REMINDER_WORDS):
        return None

    seconds, used = _parse_duration(normals)
    if not seconds:
        return None

    skip = REMINDER_WORDS | {"baad", "after", "in", "mein", "later", "set", "lagao", "laga", "lagana", "chahiye", "kar", "dilao"}
    name = [
        display for i, (normal, display) in enumerate(pairs)
        if i not in used and normal not in skip and normal not in FILLERS
    ]

    command = "remind me"
    if name:
        command += " to " + " ".join(name)
    return f"{command} in {_format_duration(seconds)}"


def _routine_name(pairs):
    return " ".join(_clean_words(
        pairs, ROUTINE_WORDS, OPEN_WORDS, CLOSE_WORDS, START_WORDS, CREATE_WORDS,
        SHOW_WORDS, DELETE_WORDS, PLAY_WORDS
    ))


def _rule_routine(pairs, normals):
    if not _has(normals, ROUTINE_WORDS):
        return None

    name = _routine_name(pairs)

    if _has(normals, CREATE_WORDS):
        return f"create {name} routine" if name else "create routine"

    if _has(normals, SHOW_WORDS) or ("routines" in normals and not name):
        return f"show {name} routine" if name else "show routines"

    if _has(normals, DELETE_WORDS):
        return f"delete {name} routine" if name else None

    if _has(normals, CLOSE_WORDS):
        return f"close {name} routine" if name else None

    return f"run {name} routine" if name else None


def _rule_notes(pairs, normals):
    if not _has(normals, NOTE_WORDS):
        return None

    if _has(normals, SAVE_WORDS):
        return "save notes"
    if _has(normals, CLOSE_WORDS):
        return "close notes"
    if _has(normals, ADD_WORDS | CREATE_WORDS):
        return "add a note"
    if _has(normals, SHOW_WORDS | OPEN_WORDS | {"dekho"}):
        return "open notes"

    return None


def _rule_tasks(pairs, normals):
    if not _has(normals, TASK_WORDS):
        return None

    number = _first_number([n for n in normals if n not in {"ek", "do"} or any(m.isdigit() for m in normals)])

    if number is not None and _has(normals, DONE_WORDS):
        return f"mark task {number} as done"

    if number is not None and _has(normals, DELETE_WORDS):
        return f"delete task {number}"

    if _has(normals, ADD_WORDS | CREATE_WORDS):
        content = " ".join(_clean_words(pairs, TASK_WORDS, ADD_WORDS, CREATE_WORDS, OPEN_WORDS, SHOW_WORDS))
        return f"add task {content}" if content else "add a task"

    if _has(normals, CLOSE_WORDS):
        return "close tasks"

    if _has(normals, SHOW_WORDS | OPEN_WORDS):
        return "show my tasks"

    return None


def _rule_info(pairs, normals):
    asks = {"kya", "kitne", "kitna", "batao", "bata", "hai", "hua", "bataiye"}

    if _has(normals, {"baje", "samay", "time", "waqt", "vakt"}) and _has(normals, asks):
        return "what time is it"

    if _has(normals, {"date", "tarikh", "tareekh", "taareekh", "tithi"}) or (
        "din" in normals and _has(normals, {"aaj", "kaun"})
    ):
        return "what is today's date"

    if _has(normals, {"battery", "batri", "charge"}):
        return "battery status"

    return None


def _rule_system(pairs, normals):
    if "lock" in normals:
        return "lock computer"

    if _has(normals, {"shutdown"}):
        return "shutdown"

    if _has(normals, {"restart", "reboot"}):
        return "restart"

    if _has(normals, {"computer", "pc", "laptop"}) and _has(normals, CLOSE_WORDS):
        return "shutdown"

    return None


def _rule_play(pairs, normals):
    if not _has(normals, PLAY_WORDS):
        return None

    query = _clean_words(
        pairs, PLAY_WORDS, {"youtube", "yt", "gaana", "gana", "gaane", "geet", "song", "video", "music", "sangeet"}
    )
    query_text = " ".join(query)

    # "chrome chalao" means open chrome, "shape of you chalao" means play it
    if (_has(normals, {"chalao", "chala"}) and not _has(normals, {"bajao", "baja", "sunao", "suna", "play"})
            and query_text in _known_targets()):
        return f"open {query_text}"

    return f"play {query_text}".strip()


def _rule_search(pairs, normals):
    asks_search = _has(normals, SEARCH_WORDS)
    web = _has(normals, {"google", "web", "internet", "online"})

    if not asks_search and not (web and _has(normals, {"kar", "karo", "kare", "kijiye", "kariye"})):
        return None

    query = " ".join(_clean_words(
        pairs, SEARCH_WORDS, {"google", "web", "internet", "online", "youtube", "yt", "baare", "bare", "about", "for"}
    ))

    if not query:
        return "google" if "google" in normals else None

    if _has(normals, {"youtube", "yt"}):
        return f"search youtube for {query}"

    if web:
        return f"google {query}"

    # Same as the English command: "search X" / "find X" look for files
    if _has(normals, {"dhundo", "dhoondo", "dhundh", "dhundhiye", "khojo", "khoj", "khojiye", "find"}):
        return f"find {query}"

    return f"search {query}"


def _rule_close(pairs, normals):
    if not _has(normals, CLOSE_WORDS):
        return None

    target = " ".join(_clean_words(pairs, CLOSE_WORDS))
    return f"close {target}" if target else None


def _rule_open(pairs, normals):
    if not _has(normals, OPEN_WORDS | START_WORDS):
        return None

    target = " ".join(_clean_words(pairs, OPEN_WORDS, START_WORDS))
    return f"open {target}" if target else None


def _rule_greeting(pairs, normals):
    if _has(normals, {"namaste", "namaskar", "pranam", "hello", "hi", "hey"}):
        return "hello"
    if _has(normals, {"madad", "sahayata", "sahaayata"}):
        return "help"
    return None


# Order matters: the first rule that matches wins
RULES = (
    _rule_reminder, _rule_routine, _rule_notes, _rule_tasks, _rule_voice, _rule_volume,
    _rule_info, _rule_system, _rule_play, _rule_search, _rule_close, _rule_open,
    _rule_greeting,
)


def to_english(text):
    """
    Turn a Hindi / Hinglish command into an English command.
    Returns None if the text is not Hindi (or not a command I know), so plain
    English is never changed.
    """

    pairs = _tokens(text)
    normals = [normal for normal, _ in pairs]

    if not normals:
        return None

    is_hindi = has_devanagari(text) or _has(normals, HINDI_MARKERS)
    if not is_hindi:
        return None

    for rule in RULES:
        result = rule(pairs, normals)
        if result:
            return " ".join(result.split())

    return None