from rest_framework import serializers

from apps.document.models import File


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ('id', 'name', 'url', 'module', 'created_date', 'size',
                  'size_', 'extension', 'peaks', 'duration')
        read_only_fields = ('name', 'id', 'url', 'module', 'created_date',
                            'size', 'size_', 'extension', 'peaks', 'duration')

    def to_internal_value(self, data):
        return data.get('id')
