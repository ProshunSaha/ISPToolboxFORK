import requests
import json
from mmwave.models import EPTLidarPointCloud
from django.contrib.gis.geos import GEOSGeometry
from dataUpdate.util.mail import sendNotifyEmail
from isptoolbox_storage.storage import S3ManifestStorage
from django.core.files.base import ContentFile


PT_CLOUD_GEOJSON_S3_PATH = 'pt_clouds.geojson'
SUCCESSFUL_UPDATE_SUBJECT = "[Automated Message][Success] Automated Point Cloud Update Successful"
UNSUCCESSFUL_UPDATE_SUBJECT = "[Automated Message][Failure] Automated Point Cloud Update Failed"


def loadBoundariesFromEntWine(send_email_success=False, send_email_failure=True):
    try:
        response = requests.get('https://usgs.entwine.io/boundaries/resources.geojson')
        response_content = json.loads(response.content)
        new_point_clouds = []
        for feat in response_content['features']:
            props = feat['properties']
            pt_cloud, created = EPTLidarPointCloud.objects.get_or_create(
                name=props['name'],
                url=props['url'],
                count=props['count'],
                boundary=GEOSGeometry(json.dumps(feat['geometry'])),
                srs=3857
            )
            pt_cloud.save()
            if created:
                new_point_clouds.append(pt_cloud)
        if send_email_success or len(new_point_clouds) > 0:
            sendNotifyEmail(
                SUCCESSFUL_UPDATE_SUBJECT,
                f'Successfully loaded {len(new_point_clouds)} new point clouds into the database'
            )
        if len(new_point_clouds) > 0:
            pt_clouds = EPTLidarPointCloud.objects.all()
            feature_collection = {
                'type': "FeatureCollection",
                'features': [
                    {'type': "Feature", 'geometry': json.loads(cld.boundary.json)}
                    for cld in pt_clouds
                ]
            }
            contents = json.dumps(feature_collection).encode()
            s3storage = S3ManifestStorage()
            s3storage.save(PT_CLOUD_GEOJSON_S3_PATH, ContentFile(contents))
    except Exception as e:
        if send_email_failure:
            sendNotifyEmail(UNSUCCESSFUL_UPDATE_SUBJECT, f'Error: {str(e)}')

    return new_point_clouds


if __name__ == "__main__":
    loadBoundariesFromEntWine()
