import random
from faker import Faker
from django.utils.crypto import get_random_string

from apps.user.models import User

fake = Faker()


def department_id():
    numbers = [9, 13, 20, 25]

    while True:
        random.shuffle(numbers)  # Shuffle the numbers
        for num in numbers:
            yield num  # Yield each number one by one


def shuffle_position():
    positions = [5, 6, 7, 8, 9, 10, 11, 12]

    while True:
        random.shuffle(positions)
        for pos in positions:
            yield pos


def run():
    for _ in range(200):
        phone = str(fake.phone_number())
        department = department_id()
        dept_id = next(department)

        User.objects.create(
            username=phone,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            father_name=fake.first_name(),
            phone=phone,
            pinfl=str(fake.random_number(14)),
            table_number=str(fake.random_number(6)),
            tin=str(fake.random_number(9)),
            email=fake.email(),
            status_id=1,
            department_id=dept_id,
            top_level_department_id=dept_id,
            company_id=16,
            position_id=next(shuffle_position()),
            is_registered=True,
        )
