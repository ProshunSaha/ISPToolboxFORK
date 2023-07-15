# This is an auto-generated Django model module.
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.db import connections


class HrslUsa15(models.Model):
    """
    High Resolution Spatial Layer - Facebook Dataset

    Has attribution requirements
    https://data.humdata.org/dataset/united-states-high-resolution-population-density-maps-demographic-estimates
    """
    rid = models.AutoField(primary_key=True)
    # This field type is a guess.
    rast = models.RasterField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'hrsl_usa_1_5'

    @staticmethod
    def get_intersection_population(area_of_interest: GEOSGeometry, read_only: bool):
        query = f"""
            WITH raster_data as (
                SELECT
                    ST_Clip(
                        ST_SetSRID({HrslUsa15.rast.field.column}, ST_SRID(ST_GeomFromEWKB(%s))),
                        ST_GeomFromEWKB(%s),
                        0,
                        TRUE
                    ) as intersect
                FROM
                    {HrslUsa15._meta.db_table}
                WHERE
                    ST_Intersects(
                        ST_SetSRID({HrslUsa15.rast.field.column}, ST_SRID(ST_GeomFromEWKB(%s))),
                        ST_GeomFromEWKB(%s)
                    )
            )
            SELECT (ST_SummaryStatsAgg(raster_data.intersect, 1, false)).sum FROM raster_data;
        """
        with connections[HrslUsa15.objects.db].cursor() as cursor:
            cursor.execute(
                query, [area_of_interest.ewkb, area_of_interest.ewkb, area_of_interest.ewkb, area_of_interest.ewkb])
            res = cursor.fetchone()
            return res
