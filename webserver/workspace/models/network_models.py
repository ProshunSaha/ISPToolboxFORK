from typing import List
from urllib.parse import urlparse
from django.contrib.gis.db.models.fields import GeometryField
from django.contrib.gis.geos.point import Point
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.conf import settings
from django.contrib.gis.db import models as geo_models
from django.contrib.gis.geos import GEOSGeometry, LineString, Polygon
from django.contrib.sessions.models import Session
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from gis_data.models import MsftBuildingOutlines

from rest_framework import serializers


import csv
import logging
import math
import json
import re
import random
import uuid
from workspace.models.task_models import (
    AbstractAsyncTaskAssociatedModel,
    AbstractAsyncTaskHashCacheMixin,
    AbstractAsyncTaskPrimaryKeyMixin,
    AsyncTaskStatus,
)
from workspace.models.validators import validate_ptp_link_geometry

from workspace.utils.geojson_circle import createGeoJSONCircle, createGeoJSONSector
from .model_constants import (
    EARTH_RADIUS_M,
    FREQUENCY_CHOICES,
    KM_2_MI,
    FeatureType,
    M_2_FT,
    ModelLimits,
    SPEED_OF_LIGHT
)
from mmwave.lidar_utils.LidarEngine import LidarEngine, LidarResolution, LIDAR_RESOLUTION_DEFAULTS

from mmwave.tasks.link_tasks import getDTMPoint, getElevationProfile
from mmwave.models import EPTLidarPointCloud
from mmwave.lidar_utils.DSMTileEngine import DSMTileEngine
from celery_async import celery_app as app


BUFFER_DSM_EXPORT_KM = 0.5


class WorkspaceFeature(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        help_text="This is a django session - different than map session",
        db_column="django_session",
    )

    map_session = models.ForeignKey(
        "workspace.WorkspaceMapSession",
        on_delete=models.CASCADE,
        null=True,
        default=None,
        db_column="session",
    )
    geojson = geo_models.PointField()
    uneditable = models.BooleanField(default=False)
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @classmethod
    def get_rest_queryset(cls, request):
        user = request.user
        if request.user.is_anonymous:
            return cls.objects.filter(session=request.session.session_key)
        else:
            return cls.objects.filter(owner=user) | cls.objects.filter(
                session=request.session.session_key
            )


class SessionWorkspaceModelMixin:
    @classmethod
    def get_features_for_session(serializer, session, objects=None):
        if not objects:
            objects = serializer.Meta.model.objects.filter(map_session=session).all()

        # Filter out all geometryfield model properties from properties.
        features = []
        for obj in objects:
            if obj.map_session == session:
                properties = {}
                for k, v in serializer(obj).data.items():

                    # Some keys might be properties, not fields
                    try:
                        model_field_type = obj._meta.get_field(k)
                    except FieldDoesNotExist:
                        model_field_type = None

                    if not isinstance(model_field_type, GeometryField):
                        # UUIDs not being serializable are annoying
                        if isinstance(v, uuid.UUID):
                            properties[k] = str(v)
                        else:
                            properties[k] = v

                features.append(
                    {
                        "type": "Feature",
                        "geometry": json.loads(obj.geojson.json),
                        "properties": properties,
                    }
                )

        return {"type": "FeatureCollection", "features": features}


class UnitPreferencesModelMixin:
    @property
    def get_units(self):
        from workspace.models.session_models import WorkspaceMapSession
        return self.map_session.units if self.map_session else WorkspaceMapSession.UnitPreferences.METRIC


# TODO: Remove this after AP sectors launches
class AccessPointSectorSerializerValidatorMixin(serializers.Serializer):
    """
    Mixin for validating that one of either AP or Sector is defined
    """

    def validate(self, data):
        # Get the UUID from the request. POST requests don't have UUIDs, but
        # others do
        request = self.context["request"]
        if request.method == "POST":
            uuid = None
            ap = data.get("ap", None)
            sector = data.get("sector", None)
        else:
            path = urlparse(request.get_full_path()).path
            uuid = path.split("/")[-2]
            instance = self.Meta.model.objects.get(uuid=uuid)
            ap = data.get("ap", instance.ap)
            sector = data.get("sector", instance.sector)

        if not ap and not sector:
            raise serializers.ValidationError("Must have one of ap or sector")
        elif ap and sector:
            raise serializers.ValidationError("Cannot have both ap and sector")
        else:
            return data


class AccessPointLocation(UnitPreferencesModelMixin, WorkspaceFeature):
    name = models.CharField(
        max_length=ModelLimits.NAME.max,
        default="Unnamed Tower",
        validators=[
            MinLengthValidator(
                int(ModelLimits.NAME.min),
                message=_(
                    "Ensure this value has length of at least %(limit_value)s characters."
                ),
            ),
            MaxLengthValidator(
                int(ModelLimits.NAME.max),
                message=_(
                    "Ensure this value has length at most %(limit_value)s characters."
                ),
            ),
        ],
    )

    # TODO: deprecate height, radius, no_check_radius, default_cpe_height after AP sector launch
    height = models.FloatField(
        default=ModelLimits.HEIGHT.default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )
    max_radius = models.FloatField(
        default=ModelLimits.RADIUS.default,
        validators=[
            MinValueValidator(
                ModelLimits.RADIUS.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s km."
                ),
            ),
            MaxValueValidator(
                ModelLimits.RADIUS.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. km"
                ),
            ),
        ],
    )
    no_check_radius = models.FloatField(
        default=ModelLimits.RADIUS.no_check_radius_default
    )
    default_cpe_height = models.FloatField(
        default=ModelLimits.HEIGHT.cpe_default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )

    @property
    def lat(self):
        return self.geojson.y

    @property
    def lng(self):
        return self.geojson.x

    @property
    def radius(self):
        return self.max_radius

    @radius.setter
    def radius(self, val):
        self.max_radius = val

    @property
    def radius_miles(self):
        return self.max_radius * KM_2_MI

    @radius_miles.setter
    def radius_miles(self, val):
        self.max_radius = val / KM_2_MI

    @property
    def observer(self):
        return self.geojson

    @property
    def height_ft(self):
        return self.height * M_2_FT

    @height_ft.setter
    def height_ft(self, val):
        self.height = val / M_2_FT

    @property
    def default_cpe_height_ft(self):
        return self.default_cpe_height * M_2_FT

    @default_cpe_height_ft.setter
    def default_cpe_height_ft(self, val):
        self.default_cpe_height = val / M_2_FT

    @property
    def feature_type(self):
        return FeatureType.AP.value

    @property
    def coordinates(self):
        return f"{self.geojson.y}, {self.geojson.x}"

    @coordinates.setter
    def coordinates(self, value):
        try:
            coords = value.split(",")
            self.geojson.x = float(coords[1])
            self.geojson.y = float(coords[0])
        except Exception:
            logging.exception("failed to parse coordinates")

    @property
    def sector_count(self):
        return self.accesspointsector_set.count()

    @classmethod
    def coordinates_validator(cls, value):
        coords = value.split(",")
        if len(coords) != 2:
            raise ValidationError(
                "Coordinates must contain two values seperated by a comma. Latitude, Longitude"
            )
        if float(coords[0]) > 90.0 or float(coords[0]) < -90.0:
            raise ValidationError(
                "Invalid latitude, latitude must be between -90 and 90."
            )
        if float(coords[1]) > 180.0 or float(coords[1]) < -180.0:
            raise ValidationError(
                "Invalid longitude, longitude must be between -180 and 180."
            )

    def get_dtm_height(self) -> float:
        return getDTMPoint(self.geojson)

    def getDSMExtentRequired(self):
        """
        Get the AOI necessary to render AP location
        """
        geo_circle = createGeoJSONCircle(self.geojson, self.max_radius)
        aoi = GEOSGeometry(json.dumps(geo_circle))
        return aoi

    def createDSMJobEnvelope(self):
        """
        Get the suggest aoi to export w/ buffer
        """
        geo_circle = createGeoJSONCircle(
            self.geojson, self.max_radius + BUFFER_DSM_EXPORT_KM
        )
        aoi = GEOSGeometry(json.dumps(geo_circle))
        return aoi.envelope


@receiver(post_save, sender=AccessPointLocation)
def _calculate_coverage_tower(
    sender, instance, created, raw, using, update_fields, **kwargs
):
    """
    Update coverage after modifying AP location
    """
    app.send_task("workspace.tasks.viewshed_tasks.updateSectors", (instance.uuid,))


@receiver(pre_delete, sender=AccessPointLocation)
def _cancel_access_point_loc_task(sender, instance, using, **kwargs):
    """
    Cancel coverage task for deleted sectors
    """
    try:
        AccessPointCoverageBuildings.objects.get(ap=instance).cancel_task()
    except AccessPointCoverageBuildings.DoesNotExist:
        pass


class AccessPointSerializer(serializers.ModelSerializer, SessionWorkspaceModelMixin):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(
        format="%D", required=False, read_only=True
    )
    height_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT_FT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT_FT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )
    radius_miles = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.RADIUS_MILES.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s mi."
                ),
            ),
            MaxValueValidator(
                ModelLimits.RADIUS_MILES.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s mi."
                ),
            ),
        ],
    )
    coordinates = serializers.CharField(
        required=False, validators=[AccessPointLocation.coordinates_validator]
    )
    feature_type = serializers.CharField(read_only=True)
    default_cpe_height_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT_FT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT_FT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )
    lat = serializers.FloatField(read_only=True)
    lng = serializers.FloatField(read_only=True)
    sector_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AccessPointLocation
        exclude = ["owner", "session", "created"]


def random_heading():
    return random.randint(ModelLimits.HEADING.min, ModelLimits.HEADING.max)


class AccessPointSector(UnitPreferencesModelMixin, WorkspaceFeature):
    name = models.CharField(max_length=50, default="Unnamed AP")

    # TODO: restore default once we add sector draw mode.
    heading = models.FloatField(
        default=random_heading,
        validators=[
            MinValueValidator(
                ModelLimits.HEADING.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s degrees."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEADING.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s degrees."
                ),
            ),
        ],
    )

    azimuth = models.FloatField(
        default=ModelLimits.AZIMUTH.default,
        validators=[
            MinValueValidator(
                ModelLimits.AZIMUTH.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s degrees."
                ),
            ),
            MaxValueValidator(
                ModelLimits.AZIMUTH.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s degrees."
                ),
            ),
        ],
    )

    height = models.FloatField(
        default=ModelLimits.HEIGHT.default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )

    default_cpe_height = models.FloatField(
        default=ModelLimits.HEIGHT.cpe_default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )

    radius = models.FloatField(
        default=ModelLimits.RADIUS.default,
        validators=[
            MinValueValidator(
                ModelLimits.RADIUS.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s km."
                ),
            ),
            MaxValueValidator(
                ModelLimits.RADIUS.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. km"
                ),
            ),
        ],
    )

    uneditable = models.BooleanField(default=True)
    frequency = models.FloatField(
        default=ModelLimits.FREQUENCY.default,
        validators=[
            MinValueValidator(ModelLimits.FREQUENCY.min),
            MaxValueValidator(ModelLimits.FREQUENCY.max),
        ],
    )
    ap = models.ForeignKey(
        AccessPointLocation, on_delete=models.CASCADE, editable=False
    )

    @property
    def radius_miles(self):
        return self.radius * KM_2_MI

    @radius_miles.setter
    def radius_miles(self, val):
        self.radius = val / KM_2_MI

    @property
    def max_radius(self):
        return self.radius

    @max_radius.setter
    def max_radius(self, val):
        self.radius = val

    @property
    def observer(self):
        return self.ap.geojson

    @property
    def default_cpe_height_ft(self):
        return self.default_cpe_height * M_2_FT

    @default_cpe_height_ft.setter
    def default_cpe_height_ft(self, val):
        self.default_cpe_height = val / M_2_FT

    @property
    def height_ft(self):
        return self.height * M_2_FT

    @height_ft.setter
    def height_ft(self, val):
        self.height = val / M_2_FT

    @property
    def feature_type(self):
        return FeatureType.AP_SECTOR.value

    def get_sector_geojson_json(self, buffer_radius=0):
        center = self.ap.geojson
        start_bearing = (self.heading - self.azimuth / 2) % 360
        end_bearing = (self.heading + self.azimuth / 2) % 360
        return createGeoJSONSector(
            center, self.radius + buffer_radius, start_bearing, end_bearing
        )

    @property
    def geojson(self):
        return Polygon(*self.get_sector_geojson_json()["coordinates"])

    def get_dtm_height(self) -> float:
        return getDTMPoint(self.ap.geojson)

    def getDSMExtentRequired(self):
        """
        Get the AOI necessary to render AP location
        """
        geo_sector = self.get_sector_geojson_json()
        aoi = GEOSGeometry(json.dumps(geo_sector))
        return aoi

    def createDSMJobEnvelope(self):
        """
        Get the suggest aoi to export w/ buffer
        """
        geo_sector = self.get_sector_geojson_json(buffer_radius=BUFFER_DSM_EXPORT_KM)
        aoi = GEOSGeometry(json.dumps(geo_sector))
        return aoi.envelope

    @staticmethod
    def _wrap_geojson(geojson):
        """Wrap geojson for turfpy functions"""
        if isinstance(geojson, str):
            geometry = json.loads(geojson)
        else:
            geometry = geojson
        return {"geometry": geometry}

    def intersects(self, lng_lat, units="METRIC"):
        """
        Determines if the point specified intersects with this sector.
        """
        from turfpy import measurement
        start = AccessPointSector._wrap_geojson(self.ap.geojson.json)
        end = AccessPointSector._wrap_geojson(lng_lat)
        start_bearing = (self.heading - self.azimuth / 2) % 360
        end_bearing = (self.heading + self.azimuth / 2) % 360
        bearing = measurement.bearing(start, end) % 360

        # If end_bearing is less than or equal to start_bearing, that means we go through 0.
        # Check if the angle is between end and start bearing for exclusion
        if end_bearing <= start_bearing:
            if bearing >= end_bearing and bearing <= start_bearing:
                return False
        elif not (bearing >= start_bearing and bearing <= end_bearing):
            return False

        distance = self.distance(lng_lat, units)
        if units == "METRIC":
            max_distance = self.radius
        else:
            max_distance = self.radius_miles

        return distance <= max_distance

    def distance(self, lng_lat, units="METRIC"):
        from turfpy import measurement
        start = AccessPointSector._wrap_geojson(self.ap.geojson.json)
        end = AccessPointSector._wrap_geojson(lng_lat)
        if units == "METRIC":
            return measurement.distance(start, end)
        else:
            return measurement.distance(start, end, units="mi")

    def create_serviceable_download(self, fp):
        writer = csv.writer(fp)
        buildings = self.building_coverage.buildingcoverage_set.all()
        nearby_ids = [b.msftid for b in buildings]
        msft_buildings = MsftBuildingOutlines.objects.filter(id__in=nearby_ids).all()
        msft_buildings = {b.id: b.geog for b in msft_buildings}
        writer.writerow(["", "latitude", "longitude", "status"])
        for idx, b in enumerate(buildings):
            geog = b.geog
            if not geog:
                geog = msft_buildings.get(b.msftid, Polygon())
            try:
                writer.writerow([idx, geog.centroid[1], geog.centroid[0], b.status])
            except Exception:
                logging.exception(f"failed to export {b.id}")


@receiver(post_save, sender=AccessPointSector)
def _calculate_coverage(sender, instance, created, raw, using, update_fields, **kwargs):
    """
    Calculate coverage for sector after saving
    """
    app.send_task(
        "workspace.tasks.sector_tasks.calculateSectorViewshed", (instance.uuid,)
    )


class AccessPointSectorSerializer(
    serializers.ModelSerializer, SessionWorkspaceModelMixin
):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(
        format="%D", required=False, read_only=True
    )
    height_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT_FT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT_FT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )

    radius_miles = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.RADIUS_MILES.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s mi."
                ),
            ),
            MaxValueValidator(
                ModelLimits.RADIUS_MILES.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s mi."
                ),
            ),
        ],
    )

    frequency = serializers.ChoiceField(
        choices=FREQUENCY_CHOICES, default=FREQUENCY_CHOICES[0][0]
    )
    feature_type = serializers.CharField(read_only=True)
    default_cpe_height_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT_FT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT_FT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )

    ap = serializers.PrimaryKeyRelatedField(
        queryset=AccessPointLocation.objects.all(), pk_field=serializers.UUIDField()
    )
    geojson_json = serializers.SerializerMethodField()

    class Meta:
        model = AccessPointSector
        exclude = ["owner", "session", "created"]

    def update(self, instance, validated_data):
        # Update frequencies here so that we don't do this update every time the sector
        # is updated.
        new_frequency = validated_data.get("frequency", instance.frequency)
        if not math.isclose(new_frequency, instance.frequency):
            APToCPELink.objects.filter(sector=instance).update(frequency=new_frequency)

        return super(AccessPointSectorSerializer, self).update(instance, validated_data)

    def get_geojson_json(self, obj):
        return obj.geojson.json


class CPELocation(UnitPreferencesModelMixin, WorkspaceFeature):
    name = models.CharField(max_length=100)

    # TODO: Deprecate this field
    ap = models.ForeignKey(
        AccessPointLocation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
    )

    sector = models.ForeignKey(
        AccessPointSector, on_delete=models.CASCADE, null=True, blank=True, default=None
    )

    height = models.FloatField(
        help_text="""
        This height value is relative to the terrain in meters. When object is first created the height field
        is taken from the AP "default_cpe_height", it is then converted to DTM height. The following
        saves are all relative to terrain.
        """,
        validators=[
            MinValueValidator(ModelLimits.HEIGHT.min),
            MaxValueValidator(ModelLimits.HEIGHT.max),
        ],
    )

    @property
    def feature_type(self):
        return FeatureType.CPE.value

    def get_dsm_height(self) -> float:
        point = self.geojson
        tile_engine = DSMTileEngine(
            point, EPTLidarPointCloud.query_intersect_aoi(point)
        )
        dsm = tile_engine.getSurfaceHeight(point)
        return dsm

    def get_dtm_height(self) -> float:
        return getDTMPoint(self.geojson)

    @property
    def height_ft(self):
        return self.height * M_2_FT

    @height_ft.setter
    def height_ft(self, value):
        self.height = value / M_2_FT


@receiver(pre_save, sender=CPELocation)
def _modify_height(sender, instance, **kwargs):
    """
    Modify the height when initially created to be relative to terrain.
    """
    default_reference = instance.ap if instance.ap else instance.sector
    if instance.created is None:
        if instance.height is None:
            instance.height = default_reference.default_cpe_height_ft

        try:
            instance.height = (
                instance.get_dsm_height() - instance.get_dtm_height() + instance.height
            )
        except Exception as e:
            logging.error(f"Exception when modifying height: {e}")
            instance.height = default_reference.default_cpe_height_ft


class CPESerializer(
    serializers.ModelSerializer,
    SessionWorkspaceModelMixin,
    AccessPointSectorSerializerValidatorMixin,
):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(format="%m/%d/%Y %-I:%M%p", required=False)
    height = serializers.FloatField(required=False)
    height_ft = serializers.FloatField(required=False)
    feature_type = serializers.CharField(read_only=True)

    # TODO: Remove ap
    ap = serializers.PrimaryKeyRelatedField(
        queryset=AccessPointLocation.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
        default=None,
    )
    sector = serializers.PrimaryKeyRelatedField(
        queryset=AccessPointSector.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = CPELocation
        exclude = ["owner", "session", "created"]


class APToCPELink(UnitPreferencesModelMixin, WorkspaceFeature):
    frequency = models.FloatField(
        default=ModelLimits.FREQUENCY.default,
        validators=[
            MinValueValidator(ModelLimits.FREQUENCY.min),
            MaxValueValidator(ModelLimits.FREQUENCY.max),
        ],
    )

    # TODO: Deprecate this field
    ap = models.ForeignKey(
        AccessPointLocation,
        on_delete=models.CASCADE,
        editable=False,
        null=True,
        blank=True,
        default=None,
    )

    sector = models.ForeignKey(
        AccessPointSector, on_delete=models.CASCADE, null=True, blank=True, default=None
    )

    cpe = models.ForeignKey(CPELocation, on_delete=models.CASCADE, editable=False)

    @property
    def geojson(self):
        if self.ap:
            ap = self.ap.geojson
        else:
            ap = self.sector.ap.geojson
        return LineString(ap, self.cpe.geojson, srid=ap.srid)

    @property
    def feature_type(self):
        return FeatureType.AP_CPE_LINK.value


@receiver(pre_save, sender=APToCPELink)
def _modify_frequency(sender, instance, **kwargs):
    """
    Modify the frequency to be equal to sector frequency.
    """
    if instance.sector:
        instance.frequency = instance.sector.frequency


class APToCPELinkSerializer(
    serializers.ModelSerializer,
    SessionWorkspaceModelMixin,
    AccessPointSectorSerializerValidatorMixin,
):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(format="%m/%d/%Y %-I:%M%p", required=False)
    feature_type = serializers.CharField(read_only=True)

    # TODO: Remove ap
    ap = serializers.PrimaryKeyRelatedField(
        queryset=AccessPointLocation.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
        default=None,
    )
    sector = serializers.PrimaryKeyRelatedField(
        queryset=AccessPointSector.objects.all(),
        pk_field=serializers.UUIDField(),
        required=False,
        allow_null=True,
        default=None,
    )

    frequency = serializers.ChoiceField(
        choices=FREQUENCY_CHOICES, default=FREQUENCY_CHOICES[0][0]
    )
    cpe = serializers.PrimaryKeyRelatedField(
        queryset=CPELocation.objects.all(), pk_field=serializers.UUIDField()
    )

    class Meta:
        model = APToCPELink
        exclude = ["owner", "session", "created"]


class PointToPointLink(UnitPreferencesModelMixin, WorkspaceFeature):
    DEFAULT_NUMBER_SAMPLES = 512

    frequency = models.FloatField(
        default=ModelLimits.FREQUENCY.default,
        validators=[
            MinValueValidator(ModelLimits.FREQUENCY.min),
            MaxValueValidator(ModelLimits.FREQUENCY.max),
        ],
    )
    geojson = geo_models.LineStringField(validators=[validate_ptp_link_geometry])

    radio0hgt = models.FloatField(
        default=ModelLimits.HEIGHT.ptp_default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )
    radio1hgt = models.FloatField(
        default=ModelLimits.HEIGHT.ptp_default,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s m."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s. m"
                ),
            ),
        ],
    )

    @property
    def radio0hgt_ft(self):
        return self.radio0hgt * M_2_FT

    @radio0hgt_ft.setter
    def radio0hgt_ft(self, val):
        self.radio0hgt = val / M_2_FT

    @property
    def radio1hgt_ft(self):
        return self.radio1hgt * M_2_FT

    @radio1hgt_ft.setter
    def radio1hgt_ft(self, val):
        self.radio1hgt = val / M_2_FT

    @property
    def feature_type(self):
        return FeatureType.PTP_LINK.value

    def get_dtm_heights(self) -> List[float]:
        return [
            getDTMPoint(Point(self.geojson[0], srid=self.geojson.srid)),
            getDTMPoint(Point(self.geojson[1], srid=self.geojson.srid)),
        ]

    @property
    def distance(self):
        from geopy.distance import distance as geopy_distance
        from geopy.distance import lonlat
        return geopy_distance(
            lonlat(
                self.geojson[0][0],
                self.geojson[0][1]
            ),
            lonlat(
                self.geojson[1][0],
                self.geojson[1][1]
            )
        ).meters

    class PointToPointGisData:
        """
        Helper class to hold GIS data relevant to link
        """
        def __init__(
            self, lidar: List[float], fresnel: List[float], elevation: List[float],
            profile: List[float],
        ):
            self.lidar = lidar
            self.fresnel = fresnel
            self.profile = profile
            self.elevation = elevation

        def __str__(self):
            return json.dumps({
                'lidar': self.lidar,
                'fresnel': self.fresnel,
                'profile': self.profile,
                'elevation': self.elevation
            })

    def gis_data(self):
        return PointToPointLink.PointToPointGisData(
            self.calculate_lidar(),
            self.calculate_fresnel(),
            self.calculate_elevation(),
            self.calculate_profile(),
        )

    def calculate_elevation(self):
        return [v['elevation'] for v in getElevationProfile(
            Point(self.geojson[0]),
            Point(self.geojson[1]),
            PointToPointLink.DEFAULT_NUMBER_SAMPLES
        )]

    def calculate_lidar(self):
        le = LidarEngine(
            self.geojson,
            LIDAR_RESOLUTION_DEFAULTS[LidarResolution.HIGH],
            PointToPointLink.DEFAULT_NUMBER_SAMPLES
        )
        return le.getProfile()

    def calculate_obstructions(self, gis_data: PointToPointGisData):
        """
        Determine Locations of Obstructions along link
        """
        obstructions = [p - f - l < 0 for p, f, l in zip(gis_data.profile, gis_data.fresnel, gis_data.lidar)]
        overlaps = 0
        if len(obstructions) > 0:
            prev = obstructions[0]
            for idx, v in enumerate(obstructions):
                if idx == 0:
                    continue
                if prev is True and v is False:
                    overlaps += 1
                prev = v
            if prev is True:
                overlaps += 1
        return overlaps

    def calculate_profile(self, num_samples: int = DEFAULT_NUMBER_SAMPLES):
        """
        Calculate how the curvature of the earth changes the fresnel zone
        """
        resolution = self.distance / num_samples
        dtm = self.get_dtm_heights()
        r1 = EARTH_RADIUS_M + self.radio0hgt + dtm[0]
        r2 = EARTH_RADIUS_M + self.radio1hgt + dtm[1]
        theta1 = 0
        theta2 = (num_samples * resolution) / EARTH_RADIUS_M
        y1 = r1 * math.sin(theta1)
        x1 = r1 * math.cos(theta1)
        y2 = r2 * math.sin(theta2)
        x2 = r2 * math.cos(theta2)
        m = (y2 - y1) / (x2 - x1)
        b = y2 - m * x2
        output = []
        for i in range(num_samples):
            theta = i * resolution / EARTH_RADIUS_M
            h = b / (math.sin(theta) - m * math.cos(theta)) - EARTH_RADIUS_M
            output.append(h)
        return output

    def calculate_fresnel(self, num_samples: int = DEFAULT_NUMBER_SAMPLES, fresnel_zone_number: float = 1.0):
        """
        Calculate the fresnel zone width across the link
        """
        resolution = self.distance / num_samples
        freq = self.frequency * 10 ** 9  # GHz to Hz
        wavelength = SPEED_OF_LIGHT / freq  # m
        d_total = num_samples * resolution
        output = []
        for i in range(num_samples):
            d1 = resolution * i
            d2 = (num_samples - i) * resolution
            fresnel = math.sqrt((fresnel_zone_number * d1 * d2 * wavelength) / d_total)
            output.append(fresnel)
        return output


class PointToPointLinkSerializer(
    serializers.ModelSerializer, SessionWorkspaceModelMixin
):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(format="%m/%d/%Y %-I:%M%p", required=False)
    feature_type = serializers.CharField(read_only=True)
    frequency = serializers.ChoiceField(
        choices=FREQUENCY_CHOICES, default=FREQUENCY_CHOICES[0][0]
    )
    radio0hgt_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min * M_2_FT,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max * M_2_FT,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )
    radio1hgt_ft = serializers.FloatField(
        required=False,
        validators=[
            MinValueValidator(
                ModelLimits.HEIGHT.min * M_2_FT,
                message=_(
                    "Ensure this value is greater than or equal to %(limit_value)s ft."
                ),
            ),
            MaxValueValidator(
                ModelLimits.HEIGHT.max * M_2_FT,
                message=_(
                    "Ensure this value is less than or equal to %(limit_value)s ft."
                ),
            ),
        ],
    )

    class Meta:
        model = PointToPointLink
        exclude = ["owner", "session", "created"]


class CoverageArea(UnitPreferencesModelMixin, WorkspaceFeature):
    name = models.CharField(max_length=50, default="Area")
    geojson = geo_models.GeometryField()

    @property
    def feature_type(self):
        return FeatureType.COVERAGE_AREA.value


@receiver(pre_save, sender=CoverageArea)
def _set_default_area_name(sender, instance, **kwargs):
    """
    Sets the default area # for a regular coverage area, equal to max + 1
    """
    if instance.created is None and instance.name == "Area":
        instance.name = f"Area {instance.map_session.area_number}"
        instance.map_session.area_number += 1
        instance.map_session.save()


@receiver(post_delete, sender=CoverageArea)
def _set_area_number_post_delete(sender, instance, using, **kwargs):
    """
    Sets the default area # for future coverage areas after deletion.
    """
    if re.match(r"^Area \d+$", instance.name):
        names = CoverageArea.objects.filter(
            map_session=instance.map_session, name__regex=r"^Area \d+$"
        ).values("name")

        instance.map_session.area_number = (
            max(
                (
                    int(re.match(r"^Area (\d+)$", area["name"]).group(1))
                    for area in names
                ),
                default=0,
            )
            + 1
        )

        instance.map_session.save()


class CoverageAreaSerializer(serializers.ModelSerializer, SessionWorkspaceModelMixin):
    lookup_field = "uuid"
    last_updated = serializers.DateTimeField(format="%m/%d/%Y %-I:%M%p", required=False)
    feature_type = serializers.CharField(read_only=True)

    class Meta:
        model = CoverageArea
        exclude = ["owner", "session", "created"]


class BuildingCoverage(models.Model):
    class CoverageStatus(models.TextChoices):
        SERVICEABLE = "serviceable"
        UNSERVICEABLE = "unserviceable"
        UNKNOWN = "unknown"

    coverage = models.ForeignKey(
        "workspace.AccessPointCoverageBuildings",
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
    )
    msftid = models.IntegerField(null=True, blank=True)
    geog = geo_models.GeometryField(null=True, blank=True)
    status = models.CharField(
        default=CoverageStatus.UNKNOWN, max_length=20, choices=CoverageStatus.choices
    )
    height_margin = models.FloatField(blank=True, default=0.0)
    cpe_location = geo_models.PointField(null=True, blank=True)


class AccessPointCoverageBuildings(
    AbstractAsyncTaskAssociatedModel,
    AbstractAsyncTaskPrimaryKeyMixin,
    AbstractAsyncTaskHashCacheMixin,
):
    class CoverageCalculationStatus(models.TextChoices):
        START = "Started"
        FAIL = "Failed"
        COMPLETE = "Complete"

    # TODO: deprecate
    ap = models.OneToOneField(
        AccessPointLocation,
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        default=None,
    )
    sector = models.OneToOneField(
        AccessPointSector,
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        default=None,
        related_name="building_coverage",
    )
    status = models.CharField(
        default=CoverageCalculationStatus.START,
        max_length=20,
        choices=CoverageCalculationStatus.choices,
    )
    created = models.DateTimeField(auto_now_add=True)

    def calculate_hash(self):
        if self.ap is not None:
            return (
                f"{self.ap.geojson.x},{self.ap.geojson.y},"
                + f"{self.ap.max_radius},{self.ap.height},{self.ap.default_cpe_height}"
            )
        else:
            return (
                f"{self.sector.ap.geojson.x},{self.sector.ap.geojson.y},"
                + f"{self.sector.max_radius},{self.sector.height},{self.sector.default_cpe_height}"
            )

    @property
    def task_status(self):
        # We need to look at the results for viewshed first.
        if self.sector:
            viewshed_status = self.sector.viewshed.task_status
            if viewshed_status != AsyncTaskStatus.COMPLETED:
                return AsyncTaskStatus.NOT_STARTED
            else:
                return super().task_status
        else:
            return None

    def coverageStatistics(self) -> dict:
        serviceable = self.buildingcoverage_set.filter(
            status=BuildingCoverage.CoverageStatus.SERVICEABLE
        ).count()
        unserviceable = self.buildingcoverage_set.filter(
            status=BuildingCoverage.CoverageStatus.UNSERVICEABLE
        ).count()
        unknown = self.buildingcoverage_set.filter(
            status=BuildingCoverage.CoverageStatus.UNKNOWN
        ).count()
        return {
            "serviceable": serviceable,
            "unserviceable": unserviceable,
            "unknown": unknown,
        }


@receiver(post_save, sender=AccessPointSector)
def _create_building_coverage_task(
    sender, instance, created, raw, using, update_fields, **kwargs
):
    """
    Create building coverage task for new sectors
    """
    if created:
        AccessPointCoverageBuildings.objects.create(sector=instance)


@receiver(pre_delete, sender=AccessPointSector)
def _cancel_building_coverage_task(sender, instance, using, **kwargs):
    """
    Cancel coverage task for deleted sectors
    """
    try:
        AccessPointCoverageBuildings.objects.get(sector=instance).cancel_task()
    except AccessPointCoverageBuildings.DoesNotExist:
        pass


class Radio(models.Model):
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = geo_models.PointField()
    installation_height = models.FloatField(default=10)


class RadioSerializer(serializers.ModelSerializer, SessionWorkspaceModelMixin):
    class Meta:
        model = Radio
        fields = "__all__"


class PTPLink(models.Model):
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    frequency = models.FloatField(default=2.4)
    radios = models.ManyToManyField(Radio)


class PTPLinkSerializer(serializers.ModelSerializer, SessionWorkspaceModelMixin):
    radios = RadioSerializer(many=True)

    class Meta:
        model = PTPLink
        fields = "__all__"
