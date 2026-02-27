from django.utils import translation


def current_language(request):
    lang = translation.get_language()
    return {
        'current_language': lang,
        'rtl': lang == 'fa',
    }
