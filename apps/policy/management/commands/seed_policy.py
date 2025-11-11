from django.core.management.base import BaseCommand

from apps.policy.models import Resource, Action, Role


class Command(BaseCommand):
    help = "Seed common Resources, Actions, and example Roles"

    def handle(self, *args, **kwargs):
        resources = [
            ("compose.document", "Compose documents"),
            ("news", "News items"),
            ("attendance.daily_summary", "Daily attendance summaries"),
            ("employee", "Employee profiles"),
            ("department", "Departments"),
            ("hr.payroll", "Payroll"),
        ]
        actions = ["view", "list", "create", "update", "delete", "export", "approve"]

        for key, desc in resources:
            Resource.objects.get_or_create(key=key, defaults={"description": desc})

        for k in actions:
            Action.objects.get_or_create(key=k, defaults={"description": k.title()})

        Role.objects.get_or_create(name="Compose Admin", defaults={"description": "Full access to compose"})
        Role.objects.get_or_create(name="Compose Editor", defaults={"description": "Create/Update in scope"})
        Role.objects.get_or_create(name="Compose Viewer", defaults={"description": "View in scope"})

        self.stdout.write(self.style.SUCCESS("Access control seeded."))
