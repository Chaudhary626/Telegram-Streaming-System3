"""
Metadata Parser — Extracts video information from captions and filenames.

Supports:
- Structured captions (Title:, Season:, Episode:, Quality:, Language:)
- Release-style filenames (Title S01E04 1080p Hindi -Group)
- Anime-style filenames ([Group] Title - 05 [720p].mkv)
- Multi-language detection (Hindi + English + Japanese)
"""
import re
from typing import Optional

# ── Language keywords (case-insensitive matching) ────────────
KNOWN_LANGUAGES = {
    "hindi": "Hindi", "hin": "Hindi", "hi": "Hindi",
    "english": "English", "eng": "English", "en": "English",
    "japanese": "Japanese", "jpn": "Japanese", "ja": "Japanese", "jap": "Japanese",
    "tamil": "Tamil", "tam": "Tamil",
    "telugu": "Telugu", "tel": "Telugu",
    "korean": "Korean", "kor": "Korean", "ko": "Korean",
    "chinese": "Chinese", "chi": "Chinese", "zh": "Chinese",
    "spanish": "Spanish", "esp": "Spanish", "es": "Spanish",
    "french": "French", "fre": "French", "fr": "French",
    "german": "German", "ger": "German", "de": "German",
    "portuguese": "Portuguese", "por": "Portuguese",
    "italian": "Italian", "ita": "Italian",
    "russian": "Russian", "rus": "Russian",
    "arabic": "Arabic", "ara": "Arabic",
    "bengali": "Bengali", "ben": "Bengali",
    "malayalam": "Malayalam", "mal": "Malayalam",
    "kannada": "Kannada", "kan": "Kannada",
    "marathi": "Marathi", "mar": "Marathi",
    "punjabi": "Punjabi", "pan": "Punjabi",
    "gujarati": "Gujarati", "guj": "Gujarati",
    "dubbed": "Dubbed", "dub": "Dubbed",
    "dual audio": "Dual Audio", "multi": "Multi",
    "multi audio": "Multi Audio",
}

# Quality patterns
QUALITY_MAP = {
    "2160p": "2160p", "4k": "2160p", "uhd": "2160p",
    "1080p": "1080p", "fhd": "1080p", "full hd": "1080p",
    "720p": "720p", "hd": "720p",
    "480p": "480p", "sd": "480p",
    "360p": "360p",
}

# Subtitle patterns
SUB_PATTERNS = ["esub", "e-sub", "hardsub", "hard-sub", "softsub", "soft-sub",
                "subtitles", "subtitle", "subs", "sub", "eng sub", "hindi sub"]


def detect_quality_from_resolution(width: int, height: int) -> str:
    """Detect quality from video dimensions."""
    r = min(width, height) if width > 0 and height > 0 else max(width, height)
    if r >= 2160: return "2160p"
    if r >= 1080: return "1080p"
    if r >= 720: return "720p"
    return "480p"


def _extract_quality(text: str) -> Optional[str]:
    """Extract quality from text."""
    text_lower = text.lower()
    # Direct match: 1080p, 720p, etc.
    m = re.search(r'\b(\d{3,4})p\b', text_lower)
    if m:
        q = m.group(0)
        return QUALITY_MAP.get(q, q)
    # Keyword match
    for key, val in QUALITY_MAP.items():
        if key in text_lower:
            return val
    return None


def _extract_languages(text: str) -> list:
    """Extract languages from text. Handles: Hindi + English + Japanese, Hindi, English."""
    langs = []
    text_lower = text.lower().strip()
    # Split by common delimiters
    parts = re.split(r'[+,&/|]', text_lower)
    for part in parts:
        part = part.strip()
        if part in KNOWN_LANGUAGES:
            lang = KNOWN_LANGUAGES[part]
            if lang not in langs:
                langs.append(lang)
    # If no split worked, check for individual language keywords in full text
    if not langs:
        for key, val in KNOWN_LANGUAGES.items():
            if len(key) >= 3 and re.search(r'\b' + re.escape(key) + r'\b', text_lower):
                if val not in langs:
                    langs.append(val)
    return langs


def _extract_subtitles(text: str) -> Optional[str]:
    """Detect subtitle info from text."""
    text_lower = text.lower()
    for pattern in SUB_PATTERNS:
        if pattern in text_lower:
            if "esub" in text_lower or "e-sub" in text_lower:
                return "ESub"
            if "hardsub" in text_lower or "hard-sub" in text_lower:
                return "HardSub"
            if "softsub" in text_lower or "soft-sub" in text_lower:
                return "SoftSub"
            return "Yes"
    # Check for explicit "No" subtitle
    if re.search(r'subtitles?\s*:\s*no', text_lower):
        return "No"
    return None


def parse_caption(caption: str) -> dict:
    """
    Parse structured caption format:
    📝 Title: Kaiju No.8
    🎬 Season: S01
    🎞 Episode: E04
    📀 Quality: 1080p
    🔊 Language: Hindi + English + Japanese + Tamil
    ✍️ Subtitles: No
    """
    result = {"title": None, "season": None, "episode": None,
              "quality": None, "languages": [], "subtitles": None, "group": None}

    if not caption:
        return result

    lines = caption.strip().split("\n")

    for line in lines:
        # Remove emoji prefixes
        clean = re.sub(r'^[^\w\s]*\s*', '', line.strip())

        # Title
        m = re.match(r'(?:title|name|movie|anime|show)\s*[:\-–]\s*(.+)', clean, re.IGNORECASE)
        if m:
            result["title"] = m.group(1).strip()
            continue

        # Season
        m = re.match(r'(?:season|s)\s*[:\-–]?\s*S?(\d{1,3})', clean, re.IGNORECASE)
        if m:
            result["season"] = int(m.group(1))
            continue

        # Episode
        m = re.match(r'(?:episode|ep|e)\s*[:\-–]?\s*E?(\d{1,4})', clean, re.IGNORECASE)
        if m:
            result["episode"] = int(m.group(1))
            continue

        # Quality
        m = re.match(r'(?:quality|resolution|res)\s*[:\-–]\s*(.+)', clean, re.IGNORECASE)
        if m:
            q = _extract_quality(m.group(1))
            if q: result["quality"] = q
            continue

        # Language
        m = re.match(r'(?:language|lang|audio)\s*[:\-–]\s*(.+)', clean, re.IGNORECASE)
        if m:
            result["languages"] = _extract_languages(m.group(1))
            continue

        # Subtitles
        m = re.match(r'(?:subtitles?|subs?)\s*[:\-–]\s*(.+)', clean, re.IGNORECASE)
        if m:
            result["subtitles"] = _extract_subtitles(m.group(1)) or m.group(1).strip()
            continue

        # Release group
        m = re.match(r'(?:group|team|by|release)\s*[:\-–]\s*(.+)', clean, re.IGNORECASE)
        if m:
            result["group"] = m.group(1).strip()
            continue

    # Fallback: if no structured fields found, try to extract from freeform caption
    if not result["title"] and not result["season"] and not result["episode"]:
        result = {**result, **_parse_freeform(caption)}

    return result


def parse_filename(filename: str) -> dict:
    """
    Parse release-style filenames:
    - Witch Hat Atelier S01E01 720p HD WEB-DL ESub English -AnimeGalaxyHub
    - [SubGroup] Title - 05 [720p].mkv
    - One.Piece.S02E1080.1080p.Hindi.Dubbed.mkv
    """
    result = {"title": None, "season": None, "episode": None,
              "quality": None, "languages": [], "subtitles": None, "group": None}

    if not filename:
        return result

    # Remove file extension
    name = re.sub(r'\.(mkv|mp4|avi|webm|mov|ts|flv)$', '', filename, flags=re.IGNORECASE)

    # Extract group from [GroupName] at start or -GroupName at end
    m = re.match(r'^\[([^\]]+)\]\s*', name)
    if m:
        result["group"] = m.group(1).strip()
        name = name[m.end():]

    m = re.search(r'\s*[-–]\s*(\w[\w\s]*?)$', name)
    if m and len(m.group(1).strip()) < 30:
        candidate = m.group(1).strip()
        # Don't treat language names as groups
        if candidate.lower() not in KNOWN_LANGUAGES:
            result["group"] = candidate
            name = name[:m.start()]

    # Extract Season + Episode: S01E04, S1E4, Season 1 Episode 4
    m = re.search(r'S(\d{1,3})\s*E(\d{1,4})', name, re.IGNORECASE)
    if m:
        result["season"] = int(m.group(1))
        result["episode"] = int(m.group(2))
        title_part = name[:m.start()].strip()
    else:
        # Try "- 05" or "Episode 05" style
        m = re.search(r'(?:[-–]\s*|Episode\s*|Ep\s*|E)(\d{1,4})\b', name, re.IGNORECASE)
        if m:
            result["episode"] = int(m.group(1))
            title_part = name[:m.start()].strip()
        else:
            title_part = name

    # Extract quality
    q = _extract_quality(name)
    if q:
        result["quality"] = q

    # Extract languages
    langs = _extract_languages(name)
    if langs:
        result["languages"] = langs

    # Extract subtitles
    subs = _extract_subtitles(name)
    if subs:
        result["subtitles"] = subs

    # Clean up title
    if title_part:
        # Remove quality, language keywords, brackets, dots
        title = title_part
        title = re.sub(r'\[.*?\]', '', title)  # Remove [tags]
        title = re.sub(r'\b\d{3,4}p\b', '', title, flags=re.IGNORECASE)  # Remove quality
        title = re.sub(r'\b(?:HD|FHD|UHD|WEB-DL|WEB|WEBRip|BDRip|BluRay|HDTV|DVDRip|HEVC|x264|x265|AAC|10bit)\b',
                        '', title, flags=re.IGNORECASE)
        # Remove known language keywords from title
        for key in KNOWN_LANGUAGES:
            if len(key) >= 4:
                title = re.sub(r'\b' + re.escape(key) + r'\b', '', title, flags=re.IGNORECASE)
        title = title.replace('.', ' ').replace('_', ' ')
        title = re.sub(r'\s+', ' ', title).strip(' -–')
        if title:
            result["title"] = title

    return result


def _parse_freeform(text: str) -> dict:
    """Try to extract metadata from unstructured text."""
    result = {"title": None, "season": None, "episode": None,
              "quality": None, "languages": [], "subtitles": None}

    # Season + Episode
    m = re.search(r'S(\d{1,3})\s*E(\d{1,4})', text, re.IGNORECASE)
    if m:
        result["season"] = int(m.group(1))
        result["episode"] = int(m.group(2))

    # Quality
    q = _extract_quality(text)
    if q: result["quality"] = q

    # Languages
    langs = _extract_languages(text)
    if langs: result["languages"] = langs

    # Subtitles
    subs = _extract_subtitles(text)
    if subs: result["subtitles"] = subs

    return result


def parse_video_metadata(caption: str = "", filename: str = "",
                          width: int = 0, height: int = 0) -> dict:
    """
    Combined metadata parser. Priority:
    1. Caption (structured data)
    2. Filename (release-style)
    3. Video dimensions (quality fallback)

    Returns: {title, season, episode, quality, languages, subtitles, group, source}
    """
    # Try caption first
    cap = parse_caption(caption) if caption else {}
    # Then filename
    fn = parse_filename(filename) if filename else {}

    # Merge: caption takes priority
    result = {
        "title": cap.get("title") or fn.get("title"),
        "season": cap.get("season") if cap.get("season") is not None else fn.get("season"),
        "episode": cap.get("episode") if cap.get("episode") is not None else fn.get("episode"),
        "quality": cap.get("quality") or fn.get("quality"),
        "languages": cap.get("languages") or fn.get("languages") or [],
        "subtitles": cap.get("subtitles") or fn.get("subtitles"),
        "group": cap.get("group") or fn.get("group"),
        "source": "caption" if cap.get("title") else ("filename" if fn.get("title") else "auto"),
    }

    # Quality fallback from video dimensions
    if not result["quality"] and (width > 0 or height > 0):
        result["quality"] = detect_quality_from_resolution(width, height)

    # Default quality
    if not result["quality"]:
        result["quality"] = "720p"

    # Default language
    if not result["languages"]:
        result["languages"] = ["Hindi"]

    return result


def format_metadata_card(meta: dict, file_size: int = 0, duration: int = 0) -> str:
    """Format metadata as a Telegram message card."""
    title = meta.get("title") or "Unknown Title"
    season = meta.get("season")
    episode = meta.get("episode")
    quality = meta.get("quality") or "720p"
    langs = meta.get("languages") or ["Hindi"]
    subs = meta.get("subtitles")
    group = meta.get("group")

    # Size formatting
    size_str = ""
    if file_size:
        if file_size >= 1073741824:
            size_str = f"{file_size/1073741824:.2f} GB"
        elif file_size >= 1048576:
            size_str = f"{file_size/1048576:.1f} MB"
        else:
            size_str = f"{file_size/1024:.0f} KB"

    # Duration formatting
    dur_str = ""
    if duration:
        mins = duration // 60
        secs = duration % 60
        dur_str = f"{mins}m {secs}s"

    # Build card
    lines = [f"📹 **Video Detected**", "━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"📝 **{title}**")

    if season is not None and episode is not None:
        lines.append(f"🎬 Season {season} → Episode {episode}")
    elif season is not None:
        lines.append(f"🎬 Season {season}")
    elif episode is not None:
        lines.append(f"🎞 Episode {episode}")

    info_parts = [f"📀 {quality}"]
    if size_str: info_parts.append(f"📦 {size_str}")
    if dur_str: info_parts.append(f"⏱ {dur_str}")
    lines.append(" · ".join(info_parts))

    lines.append(f"🔊 {' + '.join(langs)}")

    if subs:
        lines.append(f"✍️ Subs: {subs}")
    if group:
        lines.append(f"👤 {group}")

    # Multi-language warning
    if len(langs) > 1:
        lines.append("")
        lines.append("⚠️ **Note:** Multiple languages detected in caption.")
        lines.append("Separate source entries will be created per language.")
        lines.append("Each entry uses the same file — language switching")
        lines.append("requires separate files for each language.")

    lines.append("━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)
