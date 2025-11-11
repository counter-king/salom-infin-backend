from django.db import models

from base_model.models import BaseModel
from utils.constants import CONSTANTS


class TripPlan(BaseModel):
    compose = models.ForeignKey('compose.Compose',
                                on_delete=models.CASCADE,
                                null=True, blank=True,
                                related_name='trip_plans')
    text = models.TextField(null=True, blank=True)
    users = models.ManyToManyField('user.User', blank=True)

    def __str__(self):
        return f'{self.id}'


class BusinessTrip(BaseModel):
    STATUS_CHOICES = [
        ('not_started', 'Boshlanmagan'),
        ('on_trip', 'Xizmat safarida'),
        ('reporting', 'Hisobot topshrish'),
        ('closed', 'Yakunlangan'),
    ]

    notice = models.ForeignKey('compose.Compose',
                               on_delete=models.SET_NULL,
                               null=True, blank=True,
                               related_name='notices')
    order = models.ForeignKey('compose.Compose',
                              on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name='orders')
    travel_paper = models.ForeignKey('compose.Compose',
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='travel_papers')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    end_date_2 = models.DateField(null=True, blank=True)
    locations = models.ManyToManyField('reference.Region', blank=True)
    countries = models.ManyToManyField('reference.Country', blank=True)
    destinations = models.ManyToManyField('company.Company', blank=True)
    tags = models.ManyToManyField('compose.Tag', blank=True)
    user = models.ForeignKey('user.User',
                             on_delete=models.SET_NULL,
                             null=True, blank=True)
    route = models.CharField(max_length=30, null=True, blank=True,
                             choices=CONSTANTS.COMPOSE.TRIP_ROUTE.CHOICES,
                             default=CONSTANTS.COMPOSE.TRIP_ROUTE.DEFAULT)
    company = models.ForeignKey('company.Company',
                                on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='company')
    sender_company = models.ForeignKey('company.Company',
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='sender_company')
    group_id = models.PositiveIntegerField(default=1)
    trip_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    trip_type = models.CharField(max_length=20, null=True, blank=True,
                                 choices=CONSTANTS.COMPOSE.TRIP_TYPE.CHOICES,
                                 default=CONSTANTS.COMPOSE.TRIP_TYPE.DEFAULT)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self):
        return '{} {}'.format(self.user.first_name, self.user.last_name)


class Booking(BaseModel):
    type = models.CharField(max_length=25,
                            choices=CONSTANTS.COMPOSE.BOOKING_TYPE.CHOICES,
                            default=CONSTANTS.COMPOSE.BOOKING_TYPE.DEFAULT)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    compose = models.ForeignKey('compose.Compose',
                                on_delete=models.CASCADE,
                                null=True, blank=True, related_name='bookings')
    route = models.CharField(max_length=30, null=True, blank=True,
                             choices=CONSTANTS.COMPOSE.TRIP_ROUTE.CHOICES,
                             default=CONSTANTS.COMPOSE.TRIP_ROUTE.DEFAULT)

    def __str__(self):
        return f'{self.id}'


class BookingSegment(BaseModel):
    booking = models.ForeignKey(Booking,
                                on_delete=models.CASCADE,
                                null=True, blank=True,
                                related_name='segments')
    departure_city = models.ForeignKey('reference.Region',
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='departure')
    arrival_city = models.ForeignKey('reference.Region',
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='arrival')
    departure_date = models.DateTimeField(null=True, blank=True)
    departure_end_date = models.DateTimeField(null=True, blank=True)
    arrival_date = models.DateTimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    segment_class = models.CharField(max_length=20,
                                     choices=CONSTANTS.COMPOSE.BOOKING_CLASS.CHOICES,
                                     default=CONSTANTS.COMPOSE.BOOKING_CLASS.DEFAULT,
                                     null=True, blank=True)
    flight_number = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f'{self.booking.type}'


class Passenger(BaseModel):
    booking = models.ForeignKey(Booking,
                                on_delete=models.CASCADE,
                                null=True, blank=True,
                                related_name='passengers')
    user = models.ForeignKey('user.User',
                             on_delete=models.SET_NULL,
                             null=True, blank=True)

    def __str__(self):
        return f'{self.id}'


class TripVerification(BaseModel):
    trip = models.ForeignKey(BusinessTrip, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='trip')
    verified = models.BooleanField(null=True, blank=True)
    action_date = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    left_verified_by = models.ForeignKey('user.User', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='left')
    arrived_verified_by = models.ForeignKey('user.User', on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name='arrived')
    company = models.ForeignKey('company.Company', on_delete=models.SET_NULL,
                                null=True, blank=True)
    region = models.ForeignKey('reference.Region', on_delete=models.SET_NULL,
                               null=True, blank=True)
    is_sender = models.BooleanField(default=False)
    next_destination_type = models.CharField(max_length=100, null=True, blank=True,
                                             choices=CONSTANTS.COMPOSE.DESTINATION_TYPES.CHOICES)
    next_destination_id = models.PositiveIntegerField(null=True, blank=True)
    arrived_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    arrived_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    arrived_address = models.CharField(max_length=255, null=True, blank=True)
    left_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    left_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    left_address = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'{self.id}'


class TripPlace(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return ''.format(self.name)


class VisitedPlace(BaseModel):
    trip_verification = models.ForeignKey(TripVerification,
                                          on_delete=models.CASCADE,
                                          null=True,
                                          related_name='visited_places')
    place = models.ForeignKey(TripPlace,
                              on_delete=models.SET_NULL,
                              null=True)

    def __str__(self):
        return ''.format(self.place)


class TripExpense(BaseModel):
    trip = models.ForeignKey(BusinessTrip, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    type = models.ForeignKey('reference.ExpenseType', on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    file = models.ForeignKey('document.File', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.type}'
