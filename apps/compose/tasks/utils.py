import logging
import requests
from collections import OrderedDict, defaultdict

from celery import shared_task
from django.utils import timezone

from apps.compose.models import BusinessTrip, Compose, IABSActionHistory, IABSRequestCallHistory
from apps.compose.services import IABSRequestService
from utils.tools import split_reg_number


@shared_task
def debug_tasks():
    logging.info('compose tasks are running')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def add_object_id_to_trip(self, notice_id, object_id, **kwargs):
    """
    This function is responsible for adding order_id to the trip.
    """
    try:
        trips = BusinessTrip.objects.filter(notice_id=notice_id)
        for trip in trips:
            trip.order_id = object_id
            trip.save()

    except Exception as e:
        logging.error(f"Error adding object_id to trip: {e}")
        self.retry(exc=e, countdown=60)

    create_trip = kwargs.get('create_trip', None)
    if create_trip:
        from apps.compose.tools import create_trip_verification
        compose = Compose.objects.get(id=notice_id)
        create_trip_verification(compose)


def create_iabs_action(trip, status, action, compose_id=None,
                       result=None, user_id=None, iabs_id=None,
                       request_body=None, response_body=None,
                       endpoint=None, type=None, request_id=None):
    """
    This function creates an IABS action history entry for a given trip.
    """
    iabs_obj = IABSActionHistory.objects.create(
        status=status,
        history_for=trip,
        result=result,
        user_id=user_id,
        iabs_id=iabs_id,
        action=action,
        compose_id=compose_id,
        request_body=request_body,
        response_body=response_body,
        endpoint=endpoint,
        type=type,
        request_id=request_id
    )
    IABSRequestCallHistory.objects.create(
        action_history=iabs_obj,
        caller_id=user_id,
        status=status,
        request_id=request_id,
        request_body=request_body,
        response_body=response_body
    )


SENT = 'sent'
FAILED = 'failed'


def create_iabs_trip_order(trip_data, seen, service,
                           hashmap, errors, compose_id,
                           reg_series, reg_number, ord_data):
    """
    Creates IABS orders per unique local_code and records action history.
    trip_data MUST be a queryset with user->company preloaded.
    """
    for t in trip_data:
        local_code = getattr(getattr(t.user, "company", None), "local_code", None)
        if not local_code:
            msg = f"Missing local_code for user {t.user_id}"
            errors.append(msg)
            continue

        if local_code in seen:
            continue

        seen.add(local_code)
        order_data = {
            "localCode": local_code,
            "orderDate": ord_data,
            "orderType": 2,  # 2 for simple order
            "orderNumber": reg_series,  # number should be numeric part
            "orderSeria": reg_number,  # series should be alpha part
        }

        ord_res = service.create_order(order_data) or {}
        response_body = ord_res.get("responseBody") or {}
        iabs_order_id = response_body.get("orderId")
        hashmap[local_code] = iabs_order_id  # may be None; caller guards before trip create

        endpoint = ord_res.get("endpoint")
        request_id = ord_res.get("request_id")
        status = SENT if iabs_order_id else FAILED
        result = "Order created on IABS" if iabs_order_id else "Missing orderId"

        create_iabs_action(
            t,
            status=status,
            result=result,
            user_id=t.user_id,
            action="create",
            compose_id=compose_id,
            request_body=order_data,
            response_body=ord_res,
            endpoint=endpoint,
            type="order",
            request_id=request_id,
        )

        if status == FAILED:
            errors.append(f"Order creation failed for local code {local_code}: {ord_res}")


def get_old_iabs_id(compose_id: int) -> int | None:
    # Prefer the latest "order" action if you store type/action fields; adjust filter as needed.
    qs = (IABSActionHistory.objects
          .filter(compose_id=compose_id, type="order")
          .order_by("-id")
          .only("iabs_id"))
    rec = qs.first()
    return rec.iabs_id if rec else None


@shared_task
def send_about_trip_creation_iabs(branch_code, ord_num, ord_data, **kwargs):
    """
    This function is a Celery task that sends trip creation data to the IABS system.
    It uses the IABSRequestService to build the required data structure
    and handles errors during this operation. If an exception occurs,
    the task will retry up to three times, with a default delay of 60 seconds between retries.

    Parameters:
        self: Task instance, automatically passed when the task is bind to itself.
        ord_num (Any): Order number, representing the identifier for the trip creation data.
        ord_data (Any): Additional order data required to send the request.
        **kwargs: Arbitrary keyword arguments that can be supplied to the task.

    Raises:
        Exception: In case an error occurs during the process, it retries the task with the given
                   exception and applies a countdown for the retry.
    """

    try:
        service = IABSRequestService()
        trips = kwargs.get('trips', [])
        type = kwargs.get('type', None)
        compose_id = kwargs.get('compose_id', None)
        trip_ids = [trip.get('trip_id') for trip in trips]
        # Preload user + company to avoid N+1 problems
        trip_data = (BusinessTrip.objects
                     .filter(id__in=trip_ids)
                     .select_related("user__company"))
        # Map trip IDs to trip instances
        trip_map = {t.id: t for t in trip_data}
        # Expect split_reg_number to return (series, number)
        reg_seria, reg_num = split_reg_number(ord_num)
        seen: set[str] = set()  # To track local codes that have already been processed
        hashmap: dict[str, int | None] = {}  # To store local codes and their corresponding IABS order IDs
        errors: list[str] = []  # To collect errors if any
        old_iabs_order_id: int | None = None

        if type == "trip_extension":
            parent_compose_id = kwargs.get("parent_compose_id")
            old_iabs_order_id = get_old_iabs_id(parent_compose_id)
            if old_iabs_order_id is None:
                errors.append(f"No previous IABS order found for compose_id={parent_compose_id}")
        else:
            create_iabs_trip_order(trip_data, seen, service, hashmap, errors,
                                   compose_id, reg_seria, reg_num, ord_data)

        order_type = kwargs.get('order_type', '100')  # Default to '100' if not provided

        # Create trips in IABS
        for trip in trips:
            trip_instance = trip_map.get(trip['trip_id'])
            if type == 'trip_extension':
                iabs_order_id = old_iabs_order_id
            else:
                iabs_order_id = hashmap.get(trip.get('local_code'))

            trip_payload = {
                "orderId": str(iabs_order_id),
                "orderType": order_type,
                "tripType": "1",
                "empId": trip.get('user_emp_id'),
                "beginDate": trip.get('start_date'),
                "endDate": trip.get('end_date'),
                "education": "N",
                "regionCode": "",
                "districtCode": "",
                "countryCode": "860",
                "tripLocation": ', '.join(trip.get('locations')),
                "tripReason": ', '.join(trip.get('goals')),
                "empSubstitute": "",
                "interestRate": "",
                "regNumber": reg_seria,
                "regSeria": reg_num,
                "regReason": "Raport"
            }

            trip_response = service.create_trip(trip_payload) or {}
            is_ok = (trip_response.get("code") == 0)
            status = SENT if is_ok else FAILED
            # On success: friendly message; on failure: include message/error code
            result = ("Trip created on IABS"
                      if is_ok
                      else (trip_response.get("message") or "IABS trip create failed"))

            endpoint = trip_response.get('endpoint')
            request_id = trip_response.get('request_id')

            create_iabs_action(trip_instance, status=status, result=result,
                               user_id=trip['user_id'], iabs_id=iabs_order_id, action='create',
                               compose_id=compose_id, request_body=trip_payload,
                               response_body=trip_response, endpoint=endpoint,
                               type='trip', request_id=request_id)

            if not is_ok:
                errors.append(
                    f"Trip creation failed for user {trip['user_id']}: {trip_response}"
                )
                logging.error(errors[-1])

        if errors:
            error_message = "Errors occurred during trip creation:\n" + "\n".join(errors)
            return error_message

        return f"Trip creation request sent to IABS for trip {ord_num}"
    except Exception as e:
        logging.error(f"Error sending trip to IABS: {e}")
