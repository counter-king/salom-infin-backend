from urllib.parse import urlparse, parse_qs

from rest_framework.pagination import CursorPagination, Cursor
from rest_framework.utils.urls import replace_query_param


def _ensure_token(value: str) -> str:
    """
    DRF's encode_cursor should return an opaque token.
    If a URL sneaks in (due to a monkey patch), extract ?cursor=... once.
    """
    if isinstance(value, str) and value.startswith("http"):
        q = parse_qs(urlparse(value).query)
        token = q.get("cursor", [None])[0]
        if not token:
            raise RuntimeError("encode_cursor returned a URL without ?cursor= param.")
        return token
    return value


class MessageCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = ('-created_date', '-id')

    def _normalize_ordering(self):
        ordg = self.ordering
        return tuple(ordg) if isinstance(ordg, (list, tuple)) else (ordg,)

    def token_for_instance(self, instance, *, reverse: bool) -> str:
        """
        Return an opaque base64-like token for `instance`.
        NOTE: In your environment, encode_cursor is monkey-patched to return a URL.
        We normalize it to the real token with `_ensure_token`.
        """
        ordering = self._normalize_ordering()
        position = self._get_position_from_instance(instance, ordering)

        # Call whatever encode_cursor is currently bound to (base or patched)
        raw = CursorPagination.encode_cursor(self, Cursor(
            offset=0, reverse=reverse, position=position
        ))

        token = _ensure_token(raw)

        # One-time diagnostic to help you find the patch:
        # Comment these prints once you've fixed the override.
        # if raw != token:
        #     print(
        #         "WARNING: encode_cursor returned a URL; extracted token via fallback. "
        #         "Search your codebase for a custom encode_cursor or CursorPagination override."
        #     )

        return token

    def build_link_with_cursor(self, request, token: str) -> str:
        if token.startswith('http'):
            # Extra guard — should never trigger after _ensure_token
            raise RuntimeError("build_link_with_cursor received a URL; expected opaque token.")
        url = request.build_absolute_uri(request.path)
        for k, v in request.query_params.items():
            if k not in ('cursor', 'around'):
                url = replace_query_param(url, k, v)
        return replace_query_param(url, self.cursor_query_param, token)
