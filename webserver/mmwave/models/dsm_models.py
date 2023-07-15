from django.db import models
from django.contrib.gis.db import models as gis_models
import uuid
from IspToolboxApp.util.s3 import createPresignedUrl, writeToS3
import secrets
from celery.result import AsyncResult
from celery import states
from area import area


MAXIMUM_AOI_AREA_KM2 = 100


class DSMException(Exception):
    pass


class DSMConversionJob(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
        unique=True
    )
    access_token = models.CharField(
        max_length=100,
        default=secrets.token_urlsafe,
        editable=False
    )
    area_of_interest = gis_models.GeometryField()
    task = models.UUIDField(null=True)
    error = models.CharField(null=True, max_length=200, default=None)
    created = models.DateTimeField(auto_now_add=True)

    def writeDSMtoS3(self, fp):
        writeToS3(fp, self.createS3Path())

    def createS3Path(self):
        return 'dsm-export-' + str(self.uuid) + '.tif'

    def getS3Presigned(self):
        return createPresignedUrl(self.createS3Path())

    def getTaskStatus(self):
        if self.task:
            res = AsyncResult(str(self.task))
            return res.status
        else:
            return states.PENDING

    def isValidRequest(self):
        """
        Validate that the area of interest is valid

        Area is less than maximum allowable

        Returns tuple (boolean, string)
        """
        if self.area_of_interest.empty:
            return False, "Selection empty. Please select an area"
        area_km2 = area(self.area_of_interest.json) * 1e-6
        if area_km2 > MAXIMUM_AOI_AREA_KM2:
            return False, f'Maximum area exceeded: {round(area_km2, 2)} | limit {MAXIMUM_AOI_AREA_KM2} km2'
        return True, ''

    def isRequestAuthorized(self, request):
        return request.headers.get('Authorization', None) == self.access_token
