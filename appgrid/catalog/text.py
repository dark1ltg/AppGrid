from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_PARA = re.compile(r"</p>\s*<p[^>]*>", re.IGNORECASE)
_SPACE = re.compile(r"[ \t]+\n")
_MULTI = re.compile(r"\n{3,}")


def plain_text(markup: str | None) -> str:
    """Turn AppStream HTML/XML markup into readable plain text."""
    if not markup:
        return ""
    text = markup.replace("\r\n", "\n")
    text = _BREAK.sub("\n", text)
    text = _PARA.sub("\n\n", text)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _SPACE.sub("\n", text)
    text = _MULTI.sub("\n\n", text)
    return text.strip()
