from rest_framework import serializers
from apps.hr.models import (
    Payroll,
    PayrollCategory
)


class PayrollSummaryResponseSerializer(serializers.Serializer):
    """
    Serializer for Payroll Summary Response
    """
    main_office = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        allow_null=True, required=False
    )
    branches = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        allow_null=True, required=False
    )


class PayrollCategorySerializer(serializers.Serializer):
    """
    Serializer for Payroll Category
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, required=False)
