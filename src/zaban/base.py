import re

from zaban.config import settings

# Every address the server writes goes through here. The site can then run under a base path (for example /zaban)
# on a domain that other apps share.


def base_path() -> str:
    return settings.base_path


def with_base(path: str) -> str:
    # A root-relative address gets the base path in front. Absolute addresses (other sites) are left alone.
    if path.startswith("/") and not path.startswith("//"):
        return f"{base_path()}{path}"
    return path


def cookie_path() -> str:
    # Cookies are scoped to the site's own path, so other apps on the same domain never receive them.
    return base_path() or "/"


_LINK_ATTRIBUTE = re.compile(r"""(\s(?:href|src|action)=["'])/(?!/)""")


def prefix_html(html: str) -> str:
    base = base_path()
    if not base:
        return html
    # Links, sources and forms that start with one slash get the base path.
    # The page script reads the base from window.ZABAN_BASE.
    html = _LINK_ATTRIBUTE.sub(lambda match: f"{match.group(1)}{base}/", html)
    return html.replace("<head>", f'<head><script>window.ZABAN_BASE="{base}";</script>', 1)
