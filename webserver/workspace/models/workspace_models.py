from django.db import models
from django.conf import settings
from rest_framework import serializers
import time


class ISPCompany(models.Model):
    name = models.CharField(max_length=128)
    employees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='Employee')


class Employee(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    company = models.ForeignKey(ISPCompany, on_delete=models.CASCADE)
    date_joined = models.DateField()


class AnalyticsEvent(models.Model):
    url = models.TextField()
    session_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=255)
    created_at = models.CharField(max_length=255, default=int(time.time()))


class AnalyticsSerializer(serializers.ModelSerializer):
    id = serializers.CharField()
    url = serializers.CharField()
    session_id = serializers.CharField()
    event_type = serializers.CharField()
    created_at = serializers.CharField()

    class Meta:
        model = AnalyticsEvent
        fields = ("__all__")
