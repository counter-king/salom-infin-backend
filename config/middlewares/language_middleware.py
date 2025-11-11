from django.utils import translation


class ActivateLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'HTTP_ACCEPT_LANGUAGE' in request.META:
            language = request.META.get('HTTP_ACCEPT_LANGUAGE')
            translation.activate(language)
        response = self.get_response(request)
        return response
