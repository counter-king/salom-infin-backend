from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.inspectors import SwaggerAutoSchema
from rest_framework.schemas.openapi import AutoSchema


class BothHttpAndHttpsSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        schema.schemes = ["http", "https"]
        return schema

    def get_operation(self, view, method, operation_keys, *args, **kwargs):
        # A list of standard HTTP verbs to check against.
        # HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
        #
        # # Check if the 'method' parameter is a valid HTTP verb.
        # http_method_name = method.upper() if method.upper() in HTTP_METHODS else None
        #
        # # If it's not a verb, try to get it from the view's action.
        # if not http_method_name:
        #     view_action = getattr(view, 'action', None)
        #     if view_action:
        #         # DRF maps actions to HTTP verbs (e.g., 'create' maps to 'POST').
        #         # We need to handle this mapping.
        #         if view_action == 'create':
        #             http_method_name = 'POST'
        #         elif view_action == 'list' or view_action == 'retrieve':
        #             http_method_name = 'GET'
        #         elif view_action == 'update' or view_action == 'partial_update':
        #             http_method_name = 'PUT' if view_action == 'update' else 'PATCH'
        #         elif view_action == 'destroy':
        #             http_method_name = 'DELETE'

        operation = super().get_operation(view, method, operation_keys, *args, **kwargs)

        lang_header = openapi.Parameter(
            name="Accept-Language",
            description="Description",
            required=False,
            in_=openapi.IN_HEADER,
            type=openapi.IN_QUERY,
            enum=['uz', 'ru', 'en'],
            default='uz'
        )

        # Idempotency only for POST requests
        # if http_method_name == 'POST':
        idempotency_key = openapi.Parameter(
            name="Idempotency-Key",
            description="Unique key to ensure idempotency of the request. Only required for POST requests.",
            required=False,
            in_=openapi.IN_HEADER,
            type=openapi.TYPE_STRING,
            default=None
        )

        operation.parameters.append(idempotency_key)
        operation.parameters.append(lang_header)

        return operation
