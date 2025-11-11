import csv
import time

from django.core.management.base import BaseCommand, CommandError

from apps.user.models import User
from apps.company.models import Department, Company, Position


class Command(BaseCommand):
    help = 'Exporting employees from CSV to Workzone'

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='+', type=str)

    def handle(self, *args, **options):
        file_name = options['file'][0]
        file_path = f'users/{file_name}'

        with open(file_path) as f:
            reader = csv.reader(f, delimiter=';')
            start = time.time()
            new_count = 0

            for row in reader:
                try:
                    dept = Department.objects.get(code=int(row[5]))
                except Department.DoesNotExist as e:
                    dept = None

                try:
                    top_dept = Department.objects.get(code=int(row[6]))
                except Department.DoesNotExist as e:
                    top_dept = None

                try:
                    company = Company.objects.get(code=int(row[7]))
                except Company.DoesNotExist as e:
                    company = None

                try:
                    position = Position.objects.get(code=int(row[8]))
                except Position.DoesNotExist as e:
                    position = None

                user = User()
                user.first_name = row[0]
                user.last_name = row[1]
                user.father_name = row[2]
                user.pinfl = row[3]
                user.table_number = row[4]
                user.department_id = dept.id if dept else None
                user.top_level_department_id = top_dept.id if top_dept else None
                user.company_id = company.id if company else None
                user.position_id = position.id if position else None
                user.phone = row[9]
                user.username = row[9]
                user.save()
                new_count += 1

            end_time = time.time() - start

        self.stdout.write(self.style.SUCCESS('Successfully employees migrated in %s seconds' % str(end_time)))
        self.stdout.write(self.style.SUCCESS('New added users count %s' % str(new_count)))
