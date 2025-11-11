from django.http import JsonResponse, Http404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler


def base_exception_handler(exc, context):
    # Call the default exception handler first
    response = exception_handler(exc, context)

    # Customize the response for 404 Not Found exceptions
    if isinstance(exc, NotFound) or isinstance(exc, Http404):
        return JsonResponse(data={
            "code": "NOT_FOUND",
            "message": "So'ralgan resurs topilmadi.",
            "status": "fail",
            "status_code": str(status.HTTP_404_NOT_FOUND),
        }, status=status.HTTP_404_NOT_FOUND)

    if response is None:
        # Handle 500 errors or unexpected exceptions
        return JsonResponse(data=
        {
            "code": "SERVER_ERROR",
            "message": str(exc),
            "status": "fail",
            "status_code": str(status.HTTP_500_INTERNAL_SERVER_ERROR)
        },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response
