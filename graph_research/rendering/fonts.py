"""Local font fallback for exported scientific labels; no downloads or global rc changes."""
from functools import lru_cache


CJK_FAMILIES=('Microsoft YaHei','Microsoft YaHei UI','SimHei','SimSun','DengXian',
              'Noto Sans CJK SC','Noto Sans SC','Source Han Sans SC','PingFang SC','WenQuanYi Zen Hei')


@lru_cache(maxsize=1)
def available_families():
    from matplotlib import font_manager
    return frozenset(font.name for font in font_manager.fontManager.ttflist)


def label_font_families(text):
    """Select installed fallback families when labels contain CJK/extended characters.

    Missing fonts remain visible as Matplotlib warnings; no unsupported glyph is
    silently replaced with another label. ASCII drawings keep the user's style.
    """
    if not any(ord(character)>=0x2e80 for character in str(text)):return None
    available=available_families()
    candidates=[family for family in CJK_FAMILIES if family in available]
    for family in ('DejaVu Sans','Segoe UI Symbol','Segoe UI Emoji'):
        if family in available and family not in candidates:candidates.append(family)
    return candidates or None
