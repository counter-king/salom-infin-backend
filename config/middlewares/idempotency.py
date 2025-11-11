import json
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.expiry = getattr(settings, "IDEMPOTENCY_KEY_EXPIRY", 86400)

    def __call__(self, request):
        # Only apply to POST requests
        if request.method == "POST":
            key = request.headers.get("Idempotency-Key")

            if not key:
                return JsonResponse(
                    {"message": "Missing Idempotency-Key header."},
                    status=400
                )

            cache_key = f"idempotency:{key}"

            # If key exists → return stored response
            if cached := cache.get(cache_key):
                return JsonResponse(cached["data"], status=cached["status"])

            # Process request
            response = self.get_response(request)

            # Store only if success (you can adjust this)
            if 200 <= response.status_code < 300:
                try:
                    # Convert response to JSON serializable dict
                    data = json.loads(response.content.decode())
                except Exception:
                    data = {"non_json_response": True}

                cache.set(
                    cache_key,
                    {"status": response.status_code, "data": data},
                    timeout=self.expiry
                )

            return response

        # Non-POST → just continue
        return self.get_response(request)
