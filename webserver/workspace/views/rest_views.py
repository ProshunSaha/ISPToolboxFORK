from django.shortcuts import render
from django.views import View
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from workspace.models import Network, AccessPointLocation, AccessPointCoverage
from gis_data.models import MsftBuildingOutlines
from workspace import serializers
from workspace.forms import NetworkForm
from django.http import HttpResponseRedirect
from django.db.models import Count
from rest_framework import generics
from django.contrib.auth.forms import AuthenticationForm
from IspToolboxAccounts.forms import IspToolboxUserCreationForm
from rest_framework import generics, mixins, renderers, response
from django.http import JsonResponse
from rest_framework.response import Response
import json


# REST Views
class NetworkDetail(mixins.ListModelMixin,
                  mixins.CreateModelMixin,
                  mixins.UpdateModelMixin,
                  generics.RetrieveAPIView):
    serializer_class = serializers.NetworkSerializer

    def get_queryset(self):
        user = self.request.user
        return Network.objects.filter(owner=user)
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class AccessPointLocationListCreate(mixins.ListModelMixin,
                  mixins.CreateModelMixin,
                  generics.GenericAPIView):
    serializer_class = serializers.AccessPointSerializer
    renderer_classes = [renderers.TemplateHTMLRenderer]
    lookup_field = 'uuid'
    template_name = "workspace/molecules/access_point_pagination.html"

    def get_queryset(self):
        user = self.request.user
        return AccessPointLocation.objects.filter(owner=user)
    
    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({'serializer': serializer, 'data': serializer.data})

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class AccessPointLocationGet(mixins.RetrieveModelMixin, generics.GenericAPIView):
    serializer_class = serializers.AccessPointSerializer
    lookup_field = 'uuid'

    def get_queryset(self):
        user = self.request.user
        return AccessPointLocation.objects.filter(owner=user)
    
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class AccessPointCoverageResults(View):
    def get(self, request, uuid):
        ap = AccessPointLocation.objects.filter(owner=request.user, uuid=uuid).get()
        coverage = AccessPointCoverage.objects.filter(ap=ap).get()
        features = []
        for building in coverage.nearby_buildings.all():
            feature = {
                "type": "Feature",
                "geometry": json.loads(
                    MsftBuildingOutlines.objects.get(id=building.msftid).geog.json
                ),
                "properties": {
                    "serviceable": building.status,
                }
            }
            features.append(feature)
        fc = {'type': 'FeatureCollection', 'features': features}
        return JsonResponse(fc)
