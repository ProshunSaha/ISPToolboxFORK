from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from rest_framework.test import APIClient
import json
from uuid import UUID

from workspace import geojson_utils
from workspace.models import (
    AccessPointLocation, CPELocation, APToCPELink, WorkspaceMapSession, CoverageArea, AccessPointBasedCoverageArea
)
from workspace.models.model_constants import FeatureType
from workspace.models import (
    AccessPointSerializer, CPESerializer, APToCPELinkSerializer, CoverageAreaSerializer, APCoverageAreaSerializer
)


################################################################################
#  UNIVERSAL CONSTANTS
################################################################################

JSON_CONTENT_TYPE = 'application/json'


################################################################################
#  TEST CASE DEFAULTS
################################################################################

DEFAULT_USERNAME = 'testuser'
DEFAULT_PASSWORD = 'cant_crack_this'
DEFAULT_EMAIL = 'testuser@test.com'
DEFAULT_FIRST_NAME = 'Test'
DEFAULT_LAST_NAME = 'User'

DEFAULT_AP_POINT = {
    "type": "Point",
    "coordinates": [
        -121.777777777777,
        38.98777777777777
    ]
}
DEFAULT_AP_POINT = json.dumps(DEFAULT_AP_POINT)

DEFAULT_CPE_POINT = {
    "type": "Point",
    "coordinates": [
        -121.811111111111111,
        38.92222222222222,
    ]
}
DEFAULT_CPE_POINT = json.dumps(DEFAULT_CPE_POINT)

DEFAULT_TEST_LINESTRING = {
    "type": "LineString",
    "coordinates": [
        [
            -121.777777777777,
            38.98777777777777
        ],
        [
            -121.811111111111111,
            38.92222222222222
        ]
    ]
}
DEFAULT_TEST_LINESTRING = json.dumps(DEFAULT_TEST_LINESTRING)

DEFAULT_TEST_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [
                -117.70889282226562,
                34.45788034775209
            ],
            [
                -118.09478759765625,
                34.033314554166736
            ],
            [
                -117.34085083007811,
                34.09474769880026
            ],
            [
                -117.70889282226562,
                34.45788034775209
            ]
        ]
    ]
}
DEFAULT_TEST_POLYGON = json.dumps(DEFAULT_TEST_POLYGON)

DEFAULT_TEST_GEO_COLLECTION = {
    "type": "GeometryCollection",
    "geometries": [
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        -74.45676,
                        40.36817
                    ],
                    [
                        -74.45676,
                        40.36718074074074
                    ],
                    [
                        -74.45577074074075,
                        40.36718074074074
                    ],
                    [
                        -74.45577074074075,
                        40.36817
                    ],
                    [
                        -74.45676,
                        40.36817
                    ]
                ]
            ]
        },
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        -74.45577074074075,
                        40.35926666666666
                    ],
                    [
                        -74.45577074074075,
                        40.35827740740741
                    ],
                    [
                        -74.45379222222222,
                        40.35827740740741
                    ],
                    [
                        -74.45379222222222,
                        40.35926666666666
                    ],
                    [
                        -74.45577074074075,
                        40.35926666666666
                    ]
                ]
            ]
        },
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        -74.45478148148149,
                        40.35629888888889
                    ],
                    [
                        -74.45478148148149,
                        40.35530962962963
                    ],
                    [
                        -74.45379222222222,
                        40.35530962962963
                    ],
                    [
                        -74.45379222222222,
                        40.35629888888889
                    ],
                    [
                        -74.45478148148149,
                        40.35629888888889
                    ]
                ]
            ]
        }
    ]
}
DEFAULT_TEST_GEO_COLLECTION = json.dumps(DEFAULT_TEST_GEO_COLLECTION)

DEFAULT_NAME = 'Test Object'
DEFAULT_HEIGHT = 10.0
DEFAULT_MAX_RADIUS = 14.2
DEFAULT_NO_CHECK_RADIUS = 0.01
DEFAULT_CPE_HEIGHT = 2.0
DEFAULT_FREQUENCY = 2.4
DEFAULT_UNEDITABLE = False


################################################################################
#  TEST CASE UPDATED FIELDS
################################################################################

UPDATED_TEST_POINT = {
    "type": "Point",
    "coordinates": [
        -122.63763427734375,
        39.142842478062505
    ]
}
UPDATED_TEST_POINT = json.dumps(UPDATED_TEST_POINT)

UPDATED_TEST_LINESTRING = {
    "type": "LineString",
    "coordinates": [
        [
            -122.07733154296875,
            39.31517545076218
        ],
        [
            -122.41241455078125,
            39.31517545076218
        ]
    ]
}
UPDATED_TEST_LINESTRING = json.dumps(UPDATED_TEST_LINESTRING)

UPDATED_TEST_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [
                -117.81600952148438,
                34.42503613021332
            ],
            [
                -117.59902954101562,
                34.42503613021332
            ],
            [
                -117.59902954101562,
                34.56312121279482
            ],
            [
                -117.81600952148438,
                34.56312121279482
            ],
            [
                -117.81600952148438,
                34.42503613021332
            ]
        ]
    ]
}
UPDATED_TEST_POLYGON = json.dumps(UPDATED_TEST_POLYGON)

UPDATED_TEST_GEO_COLLECTION = {
    "type": "GeometryCollection",
    "geometries": [
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [
                        -74.43994259259259,
                        40.346406296296294
                    ],
                    [
                        -74.43994259259259,
                        40.34541703703704
                    ],
                    [
                        -74.43895333333333,
                        40.34541703703704
                    ],
                    [
                        -74.43895333333333,
                        40.346406296296294
                    ],
                    [
                        -74.43994259259259,
                        40.346406296296294
                    ]
                ]
            ]
        }
    ]
}
UPDATED_TEST_GEO_COLLECTION = json.dumps(UPDATED_TEST_GEO_COLLECTION)

UPDATED_NAME = 'Test Object Two: Electric Boogaloo'
UPDATED_HEIGHT = 100
UPDATED_MAX_RADIUS = 2.42
UPDATED_FREQUENCY = 5


################################################################################
#  URLs FOR REST ENDPOINTS
################################################################################

AP_ENDPOINT = '/pro/workspace/api/ap-los'
CPE_ENDPOINT = '/pro/workspace/api/cpe'
AP_CPE_LINK_ENDPOINT = '/pro/workspace/api/ap-cpe-link'
COVERAGE_AREA_ENDPOINT = '/pro/workspace/api/coverage-area'
AP_COVERAGE_AREA_ENDPOINT = '/pro/workspace/api/ap-coverage-area'


################################################################################
#  TEST CASE CLASSES START HERE
################################################################################

class WorkspaceBaseTestCase(TestCase):
    def setUp(self):
        """Set-up test user and test objects."""
        self.testuser = get_user_model().objects.create_superuser(
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
            email=DEFAULT_EMAIL,
            first_name=DEFAULT_FIRST_NAME,
            last_name=DEFAULT_LAST_NAME
        )
        self.testuser.save()

        self.test_session = WorkspaceMapSession(
            owner=self.testuser,
        )
        self.test_session.save()

        self.test_ap = AccessPointLocation(
            owner=self.testuser,
            name=DEFAULT_NAME,
            map_session=self.test_session,
            geojson=DEFAULT_AP_POINT,
            height=DEFAULT_HEIGHT,
            max_radius=DEFAULT_MAX_RADIUS
        )
        self.test_ap.save()

        self.test_cpe = CPELocation(
            owner=self.testuser,
            name=DEFAULT_NAME,
            map_session=self.test_session,
            geojson=DEFAULT_CPE_POINT,
            height=DEFAULT_HEIGHT
        )
        self.test_cpe.save()

        self.test_ap_cpe_link = APToCPELink(
            owner=self.testuser,
            frequency=DEFAULT_FREQUENCY,
            map_session=self.test_session,
            ap=self.test_ap,
            cpe=self.test_cpe
        )
        self.test_ap_cpe_link.save()

        self.test_coverage_area = CoverageArea(
            owner=self.testuser,
            map_session=self.test_session,
            geojson=DEFAULT_TEST_POLYGON,
            uneditable=DEFAULT_UNEDITABLE
        )
        self.test_coverage_area.save()

        self.test_ap_coverage_area = AccessPointBasedCoverageArea(
            owner=self.testuser,
            map_session=self.test_session,
            geojson=DEFAULT_TEST_GEO_COLLECTION,
            ap=self.test_ap
        )
        self.test_ap_coverage_area.save()

    def build_feature_collection(self, features):
        return {
            'type': 'FeatureCollection',
            'features': features
        }

    def trim_mtime_from_feature_collection(self, feature_collection):
        for feature in feature_collection['features']:
            if 'properties' in feature and 'last_updated' in feature['properties']:
                del feature['properties']['last_updated']

    def json_dumps(self, data):
        """
        Parses UUID properly
        """
        return json.dumps(data, default=lambda x: str(x) if isinstance(x, UUID) else None)


class WorkspaceModelsTestCase(WorkspaceBaseTestCase):
    def get_feature_collection_flow(self, serializer, expected_features):
        feature_collection = serializer.get_features_for_session(self.test_session)
        self.trim_mtime_from_feature_collection(feature_collection)
        self.assertJSONEqual(
            json.dumps(self.build_feature_collection(expected_features)),
            self.json_dumps(feature_collection)
        )

    def test_feature_types(self):
        self.assertTrue(self.test_ap.feature_type, FeatureType.AP.value)
        self.assertTrue(self.test_cpe.feature_type, FeatureType.CPE.value)
        self.assertTrue(self.test_ap_cpe_link.feature_type, FeatureType.AP_CPE_LINK.value)
        self.assertTrue(self.test_coverage_area.feature_type, FeatureType.COVERAGE_AREA.value)
        self.assertTrue(self.test_ap_coverage_area, FeatureType.AP_COVERAGE_AREA.value)

    def test_get_features_for_session_ap(self):
        expected_height_ft = DEFAULT_HEIGHT * 3.28084
        expected_default_cpe_height_ft = DEFAULT_CPE_HEIGHT * 3.28084
        expected_max_radius_miles = DEFAULT_MAX_RADIUS * 0.621371
        expected_ap = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_AP_POINT),
            'properties': {
                'name': DEFAULT_NAME,
                'height': DEFAULT_HEIGHT,
                'uuid': str(self.test_ap.uuid),
                'map_session': str(self.test_session.uuid),
                'no_check_radius': DEFAULT_NO_CHECK_RADIUS,
                'default_cpe_height': DEFAULT_CPE_HEIGHT,
                'feature_type': FeatureType.AP.value,
                'max_radius': DEFAULT_MAX_RADIUS,
                'height_ft': expected_height_ft,
                'default_cpe_height_ft': expected_default_cpe_height_ft,
                'max_radius_miles': expected_max_radius_miles
            }
        }
        self.get_feature_collection_flow(AccessPointSerializer, [expected_ap])

    def test_get_features_for_session_cpe(self):
        expected_height_ft = DEFAULT_HEIGHT * 3.28084
        expected_cpe = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_CPE_POINT),
            'properties': {
                'name': DEFAULT_NAME,
                'height': DEFAULT_HEIGHT,
                'uuid': str(self.test_cpe.uuid),
                'map_session': str(self.test_session.uuid),
                'feature_type': FeatureType.CPE.value,
                'height_ft': expected_height_ft,
            }
        }
        self.get_feature_collection_flow(CPESerializer, [expected_cpe])

    def test_get_features_for_session_ap_cpe_link(self):
        expected_link = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_TEST_LINESTRING),
            'properties': {
                'frequency': DEFAULT_FREQUENCY,
                'ap': str(self.test_ap.uuid),
                'cpe': str(self.test_cpe.uuid),
                'uuid': str(self.test_ap_cpe_link.uuid),
                'map_session': str(self.test_session.uuid),
                'feature_type': FeatureType.AP_CPE_LINK.value
            }
        }
        self.get_feature_collection_flow(APToCPELinkSerializer, [expected_link])

    def test_get_features_for_user_coverage_area(self):
        expected_area = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_TEST_POLYGON),
            'properties': {
                'uuid': str(self.test_coverage_area.uuid),
                'map_session': str(self.test_session.uuid),
                'feature_type': FeatureType.COVERAGE_AREA.value,
                'uneditable': DEFAULT_UNEDITABLE
            }
        }
        self.get_feature_collection_flow(CoverageAreaSerializer, [expected_area])

    def test_get_features_for_session_ap_coverage_area(self):
        expected_link = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_TEST_GEO_COLLECTION),
            'properties': {
                'ap': str(self.test_ap.uuid),
                'uuid': str(self.test_ap_coverage_area.uuid),
                'map_session': str(self.test_session.uuid),
                'feature_type': FeatureType.AP_COVERAGE_AREA.value
            }
        }
        self.get_feature_collection_flow(APCoverageAreaSerializer, [expected_link])


class WorkspaceRestViewsTestCase(WorkspaceBaseTestCase):
    def setUp(self):
        super(WorkspaceRestViewsTestCase, self).setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.testuser)

    def create_geojson_model(self, model_cls, endpoint, data):
        """Uses the POST endpoint for the model class to create a model, then check if it's in db."""

        response = self.client.post(
            f'{endpoint}/',
            data,
            format='json',
            HTTP_ACCEPT=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, HTTP_201_CREATED)
        new_id = response.json()['uuid']
        return model_cls.objects.get(uuid=new_id)

    def update_geojson_model(self, model_cls, endpoint, model_id, data):
        """Uses the PATCH endpoint for the model class to create a model, then retrieve it from db."""
        response = self.client.patch(
            f'{endpoint}/{model_id}/',
            data,
            format='json',
            HTTP_ACCEPT=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, HTTP_200_OK)
        return model_cls.objects.get(uuid=model_id)

    def delete_geojson_model(self, model_cls, endpoint, model_id):
        """Uses the DELETE endpoint for the model class to delete the model, then test if its deleted."""
        num_user_models = len(model_cls.objects.filter(owner=self.testuser))
        response = self.client.delete(f'{endpoint}/{model_id}/', HTTP_ACCEPT=JSON_CONTENT_TYPE)
        new_num_user_models = len(model_cls.objects.filter(owner=self.testuser))

        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT)
        self.assertFalse(model_cls.objects.filter(uuid=model_id).exists())
        self.assertEqual(num_user_models - 1, new_num_user_models)

    def test_create_ap(self):
        new_ap = {
            'name': DEFAULT_NAME,
            'geojson': DEFAULT_AP_POINT,
            'height': DEFAULT_HEIGHT,
            'max_radius': DEFAULT_MAX_RADIUS
        }
        ap = self.create_geojson_model(AccessPointLocation, AP_ENDPOINT, new_ap)
        self.assertEqual(ap.owner, self.testuser)
        self.assertEqual(ap.name, DEFAULT_NAME)
        self.assertJSONEqual(ap.geojson.json, DEFAULT_AP_POINT)
        self.assertEqual(ap.height, DEFAULT_HEIGHT)
        self.assertEqual(ap.max_radius, DEFAULT_MAX_RADIUS)

    def test_create_cpe(self):
        new_cpe = {
            'name': DEFAULT_NAME,
            'geojson': DEFAULT_CPE_POINT,
            'height': DEFAULT_HEIGHT
        }
        cpe = self.create_geojson_model(CPELocation, CPE_ENDPOINT, new_cpe)
        self.assertEqual(cpe.owner, self.testuser)
        self.assertEqual(cpe.name, DEFAULT_NAME)
        self.assertJSONEqual(cpe.geojson.json, DEFAULT_CPE_POINT)
        self.assertEqual(cpe.height, DEFAULT_HEIGHT)

    def test_create_ap_cpe_link(self):
        new_link = {
            'frequency': DEFAULT_FREQUENCY,
            'geojson': DEFAULT_TEST_LINESTRING,
            'ap': self.test_ap.uuid,
            'cpe': self.test_cpe.uuid
        }
        link = self.create_geojson_model(APToCPELink, AP_CPE_LINK_ENDPOINT, new_link)
        self.assertEqual(link.owner, self.testuser)
        self.assertEqual(link.frequency, DEFAULT_FREQUENCY)
        self.assertJSONEqual(link.geojson.json, DEFAULT_TEST_LINESTRING)
        self.assertEqual(link.ap, self.test_ap)
        self.assertEqual(link.cpe, self.test_cpe)

    def test_create_coverage_area(self):
        new_area = {
            'geojson': DEFAULT_TEST_POLYGON,
            'uneditable': DEFAULT_UNEDITABLE
        }
        area = self.create_geojson_model(CoverageArea, COVERAGE_AREA_ENDPOINT, new_area)
        self.assertEqual(area.owner, self.testuser)
        self.assertEqual(area.uneditable, DEFAULT_UNEDITABLE)
        self.assertJSONEqual(area.geojson.json, DEFAULT_TEST_POLYGON)

    def test_create_ap_coverage_area(self):
        new_area = {
            'geojson': DEFAULT_TEST_GEO_COLLECTION,
            'ap': self.test_ap.uuid
        }
        area = self.create_geojson_model(AccessPointBasedCoverageArea, AP_COVERAGE_AREA_ENDPOINT, new_area)
        self.assertEqual(area.owner, self.testuser)
        self.assertJSONEqual(area.geojson.json, DEFAULT_TEST_GEO_COLLECTION)
        self.assertEqual(area.ap, self.test_ap)

    def test_update_ap(self):
        ap_id = self.test_ap.uuid
        updated_ap = {
            'name': UPDATED_NAME,
            'geojson': UPDATED_TEST_POINT,
            'height': UPDATED_HEIGHT,
            'max_radius': UPDATED_MAX_RADIUS
        }
        ap = self.update_geojson_model(AccessPointLocation, AP_ENDPOINT, ap_id, updated_ap)
        self.assertEqual(ap.owner, self.testuser)
        self.assertEqual(ap.name, UPDATED_NAME)
        self.assertJSONEqual(ap.geojson.json, UPDATED_TEST_POINT)
        self.assertEqual(ap.height, UPDATED_HEIGHT)
        self.assertEqual(ap.max_radius, UPDATED_MAX_RADIUS)

    def test_update_cpe(self):
        cpe_id = self.test_cpe.uuid
        updated_cpe = {
            'name': UPDATED_NAME,
            'geojson': UPDATED_TEST_POINT,
            'height': UPDATED_HEIGHT,
        }
        cpe = self.update_geojson_model(CPELocation, CPE_ENDPOINT, cpe_id, updated_cpe)
        self.assertEqual(cpe.owner, self.testuser)
        self.assertEqual(cpe.name, UPDATED_NAME)
        self.assertJSONEqual(cpe.geojson.json, UPDATED_TEST_POINT)
        self.assertEqual(cpe.height, UPDATED_HEIGHT)

    def test_update_ap_cpe_link(self):
        link_id = self.test_ap_cpe_link.uuid
        updated_link = {
            'frequency': UPDATED_FREQUENCY,
        }
        link = self.update_geojson_model(APToCPELink, AP_CPE_LINK_ENDPOINT, link_id, updated_link)
        self.assertEqual(link.owner, self.testuser)
        self.assertEqual(link.frequency, UPDATED_FREQUENCY)
        self.assertEqual(link.ap, self.test_ap)
        self.assertEqual(link.cpe, self.test_cpe)

    def test_update_coverage_area(self):
        area_id = self.test_coverage_area.uuid
        updated_area = {
            'geojson': UPDATED_TEST_POLYGON
        }
        area = self.update_geojson_model(CoverageArea, COVERAGE_AREA_ENDPOINT, area_id, updated_area)
        self.assertEqual(area.owner, self.testuser)
        self.assertJSONEqual(area.geojson.json, UPDATED_TEST_POLYGON)

    def test_update_ap_coverage_area(self):
        area_id = self.test_ap_coverage_area.uuid
        updated_area = {
            'geojson': UPDATED_TEST_GEO_COLLECTION
        }
        area = self.update_geojson_model(AccessPointBasedCoverageArea, AP_COVERAGE_AREA_ENDPOINT, area_id, updated_area)
        self.assertEqual(area.owner, self.testuser)
        self.assertJSONEqual(area.geojson.json, UPDATED_TEST_GEO_COLLECTION)

    def test_delete_geojson_models(self):
        # have to delete the AP CPE link and AP Coverage area first
        self.delete_geojson_model(APToCPELink, AP_CPE_LINK_ENDPOINT, self.test_ap_cpe_link.uuid)
        self.delete_geojson_model(AccessPointBasedCoverageArea, AP_COVERAGE_AREA_ENDPOINT, self.test_ap_coverage_area.uuid)
        self.delete_geojson_model(AccessPointLocation, AP_ENDPOINT, self.test_ap.uuid)
        self.delete_geojson_model(CPELocation, CPE_ENDPOINT, self.test_cpe.uuid)
        self.delete_geojson_model(CoverageArea, COVERAGE_AREA_ENDPOINT, self.test_coverage_area.uuid)


class WorkspaceGeojsonUtilsTestCase(WorkspaceBaseTestCase):
    def test_merge_two_feature_collections(self):
        expected_height_ft = DEFAULT_HEIGHT * 3.28084
        expected_max_radius_miles = DEFAULT_MAX_RADIUS * 0.621371
        expected_default_cpe_height_ft = DEFAULT_CPE_HEIGHT * 3.28084
        expected_ap = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_AP_POINT),
            'properties': {
                'name': DEFAULT_NAME,
                'height': DEFAULT_HEIGHT,
                'map_session': str(self.test_session.uuid),
                'uuid': str(self.test_ap.uuid),
                'no_check_radius': DEFAULT_NO_CHECK_RADIUS,
                'default_cpe_height': DEFAULT_CPE_HEIGHT,
                'feature_type': FeatureType.AP.value,
                'max_radius': DEFAULT_MAX_RADIUS,
                'height_ft': expected_height_ft,
                'default_cpe_height_ft': expected_default_cpe_height_ft,
                'max_radius_miles': expected_max_radius_miles
            }
        }
        expected_cpe = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_CPE_POINT),
            'properties': {
                'name': DEFAULT_NAME,
                'height': DEFAULT_HEIGHT,
                'map_session': str(self.test_session.uuid),
                'uuid': str(self.test_cpe.uuid),
                'feature_type': FeatureType.CPE.value,
                'height_ft': expected_height_ft,
            }
        }
        expected_feature_collection = self.build_feature_collection([expected_ap, expected_cpe])

        aps = AccessPointSerializer.get_features_for_session(self.test_session)
        cpes = CPESerializer.get_features_for_session(self.test_session)
        feature_collection = geojson_utils.merge_feature_collections(aps, cpes)
        self.trim_mtime_from_feature_collection(feature_collection)
        self.assertJSONEqual(json.dumps(expected_feature_collection),
                             self.json_dumps(feature_collection))

    def test_merge_two_feature_collections_one_empty(self):
        expected_height_ft = DEFAULT_HEIGHT * 3.28084
        expected_max_radius_miles = DEFAULT_MAX_RADIUS * 0.621371
        expected_default_cpe_height_ft = DEFAULT_CPE_HEIGHT * 3.28084
        expected_ap = {
            'type': 'Feature',
            'geometry': json.loads(DEFAULT_AP_POINT),
            'properties': {
                'name': DEFAULT_NAME,
                'height': DEFAULT_HEIGHT,
                'map_session': str(self.test_session.uuid),
                'uuid': str(self.test_ap.uuid),
                'no_check_radius': DEFAULT_NO_CHECK_RADIUS,
                'default_cpe_height': DEFAULT_CPE_HEIGHT,
                'feature_type': FeatureType.AP.value,
                'max_radius': DEFAULT_MAX_RADIUS,
                'height_ft': expected_height_ft,
                'default_cpe_height_ft': expected_default_cpe_height_ft,
                'max_radius_miles': expected_max_radius_miles
            }
        }
        expected_feature_collection = self.build_feature_collection([expected_ap])

        aps = AccessPointSerializer.get_features_for_session(self.test_session)
        empty_feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }
        feature_collection = geojson_utils.merge_feature_collections(aps, empty_feature_collection)
        self.trim_mtime_from_feature_collection(feature_collection)
        self.assertJSONEqual(json.dumps(expected_feature_collection),
                             self.json_dumps(feature_collection))
