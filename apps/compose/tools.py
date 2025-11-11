from collections import OrderedDict, defaultdict

from django.utils import timezone

from apps.compose.models import (
    Compose,
    Signer,
    Receiver,
    BusinessTrip,
    TripPlan,
    Booking,
    ComposeLink, Approver,
)
from apps.compose.services import GenerateComposeRegisterNumber
from apps.compose.tasks.utils import send_about_trip_creation_iabs
from apps.conftest import document_sub_type
from apps.docflow.models import BaseDocument, Reviewer, DocumentFile, Assignment, Assignee
from apps.pdf_kit.generate_letter import (
    GenerateInnerLetterToPdf,
    GenerateApplicationToPDF,
    GenerateTripNoticeToPdf,
    GenerateOrderToPdf,
    GenerateNoticeToPdf,
    GenerateDecreeToPdf,
    GenerateLocalTripOrderToPdf,
    GeneratePowerOfAttorneyToPdf,
    GenerateTripNoticeV2ToPdf, GenerateActToPdf,
)
from apps.reference.tasks import action_log
from apps.user.models import User
from config.middlewares.current_user import get_current_user_id
from utils.constant_ids import (
    get_default_base_doc_status_id,
    get_compose_status_id,
    get_in_progress_base_doc_status_id,
)
from utils.constants import CONSTANTS
from utils.tools import normalize_user_name, first_letter, send_sms_to_phone, calculate_years_and_months, \
    get_content_type_id, format_uzbek_date

DOC_TYPE = CONSTANTS.DOC_TYPE_ID


def create_base_document(compose, register_date, register_number=None):
    base_document = BaseDocument.objects.create(register_number=register_number,
                                                document_type_id=compose.document_type_id,
                                                company_id=compose.company_id,
                                                journal_id=compose.journal_id,
                                                description=compose.short_description,
                                                document_sub_type_id=compose.document_sub_type_id,
                                                created_by_id=compose.author_id,
                                                modified_by_id=compose.author_id,
                                                register_date=register_date,
                                                compose_id=compose.id)
    return base_document


def send_for_review(receiver_id, base_document_id, **kwargs):
    """
    This function sends the document for review.
    If the receiver is a department, the document will be sent to the head of the department.
    If the receiver does not exist, the document will be sent to the performers.
    """
    status_id = get_default_base_doc_status_id()
    try:
        receivers = Receiver.objects.get(id=receiver_id)
    except Receiver.DoesNotExist:
        performers = kwargs.get('performers')
        for performer in performers:
            user = User.objects.filter(id=performer.get('id')).first()
            if user:
                Reviewer.objects.create(
                    user=user,
                    document_id=base_document_id,
                    status_id=status_id)
    else:
        for receiver in receivers.departments.all():
            user = User.objects.filter(top_level_department_id=receiver.id).first()
            if user:
                Reviewer.objects.create(
                    user=user,
                    document_id=base_document_id,
                    status_id=status_id)


def create_assignment(document_id, signer, performers, text,
                      qr_info=None, resolution_type=None, deadline=None):
    """
    Create a task for the performers.
    It works only for the documents that have just been signed.
    """
    in_progress_status = get_in_progress_base_doc_status_id()
    default_status_id = get_default_base_doc_status_id()

    # Create a reviewer
    review = Reviewer(document_id=document_id,
                      user_id=signer,
                      status_id=in_progress_status,
                      read_time=timezone.now(),
                      has_resolution=True,
                      is_read=True).save()

    # Create an assignment
    assignment = Assignment(reviewer_id=review.id,
                            is_verified=True,
                            is_project_resolution=True,
                            type=resolution_type,
                            receipt_date=timezone.now(),
                            content=text,
                            created_by_id=review.user_id,
                            deadline=deadline).save()

    for index, user in enumerate(performers):
        Assignee.objects.create(assignment_id=assignment.id,
                                user_id=user.get('id'),
                                status_id=default_status_id,
                                is_responsible=True if index == 0 else False,
                                created_by_id=review.user_id)


def get_signers(signers):
    data = []

    for signer in signers:
        data.append({
            'name': f'{first_letter(signer.user.first_name)}. {signer.user.last_name}',
            'position': signer.user.position.name,
            'is_signed': signer.is_signed,
            'signed_date': signer.action_date
        })
    return data


def get_receivers(receiver, type):
    if type == 'departments':
        return [{'name': receive.name} for receive in receiver.departments.all()]
    elif type == 'companies':
        return [{'name': receive.name} for receive in receiver.companies.all()]
    return []


def save_pdf_and_files(compose, base_document, pdf_file_id, request=None):
    """
    Save the generated PDF and related files to the document.
    """
    if pdf_file_id:
        DocumentFile.objects.create(document_id=base_document.id, file_id=pdf_file_id)

    if compose.files.exists():
        for file in compose.files.all():
            DocumentFile.objects.create(document_id=base_document.id, file_id=file.id)

    # Log the creation of the base document
    user_id = get_current_user_id()
    user_ip = None
    ct_id = get_content_type_id(base_document)
    action_log.apply_async(
        (user_id, 'created', '100', ct_id,
         base_document.id, user_ip, base_document.register_number), countdown=2)


def modify_compose(compose, **kwargs):
    compose.registered_document_id = kwargs.get('registered_document_id')
    compose.status_id = get_compose_status_id('done')
    compose.file_id = kwargs.get('file_id')
    compose.register_date = kwargs.get('register_date')
    compose.register_number = kwargs.get('register_number')
    compose.register_number_int = kwargs.get('num')
    compose.is_signed = True
    compose.signed_date = timezone.now()
    compose.save()


def register_service_letter(compose_id, request):
    signers = Signer.objects.filter(compose_id=compose_id)

    if all(signers.values_list('is_signed', flat=True)):
        compose = Compose.objects.get(id=compose_id)
        register_number, num = GenerateComposeRegisterNumber(
            journal_index=compose.journal.index,
            journal_id=compose.journal_id).generate()
        now = timezone.now()
        base_document = create_base_document(compose, now, register_number)

        # Send the document for reviewer
        send_for_review(compose.receiver_id, base_document.id)

        receiver_data = get_receivers(compose.receiver, compose.receiver.type)
        signed_date = signers.last().action_date
        saved_file_id = GenerateInnerLetterToPdf(
            check_id=compose.check_id,
            content=compose.content,
            signers=get_signers(signers),
            receivers=receiver_data,
            executor=normalize_user_name(compose.author.full_name),
            phone=compose.author.cisco if compose.author.cisco else '00-00',
            created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
            signed_date=signed_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
            register_number=register_number,
            register_date=compose.created_date.strftime('%d.%m.%Y'),
            sender=compose.sender.name,
            env_id=compose.company.env_id
        ).generate_pdf()

        modify_compose(compose,
                       registered_document_id=base_document.id,
                       file_id=saved_file_id,
                       register_number=register_number,
                       num=num,
                       register_date=now)
        save_pdf_and_files(compose, base_document, saved_file_id, request)


def register_application(compose_id, request, **kwargs):
    signers = Signer.objects.filter(compose_id=compose_id)

    if all(signers.values_list('is_signed', flat=True)):
        compose = Compose.objects.get(id=compose_id)

        # Register the base document
        register_number, num = GenerateComposeRegisterNumber(
            journal_index=compose.journal.index,
            journal_id=compose.journal_id).generate()
        now = timezone.now()
        base_document = create_base_document(compose, now, register_number)

        performers = kwargs.get('performers')
        send_for_review(None, base_document.id, performers=performers)

        signers_data = get_signers(signers.exclude(type='basic_signer'))
        basic_signer = normalize_user_name(compose.curator.full_name)
        basic_signer_position = compose.curator.position.name
        user_name = normalize_user_name(compose.author.full_name)
        user_position = compose.author.position.name
        user_department = compose.author.top_level_department.name if compose.author.top_level_department else ''
        signed_date = signers.last().action_date

        saved_file_id = GenerateApplicationToPDF(
            check_id=compose.check_id,
            content=compose.content,
            signers=signers_data,
            executor=normalize_user_name(compose.author.full_name),
            phone=compose.author.cisco if compose.author.cisco else '00-00',
            created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
            signed_date=signed_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
            basic_signer=basic_signer,
            basic_signer_position=basic_signer_position,
            user_name=user_name,
            user_position=user_position,
            user_department=user_department,
            env_id=compose.company.env_id,
            document_sub_type_id=compose.document_sub_type_id
        ).generate_pdf()

        modify_compose(compose,
                       registered_document_id=base_document.id,
                       file_id=saved_file_id,
                       register_number=register_number,
                       num=num,
                       register_date=now)
        save_pdf_and_files(compose, base_document, saved_file_id, request)


def get_trip_data(compose_id):
    """Fetch trip information for a given compose_id."""

    trips = (BusinessTrip.objects.
             select_related('user').
             prefetch_related('locations', 'destinations').
             filter(notice_id=compose_id))
    if not trips.exists():
        trips = (BusinessTrip.objects.
                 select_related('user').
                 prefetch_related('locations', 'destinations', 'tags').
                 filter(order_id=compose_id))
    trip_information = []
    counter = 1

    for t in trips:
        trip_information.append({
            'counter': counter,
            'full_name': t.user.full_name,
            'department': t.user.top_level_department.name if t.user.top_level_department else '',
            'position': t.user.position.name if t.user.position else '',
            'destinations': [d.name for d in t.destinations.all()],
            'locations': [l.name for l in t.locations.all()],
            'start_date': t.start_date.strftime('%d.%m.%Y'),
            'end_date': t.end_date.strftime('%d.%m.%Y'),
            'goals': [tag.name_uz for tag in t.tags.all()],
            'group_id': t.group_id,
            'phone': t.user.phone,
            'user_emp_id': t.user.iabs_emp_id,
            'user_id': t.user.id,
            'local_code': t.user.company.local_code,
            'trip_id': t.id,
        })
        counter += 1

    return trip_information


def register_trip_notice(compose_id, request):
    # Fetch the Compose instance
    compose = (Compose.objects.
               select_related('journal', 'author').
               get(id=compose_id))

    # Register the document
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    base_document = create_base_document(compose, compose.created_date, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    signer = signers.last()

    # Get only the full names of the performers
    performers = [normalize_user_name(performer.get('full_name')) for performer in signer.performers]

    # Create a task for the performers
    create_assignment(base_document.id, signer.user_id, signer.performers,
                      signer.resolution_text, resolution_type=signer.resolution_type,
                      deadline=signer.deadline)

    trip_information = get_trip_data(compose_id)

    saved_file_id = GenerateTripNoticeToPdf(
        check_id=compose.check_id,
        content=compose.content,
        short_description=compose.short_description,
        signers=get_signers(signers.exclude(type='basic_signer')),
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        signed_date=signer.action_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        register_number=register_number,
        register_date=compose.created_date.strftime('%d.%m.%Y'),
        sender=compose.sender.name,
        trip_info=trip_information,
        performers=', '.join(performers),
        curator_name=normalize_user_name(compose.curator.full_name),
        curator_position=compose.curator.position.name,
        env_id=compose.company.env_id
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.created_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)


def get_trip_data_by_group_id(compose_id):
    hashmap = defaultdict(list)
    trips = (BusinessTrip.objects.
             select_related('user', 'sender_company').
             prefetch_related('locations', 'destinations', 'countries', 'tags').
             filter(notice_id=compose_id).order_by('group_id'))
    if not trips.exists():
        trips = (BusinessTrip.objects.
                 select_related('user', 'sender_company').
                 prefetch_related('locations', 'destinations', 'tags').
                 filter(order_id=compose_id).order_by('group_id'))

    for trip in trips:
        hashmap[trip.group_id].append({
            'full_name': trip.user.full_name,
            'position': trip.user.position.name if trip.user.position else '',
            'department': trip.user.top_level_department.name if trip.user.top_level_department else '',
            'locations': [location for location in trip.locations.all()],
            'goals': [tag.name_uz for tag in trip.tags.all()],
            'start_date': trip.start_date.strftime('%d.%m.%Y'),
            'end_date': trip.end_date.strftime('%d.%m.%Y'),
            'sender_location': trip.sender_company.region.name if trip.sender_company and trip.sender_company.region else '',
            'countries': [country for country in trip.countries.all()],
        })

    # Convert the hashmap to a list of grouped data
    data = [{'group_id': group_id, 'trips': trips} for group_id, trips in hashmap.items()]
    return data


def booking_segments_view(compose_id):
    bookings = Booking.objects.filter(compose_id=compose_id).prefetch_related(
        'segments',  # Prefetch BookingSegment objects
        'passengers__user'  # Prefetch Passenger and related User objects
    )

    booking_data = []
    for booking in bookings:
        # Prepare initial booking data
        booking_entry = {
            'route': CONSTANTS.COMPOSE.BOOKING_TYPE.GET_ROUTE.get(booking.type, ''),
            'transport': CONSTANTS.COMPOSE.TRIP_ROUTE.GET_TRANSPORT.get(booking.route, ''),
            'passengers': [passenger.user.full_name for passenger in booking.passengers.all()],
            'segments': []  # Initialize the list for segments
        }

        # Loop over segments and format their data
        for segment in booking.segments.all():
            segment_data = {
                'departure_city': segment.departure_city.name if segment.departure_city else '',
                'arrival_city': segment.arrival_city.name if segment.arrival_city else '',
                'segment_class': CONSTANTS.COMPOSE.BOOKING_CLASS.GET_SEGMENT_CLASS.get(segment.segment_class, ''),
                'departure_date': segment.departure_date.astimezone().strftime(
                    '%d.%m.%Y') if segment.departure_date else '',
                'time_range': f"{segment.departure_date.astimezone().strftime('%H:%M')}"
                if segment.departure_date else '',
            }
            booking_entry['segments'].append(segment_data)

        booking_data.append(booking_entry)

    return booking_data


def register_trip_notice_v2(compose_id, request):
    # Fetch the Compose instance
    compose = Compose.objects.get(id=compose_id)

    # Register the document
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    base_document = create_base_document(compose, compose.created_date, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    signer = signers.last()

    # Get only the full names of the performers
    performers = [normalize_user_name(performer.get('full_name')) for performer in signer.performers]

    # Create a task for the performers
    create_assignment(base_document.id, signer.user_id, signer.performers,
                      signer.resolution_text, resolution_type=signer.resolution_type,
                      deadline=signer.deadline)

    trip_information = get_trip_data_by_group_id(compose_id)
    trip_plans = TripPlan.objects.filter(compose_id=compose_id).select_related('compose').prefetch_related('users')
    # Prepare trip plans list
    trip_plans_data = [
        {
            'text': plan.text,
            'users': [user.full_name for user in plan.users.all()]
        }
        for plan in trip_plans
    ]
    # booking = booking_segments_view(compose_id)

    saved_file_id = GenerateTripNoticeV2ToPdf(
        check_id=compose.check_id,
        content=compose.content,
        short_description=compose.short_description,
        signers=get_signers(signers.exclude(type='basic_signer')),
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        signed_date=signer.action_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        register_number=register_number,
        register_date=compose.created_date.strftime('%d.%m.%Y'),
        sender=compose.sender.name,
        trip_info=trip_information,
        performers=', '.join(performers),
        curator_name=normalize_user_name(compose.curator.full_name),
        curator_position=compose.curator.position.name,
        env_id=compose.company.env_id,
        trip_plan=trip_plans_data,
        document_sub_type_id=compose.document_sub_type_id
        # booking=booking
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.created_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)

    # Generate decree v2
    compose_link = ComposeLink.objects.filter(to_compose_id=compose_id).first()
    if compose_link:
        register_decree(compose_link.from_compose_id, request, notice_instance=compose)


def register_notice(compose_id, request):
    # Fetch the Compose instance
    compose = Compose.objects.get(id=compose_id)

    # Register the document
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    base_document = create_base_document(compose, compose.created_date, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    signer = signers.last()

    # Get only the full names of the performers
    performers = [normalize_user_name(performer.get('full_name')) for performer in signer.performers]

    # Create a task for the performers
    create_assignment(base_document.id, signer.user_id, signer.performers,
                      signer.resolution_text,
                      resolution_type=signer.resolution_type, deadline=signer.deadline)

    saved_file_id = GenerateNoticeToPdf(
        check_id=compose.check_id,
        short_description=compose.short_description,
        content=compose.content,
        signers=get_signers(signers.exclude(type='basic_signer')),
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        signed_date=signer.action_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        register_number=register_number,
        register_date=compose.created_date.strftime('%d.%m.%Y'),
        sender=compose.sender.name,
        performers=', '.join(performers),
        curator_name=normalize_user_name(compose.curator.full_name),
        curator_position=compose.curator.position.name,
        env_id=compose.company.env_id
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.created_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)


def register_hr_order(compose_id, request, **kwargs):
    compose = Compose.objects.get(id=compose_id)
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    base_document = create_base_document(compose, compose.register_date, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    performers = kwargs.get('performers')
    send_for_review(None, base_document.id, performers=performers)
    basic_signer_data = get_signers(signers.filter(type='basic_signer'))
    negotiator_data = get_signers(signers.filter(type='negotiator'))
    saved_file_id = GenerateOrderToPdf(
        check_id=compose.check_id,
        content=compose.content,
        signers=basic_signer_data,
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        register_number=register_number,
        register_date=compose.register_date.strftime('%d.%m.%Y'),
        negotiators=negotiator_data,
        env_id=compose.company.env_id
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.register_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)

    if (
            compose.document_type_id == DOC_TYPE.HR_ORDER and
            compose.document_sub_type_id == DOC_TYPE.BUSINESS_TRIP_ORDER
    ):
        create_trip_verification(compose, request)


def create_trip_verification(compose, request=None):
    from apps.compose.models import BusinessTrip, TripVerification

    # Fetch trips by notice_id or order_id
    trips = BusinessTrip.objects.filter(notice_id=compose.id).select_related('sender_company').prefetch_related(
        'locations')
    if not trips.exists():
        trips = BusinessTrip.objects.filter(order_id=compose.id).select_related('sender_company').prefetch_related(
            'locations')

    # Group trips by group_id
    grouped_trips = defaultdict(list)
    for trip in trips:
        grouped_trips[trip.group_id].append(trip)

    # List to store trip verifications
    trip_verifications = []

    # Iterate over each group of trips
    for group_id, group_trips in grouped_trips.items():
        # Prepare a list of region IDs for this group
        region_ids = OrderedDict()
        region_ids[None] = None  # placeholder for sender region

        # Collect unique region IDs for the locations of trips in this group
        for trip in group_trips:
            for location in trip.locations.all():
                region_ids[location.id] = None

        # For each trip in this group, create trip verifications
        for trip in group_trips:
            for idx, location_id in enumerate(region_ids.keys()):
                trip_verifications.append(
                    TripVerification(
                        trip_id=trip.id,
                        region_id=trip.sender_company.region_id if idx == 0 else location_id,
                        is_sender=(idx == 0),  # Sender is true for the first location
                        company_id=trip.sender_company_id if idx == 0 else None,  # Sender company ID
                    )
                )

    # Bulk create trip verifications in one go
    TripVerification.objects.bulk_create(trip_verifications)


def register_decree(compose_id, request, notice_instance=None, **kwargs):
    compose = (Compose.objects.
               select_related('company', 'journal', 'author', 'document_sub_type').
               prefetch_related('signers').
               get(id=compose_id))
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    now = timezone.now()
    base_document = create_base_document(compose, now, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    basic_signer_data = get_signers(signers.order_by('-action_date'))

    compose_instance = notice_instance if notice_instance else compose

    # Create an assignment for the performers
    basic_signer = signers.filter(type='basic_signer').first()
    create_assignment(base_document.id, basic_signer.user_id,
                      basic_signer.performers,
                      basic_signer.resolution_text,
                      resolution_type=basic_signer.resolution_type,
                      deadline=basic_signer.deadline)

    # Fetch trip information
    trip_information = get_trip_data(compose_id)
    trip_v2 = get_trip_data_by_group_id(compose_id)
    register_date = compose.created_date.strftime('%d.%m.%Y')

    saved_file_id = GenerateDecreeToPdf(
        check_id=compose.check_id,
        content=compose.content,
        signers=basic_signer_data,
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        register_number=register_number,
        register_date=register_date,
        trips=trip_information,
        doc_sub_type=compose.document_sub_type_id,
        env_id=compose.company.env_id,
        trip_notice_number=compose.parent.register_number if compose.parent else None,
        trip_v2=trip_v2,
    ).generate_pdf()

    modify_compose(compose, registered_document_id=base_document.id,
                   file_id=saved_file_id, register_number=register_number,
                   num=num, register_date=now)
    save_pdf_and_files(compose, base_document, saved_file_id, request)

    if is_trip_decree(compose):
        handle_trip_decree(compose, request, trip_information, register_number, register_date, compose_instance)

    if is_trip_extension_decree(compose):
        handle_trip_extension(compose, trip_information, register_number, register_date, compose_id)

    # if is_trip_decree(compose):
    #     create_trip_verification(compose, request)
    #     for t in trip_information:
    #         phone = t.get('phone')
    #         full_name = t.get('full_name')
    #         start_date = t.get('start_date')
    #         text = f"Hurmatli xodim! {start_date} dan xizmat safaringiz. SalomSQB ilovasini yuklang, safaringizni tasdiqlang: iOS https://bit.ly/3YMTOzu Android https://bit.ly/42vZoZC"
    #         is_ok, res = send_sms_to_phone(phone, text)
    #         if is_ok:
    #             action_log(compose_instance, request, 'created', '147', full_name)
    #         else:
    #             action_log(compose_instance, request, 'created', '148', res)
    #
    #     # send information about trip to IABS
    #     send_about_trip_creation_iabs.apply_async(
    #         (compose.company.local_code, register_number, register_date),
    #         {
    #             'trips': trip_information,
    #             'compose_id': compose_id,
    #         },
    #         countdown=2,
    #     )
    #
    # if is_trip_extension_decree(compose):
    #     # send information about trip to IABS
    #     send_about_trip_creation_iabs.apply_async(
    #         (compose.company.local_code, register_number, register_date),
    #         {
    #             'trips': trip_information,
    #             'compose_id': compose_id,
    #             'order_type': '102',  # Extend trip decree
    #         },
    #         countdown=2,
    #     )


def handle_trip_decree(compose, request, trips, register_number, register_date, compose_instance):
    create_trip_verification(compose, request)
    user_id = get_current_user_id()
    ct_id = get_content_type_id(compose_instance)

    for trip in trips:
        phone = trip.get('phone')
        full_name = trip.get('full_name')
        start_date = trip.get('start_date')
        message = (
            f"Hurmatli xodim! {start_date} dan xizmat safaringiz. "
            "SalomSQB ilovasini yuklang, safaringizni tasdiqlang: "
            "iOS https://bit.ly/3YMTOzu Android https://bit.ly/4gNU7BU"
        )
        is_ok, res = send_sms_to_phone(phone, message)
        action_log.apply_async(
            (user_id, 'created', '147' if is_ok else '148', ct_id,
             compose_instance.id, None, full_name if is_ok else res), countdown=2)

    send_about_trip_creation_iabs.apply_async(
        (compose.company.local_code, register_number, register_date),
        {
            'trips': trips,
            'compose_id': compose.id,
        },
        countdown=2,
    )


def get_parent_compose_id(compose) -> int:
    parent = Compose.objects.get(id=compose.parent_id).parent_id
    decree_compose = Compose.objects.filter(parent_id=parent).first()

    return decree_compose.id if decree_compose else None


def handle_trip_extension(compose, trips, register_number, register_date, compose_id):
    parent_compose_id = get_parent_compose_id(compose)
    send_about_trip_creation_iabs.apply_async(
        (compose.company.local_code, register_number, register_date),
        {
            'trips': trips,
            'compose_id': compose_id,
            'order_type': '102',  # Extend trip decree
            'type': 'extension',
            'parent_compose_id': parent_compose_id,
        },
        countdown=2,
    )


def is_trip_decree(compose):
    return (
            compose.document_type_id == DOC_TYPE.DECREE_TYPE and
            compose.document_sub_type_id in [DOC_TYPE.TRIP_DECREE_SUB_TYPE, DOC_TYPE.TRIP_DECREE_V2]
    )


def is_trip_extension_decree(compose):
    return (
            compose.document_type_id == DOC_TYPE.DECREE_TYPE and
            compose.document_sub_type_id == DOC_TYPE.EXTEND_TRIP_DECREE_V2
    )


def register_local_trip_order(compose_id, request, **kwargs):
    compose = Compose.objects.get(id=compose_id)
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    now = timezone.now()
    base_document = create_base_document(compose, now, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    negotiators = get_signers(signers.filter(type='signer').order_by('-action_date'))

    # Create an assignment for the performers
    curator_qs = signers.filter(type='basic_signer')
    curator = get_signers(curator_qs)
    basic_signer = curator_qs.first()
    create_assignment(base_document.id, basic_signer.user_id, basic_signer.performers,
                      basic_signer.resolution_text,
                      resolution_type=basic_signer.resolution_type, deadline=basic_signer.deadline)

    # Fetch trip information
    trip_information = get_trip_data(compose_id)

    saved_file_id = GenerateLocalTripOrderToPdf(
        check_id=compose.check_id,
        content=compose.content,
        signers=negotiators,
        curator=curator,
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        register_number=register_number,
        register_date=compose.created_date.strftime('%d.%m.%Y'),
        trips=trip_information,
        env_id=compose.company.env_id
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=now)
    save_pdf_and_files(compose, base_document, saved_file_id, request)

    if (
            compose.document_type_id == DOC_TYPE.HR_ORDER and
            compose.document_sub_type_id == DOC_TYPE.LOCAL_BUSINESS_TRIP_ORDER
    ):
        create_trip_verification(compose, request)


def register_power_of_attorney(compose_id, request):
    # Fetch the Compose instance
    compose = Compose.objects.get(id=compose_id)

    # Register the document
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate_power_of_attorney_number()
    base_document = create_base_document(compose, compose.created_date, register_number)

    signers = Signer.objects.filter(compose_id=compose_id)
    signer = signers.last()

    # Create a task for the performers
    create_assignment(base_document.id,
                      signer.user_id,
                      signer.performers,
                      signer.resolution_text,
                      resolution_type=signer.resolution_type,
                      deadline=signer.deadline)

    old_attorney_date = None
    old_attorney_number = None
    old_attorney_exists = 'not_exists'
    deadline_in_words = calculate_years_and_months(compose.start_date,
                                                   compose.end_date) if compose.start_date and compose.end_date else ''
    if compose.parent and compose.parent.register_date and compose.parent.register_number:
        old_attorney_exists = 'exists'
        old_attorney_date = compose.parent.register_date.strftime('%d.%m.%Y')
        old_attorney_number = compose.parent.register_number

    saved_file_id = GeneratePowerOfAttorneyToPdf(
        check_id=compose.check_id,
        signers=get_signers(signers.exclude(type='signer')),
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        signed_date=signer.action_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        register_number=register_number,
        curator_name=compose.curator.full_name,
        curator_position=compose.curator.position.name,
        employee_name=compose.user.full_name,
        employee_position=compose.user.position.name,
        passport_series=compose.user.passport_seria,
        passport_number=compose.user.passport_number,
        passport_issued_date=compose.user.passport_issue_date.strftime('%d.%m.%Y'),
        passport_issued_by=compose.user.passport_issued_by,
        start_date=compose.start_date.strftime('%d.%m.%Y') if compose.start_date else '',
        end_date=compose.end_date.strftime('%d.%m.%Y') if compose.end_date else '',
        env_id=compose.company.env_id,
        old_attorney_date=old_attorney_date,
        old_attorney_number=old_attorney_number,
        old_attorney_exists=old_attorney_exists,
        employee_company=compose.user.company.name,
        document_sub_type=compose.document_sub_type_id,
        deadline_in_words=deadline_in_words,
        content=compose.content,
        short_description=compose.short_description,
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.created_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)


def register_act(compose_id, request=None):
    # Fetch the Compose instance
    compose = Compose.objects.get(id=compose_id)

    # Register the document
    register_number, num = GenerateComposeRegisterNumber(
        journal_index=compose.journal.index,
        journal_id=compose.journal_id).generate()
    base_document = create_base_document(compose, compose.created_date, register_number)

    signers = (
        Signer.objects.filter(compose_id=compose_id)
        .select_related("user__position", "user__top_level_department", "user__company__region", )
    )
    all_signers = list(signers)

    # Find employee (the author)
    employee = next(
        (s for s in all_signers if s.user_id == compose.author_id), None
    )

    # Filter signers:
    # - only type='signer'
    # - exclude the author
    filtered_signers = [
        {
            "department": s.user.top_level_department.name if s.user and s.user.top_level_department else "",
            "position": s.user.position.name if s.user and s.user.position else "",
            "full_name": normalize_user_name(s.user.full_name) if s.user else "",
        }
        for s in all_signers
        if s.type == "signer" and s.user_id != compose.author_id
    ]

    signer = signers.last()

    # Create a task for the performers
    create_assignment(base_document.id,
                      signer.user_id,
                      signer.performers,
                      signer.resolution_text,
                      resolution_type=signer.resolution_type,
                      deadline=signer.deadline)

    saved_file_id = GenerateActToPdf(
        check_id=compose.check_id,
        signers=filtered_signers,
        executor=normalize_user_name(compose.author.full_name),
        phone=compose.author.cisco if compose.author.cisco else '00-00',
        created_date=compose.created_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        signed_date=signer.action_date.astimezone().strftime('%d.%m.%Y %H:%M:%S'),
        register_number=register_number,
        register_date=format_uzbek_date(compose.created_date),
        curator_name=normalize_user_name(compose.curator.full_name),
        curator_position=compose.curator.position.name,
        employee=employee,
        employee_name=normalize_user_name(employee.user.full_name),
        env_id=compose.company.env_id,
        document_sub_type=compose.document_sub_type_id,
        content=compose.content,
        short_description=compose.short_description,
    ).generate_pdf()

    modify_compose(compose,
                   registered_document_id=base_document.id,
                   file_id=saved_file_id,
                   register_number=register_number,
                   num=num,
                   register_date=compose.created_date)
    save_pdf_and_files(compose, base_document, saved_file_id, request)


def are_all_signed_and_approved(compose_id):
    """
    This function is responsible for checking
    if all signers and negotiators have signed the document.
    """
    signers = Signer.objects.filter(compose_id=compose_id)
    approvers = Approver.objects.filter(compose_id=compose_id)

    all_signed = all(signers.values_list('is_signed', flat=True))
    all_approved = all(approvers.values_list('is_approved', flat=True))

    return all_signed and all_approved


def register_document_after_signing(compose, request, performers=None):
    """
    Register any types of documents after all signers have signed the document.
    """
    compose_id = compose.id
    if are_all_signed_and_approved(compose_id):
        doc_type_id = compose.document_type_id
        doc_sub_type_id = compose.document_sub_type_id
        DOC_TYPE_ID = CONSTANTS.DOC_TYPE_ID

        if doc_type_id == DOC_TYPE_ID.SERVICE_LETTER:
            # register the document
            register_service_letter(compose_id, request)
        elif doc_type_id == DOC_TYPE_ID.APPLICATION:
            register_application(compose_id, request, performers=performers)
        elif doc_type_id == DOC_TYPE_ID.NOTICE and doc_sub_type_id == DOC_TYPE_ID.TRIP_NOTICE:
            register_trip_notice(compose_id, request)
        elif doc_type_id == DOC_TYPE_ID.NOTICE and doc_sub_type_id in [DOC_TYPE_ID.TRIP_NOTICE_V2,
                                                                       DOC_TYPE_ID.EXTEND_TRIP_NOTICE_V2,
                                                                       DOC_TYPE_ID.BUSINESS_TRIP_NOTICE_FOREIGN]:
            register_trip_notice_v2(compose_id, request)
        elif doc_type_id == DOC_TYPE_ID.NOTICE and doc_sub_type_id in DOC_TYPE_ID.NOTICES:
            register_notice(compose_id, request)
        elif doc_type_id == DOC_TYPE_ID.HR_ORDER and doc_sub_type_id != DOC_TYPE_ID.LOCAL_BUSINESS_TRIP_ORDER:
            register_hr_order(compose_id, request, performers=performers)
        elif (
                doc_type_id == DOC_TYPE_ID.DECREE_TYPE and
                doc_sub_type_id in [DOC_TYPE_ID.TRIP_DECREE_SUB_TYPE,
                                    DOC_TYPE_ID.LOCAL_DECREE_SUB_TYPE,
                                    DOC_TYPE_ID.TRIP_DECREE_V2]
        ):
            register_decree(compose_id, request, performers=performers)
        elif doc_type_id == DOC_TYPE_ID.HR_ORDER and doc_sub_type_id == DOC_TYPE_ID.LOCAL_BUSINESS_TRIP_ORDER:
            register_local_trip_order(compose_id, request)
        elif doc_type_id == DOC_TYPE_ID.LEGAL_SERVICES:
            register_power_of_attorney(compose_id, request)
        elif doc_sub_type_id == DOC_TYPE_ID.ACT_SERVICE_CONTRACT_WORKS:
            register_act(compose_id, request)
