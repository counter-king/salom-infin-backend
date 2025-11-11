from django.template import Context, Engine

from config.redis_client import redis_client as cache
from .models import NotificationTemplate

CACHE_TTL = 3000


def load_db_template(key: str, lang: str) -> str | None:
    ck = f"notif_tpl:{key}:{lang}"
    text = cache.get(ck)
    if text is not None:
        return text
    tpl = NotificationTemplate.objects.filter(key=key, lang=lang, is_active=True).first()
    if tpl:
        cache.set(ck, tpl.content, CACHE_TTL)
        return tpl.content
    return None


# Build a minimal Engine for plain-text Telegram messages.
# - autoescape=False because we're not rendering HTML (Telegram accepts plain text or HTML via parse_mode)
# - string_if_invalid helps you notice missing variables during dev.
tpl_engine = Engine(
    debug=False,
    autoescape=False,
    string_if_invalid="[[MISSING:{name}]]",
)


class _SafeMap(dict):
    def __missing__(self, key):
        return f"[[MISSING:{key}]]"


def render_notification(key: str, context, lang: str) -> str:
    text = load_db_template(key, lang)
    if not text:
        return ""
    # Choose engine by syntax
    if ("{{" in text) or ("{%" in text):
        # Django-style
        if not isinstance(context, dict):  # guard
            context = {}
        return tpl_engine.from_string(text).render(Context(context)).strip()
    # Python str.format style
    try:
        return text.format_map(_SafeMap(context if isinstance(context, dict) else {})).strip()
    except Exception:
        return text

# def render_notification(key: str, context: dict, lang: str) -> str:
#     """
#     1) Load DB template by (key, lang).
#     2) Render with Django Template (variables like {{count}} replaced).
#     3) If not found, fallback to the code template (file-based).
#     """
#     text = load_db_template(key, lang)
#     if text:
#         tpl = tpl_engine.from_string(text)  # same as Template(text) but with our Engine
#         return tpl.render(Context(context)).strip()
#
#     return ''
