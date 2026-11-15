"""
Web features for the assistant:

    google python tutorials            -> Google search
    search the web for best laptops    -> Google search
    search youtube for lofi music      -> YouTube search results
    play shape of you                  -> plays the first YouTube result
    open youtube / open github.com     -> opens the website
    go to flipkart                     -> opens the website

Plain "search X" / "find X" still search your FILES (features/file_search.py).
Everything opens in your default browser.
"""

import re
import urllib.request
import webbrowser
from urllib.parse import quote_plus


# Spoken name -> website. Add your own favourite sites here.
KNOWN_SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "google calendar": "https://calendar.google.com",
    "google meet": "https://meet.google.com",
    "google translate": "https://translate.google.com",
    "github": "https://github.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "leetcode": "https://leetcode.com",
    "geeksforgeeks": "https://www.geeksforgeeks.org",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "quora": "https://www.quora.com",
    "medium": "https://medium.com",
    "pinterest": "https://www.pinterest.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    "wikipedia": "https://www.wikipedia.org",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "whatsapp web": "https://web.whatsapp.com",
    "naukri": "https://www.naukri.com",
}

# How site names are said aloud (anything not listed is just capitalised)
SITE_DISPLAY_NAMES = {
    "youtube": "YouTube", "github": "GitHub", "linkedin": "LinkedIn",
    "chatgpt": "ChatGPT", "gmail": "Gmail", "stackoverflow": "Stack Overflow",
    "geeksforgeeks": "GeeksforGeeks", "leetcode": "LeetCode", "x": "X",
    "whatsapp web": "WhatsApp Web", "naukri": "Naukri",
}

# Endings accepted for "something.com" (file names like notes.txt are NOT sites)
DOMAIN_ENDINGS = {
    "com", "org", "net", "in", "io", "co", "edu", "gov", "dev", "app", "ai",
    "me", "tv", "info", "biz", "xyz", "us", "uk", "ca", "au", "de", "fr", "jp",
    "space", "online", "site", "tech", "store",
}

_DOMAIN_RE = re.compile(r"^(?:https?://)?((?:[a-z0-9-]+\.)+([a-z]{2,10}))(?:[/?#]\S*)?$")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# ----------------------------------------------------------------------------
# Understanding the command
# ----------------------------------------------------------------------------

_YOUTUBE_SEARCH = [
    re.compile(r"^(?:search|find|look up|lookup)\s+(?:on\s+|in\s+)?youtube\s+(?:for\s+)?(.+)$"),
    re.compile(r"^(?:search|find|look up|lookup)\s+(.+?)\s+(?:on|in)\s+youtube$"),
    re.compile(r"^youtube\s+(?:search\s+)?(?:for\s+)?(.+)$"),
]

_WEB_SEARCH = [
    re.compile(
        r"^(?:search|find|look up|lookup)\s+(?:on\s+|in\s+)?"
        r"(?:google|the web|web|the internet|internet|online)\s*(?:for\s+)?(.+)$"
    ),
    re.compile(
        r"^(?:search|find|look up|lookup)\s+(.+?)\s+"
        r"(?:on|in|using)\s+(?:google|the web|the internet|online)$"
    ),
    re.compile(r"^(?:web|internet|online|google)\s+search\s+(?:for\s+)?(.+)$"),
    re.compile(r"^google\s+(?:for\s+)?(.+)$"),
    re.compile(r"^(?:look up|lookup)\s+(.+)$"),
]

_PLAY = re.compile(r"^play\s+(.+)$")
_OPEN = re.compile(
    r"^(open|go to|goto|visit|browse)\s+(?:the\s+)?(?:website\s+|site\s+|web\s*page\s+)?(.+?)"
    r"(\s+(?:website|site|web\s*page))?$"
)


def _tidy(text):
    return " ".join(text.strip().strip(".?!,").split())


def _clean_play_query(text):
    text = re.sub(r"\s+(?:on|in|from|using)\s+youtube$", "", text)
    text = re.sub(r"^(?:the\s+)?(?:song|video|music video|track)\s+", "", text)
    text = re.sub(r"^youtube\s+", "", text)
    return _tidy(text)


def _as_url(target):
    """Turn "github.com" / "github dot com" / "youtube" into a URL, or None."""

    target = _tidy(target.lower())
    target = re.sub(r"\s+dot\s+", ".", target)       # "github dot com" -> "github.com"
    target = re.sub(r"\s*\.\s*", ".", target)         # "github . com"  -> "github.com"

    if target in KNOWN_SITES:
        return KNOWN_SITES[target]

    match = _DOMAIN_RE.match(target)
    if match and match.group(2) in DOMAIN_ENDINGS:
        return target if target.startswith("http") else "https://" + target

    return None


# ----------------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------------

def _open_in_browser(url):
    try:
        return bool(webbrowser.open(url))
    except Exception as error:
        print("Browser error:", error)
        return False


def google_search(query):
    if not _open_in_browser("https://www.google.com/search?q=" + quote_plus(query)):
        return "I couldn't open your web browser."
    return f"Searching Google for {query}."


def youtube_search(query):
    if not _open_in_browser(
        "https://www.youtube.com/results?search_query=" + quote_plus(query)
    ):
        return "I couldn't open your web browser."
    return f"Searching YouTube for {query}."


def _first_video_id(query):
    """Find the first normal video in the YouTube results page (no API key needed)."""

    request = urllib.request.Request(
        "https://www.youtube.com/results?search_query=" + quote_plus(query),
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "CONSENT=YES+1",
        },
    )

    with urllib.request.urlopen(request, timeout=6) as response:
        page = response.read().decode("utf-8", "ignore")

    # "videoRenderer" = a regular video (ads and Shorts use different names)
    match = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', page)
    return match.group(1) if match else None


def play_youtube(query):
    if not query:
        return "What should I play?"

    try:
        video_id = _first_video_id(query)
    except Exception as error:
        print("YouTube lookup error:", error)
        video_id = None

    if video_id:
        if not _open_in_browser("https://www.youtube.com/watch?v=" + video_id):
            return "I couldn't open your web browser."
        return f"Playing {query} on YouTube."

    # Couldn't pick a video (offline or YouTube changed): show the results instead.
    youtube_search(query)
    return f"I couldn't pick a video automatically, so I opened the YouTube results for {query}."


def _site_name(target, url):
    """Name to say: "YouTube" for known sites, "github.com" for addresses."""

    key = _tidy(target.lower())

    if key in KNOWN_SITES:
        return SITE_DISPLAY_NAMES.get(key, key.title())

    return re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0]


def open_website(url, name):
    if not _open_in_browser(url):
        return "I couldn't open your web browser."
    return f"Opening {name}."


# ----------------------------------------------------------------------------
# Entry point used by command_handler.py
# ----------------------------------------------------------------------------

def handle_web_command(command):
    """
    Returns a response string if this was a web command,
    or None so the other command handlers can try.
    """

    command = _tidy(command.lower())

    # 1. YouTube search
    for pattern in _YOUTUBE_SEARCH:
        match = pattern.match(command)
        if match:
            return youtube_search(_tidy(match.group(1)))

    # 2. Play a video
    match = _PLAY.match(command)
    if match:
        return play_youtube(_clean_play_query(match.group(1)))

    # 3. Google search
    for pattern in _WEB_SEARCH:
        match = pattern.match(command)
        if match:
            return google_search(_tidy(match.group(1)))

    # 4. Open a website
    match = _OPEN.match(command)
    if match:
        verb, target, site_word = match.groups()
        explicit = verb != "open" or bool(site_word) or bool(
            re.match(r"^open\s+(?:the\s+)?(?:website|site|web\s*page)\s", command)
        )

        url = _as_url(target)

        if url:
            return open_website(url, _site_name(target, url))

        # "open notepad" is an app, not a site: let the app launcher handle it.
        if not explicit:
            return None

        # "go to flipkart": one word, guess the .com address
        word = _tidy(target).replace(" ", "")
        if re.fullmatch(r"[a-z0-9-]{2,30}", word):
            return open_website(f"https://www.{word}.com", f"{word}.com")

        return google_search(_tidy(target))

    # "google" / "youtube" on their own
    if command in ("google", "youtube"):
        return open_website(KNOWN_SITES[command], SITE_DISPLAY_NAMES.get(command, command.title()))

    # "play" with nothing after it
    if command == "play":
        return "What should I play? For example, say: play shape of you."

    return None