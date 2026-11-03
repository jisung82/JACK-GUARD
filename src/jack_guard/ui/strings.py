"""Central text catalogue for adding translations; Korean is the initial locale."""

STRINGS = {
    "ko": {
        "title": "JACK GUARD",
        "lock": "Windows 잠금",
        "privacy": "프라이버시 모드",
        "settings": "설정",
        "quit": "종료",
    },
    "en": {
        "title": "JACK GUARD",
        "lock": "Lock Windows",
        "privacy": "Privacy mode",
        "settings": "Settings",
        "quit": "Quit",
    },
}


def tr(key, locale="ko"):
    return STRINGS.get(locale, STRINGS["ko"]).get(key, key)
