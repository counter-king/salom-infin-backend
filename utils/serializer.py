from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model
from rest_framework import serializers

from utils.tools import get_or_none

CREATE = 'create'
UPDATE = 'update'


class IDField(serializers.Field):
    def to_internal_value(self, data):
        if data and isinstance(data, dict):
            return data.get('id', data)
        return data


class SelectItemField(serializers.PrimaryKeyRelatedField):
    def __init__(self, model, extra_field="name", serializer_class=None, **kwargs):
        if not isinstance(model, str):
            self.Model = model
        else:
            self.Model = apps.get_model(*model.split('.'))

        kwargs['queryset'] = self.Model.objects.all() if not kwargs.get('read_only', False) else None
        kwargs['allow_null'] = not kwargs.get('required', True)

        self.extra_field = extra_field if isinstance(extra_field, (list, tuple)) else [extra_field]
        self.serializer_class = serializer_class  # Optionally pass a nested serializer
        self.dt_field = serializers.DateTimeField()
        super().__init__(**kwargs)

    def _get_cached_object(self, pk):
        # request = self.context.get('request')
        cache = self.context.setdefault('_select_cache', {})
        cache_key = f"{self.Model.__name__}:{pk}"
        if cache_key not in cache:
            try:
                cache[cache_key] = self.Model.objects.select_related().get(pk=pk)
            except self.Model.DoesNotExist:
                raise serializers.ValidationError(f"{self.Model.__name__} with ID {pk} does not exist.")
        return cache[cache_key]

    def to_internal_value(self, data):
        if self.pk_field is not None:
            data = self.pk_field.to_internal_value(data)
        if data:
            try:
                return self.get_queryset().get(pk=data)
            except ObjectDoesNotExist:
                request = self.context.get('request', None)
                get_or_none(self.Model, request, id=data)
                # self.fail('does_not_exist', pk_value=data)
            except (TypeError, ValueError):
                self.fail('incorrect_type', data_type=type(data).__name__)

    # def to_representation(self, value):
    #     item = self.Model.objects.get(pk=value.pk)
    #     result = {'id': value.pk}
    #     for extra_field in self.extra_field:
    #         if extra_field and item:
    #             v = getattr(item, extra_field, None)
    #             if isinstance(v, Model):
    #                 if hasattr(v, 'as_select_item'):
    #                     v = v.as_select_item()
    #                 else:
    #                     v = {"id": v.pk, "name": str(v)}
    #             result[extra_field] = v
    #     return result

    def to_representation(self, value):
        obj = self._get_cached_object(value.pk)

        if self.serializer_class:
            return self.serializer_class(obj, context=self.context).data

        result = {'id': obj.pk}
        for field in self.extra_field:
            v = getattr(obj, field, None)
            if isinstance(v, Model):
                v = getattr(v, "as_select_item", lambda: {"id": v.pk, "name": str(v)})()
            result[field] = v
        return result


def serialize_m2m(type, model, field, data, instance=None):
    def get_id(item):
        if isinstance(item, dict):
            return item.get("id")
        return item

    if type == CREATE:
        if data:
            for item in data:
                try:
                    obj_id = get_id(item)
                    obj = model.objects.get(id=obj_id)
                    getattr(instance, field).add(obj)
                except ObjectDoesNotExist:
                    pass
    elif type == UPDATE:
        getattr(instance, field).clear()
        if data:
            for item in data:
                try:
                    obj_id = get_id(item)
                    obj = model.objects.get(id=obj_id)
                    getattr(instance, field).add(obj)
                except ObjectDoesNotExist:
                    pass
