import re
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def lang_url(context, lang_code):
    """
    Return the current request path translated to the given language code.
    Strips any existing language prefix, then prepends the new one if needed.
    English (default) has no prefix (prefix_default_language=False).
    """
    request = context["request"]
    path = request.get_full_path()  # preserves query string

    # Strip any existing 2-letter language prefix like /fa/
    base_path = re.sub(r"^/[a-z]{2}/", "/", path)

    if lang_code == "en":
        return base_path
    return f"/{lang_code}{base_path}"
