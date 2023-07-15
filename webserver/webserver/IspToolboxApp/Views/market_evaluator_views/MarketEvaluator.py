
from django.views import View
from django.contrib.gis.geos import GEOSGeometry
from webserver.IspToolboxApp.Tasks.mmWaveTasks.mmwave import getOSMNodes
from shapely.geometry import shape
import json
import logging
from django.http import JsonResponse
from django.db import connections
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


def getQueryTemplate(skeleton, addExclude, includeExclude):
    if addExclude:
        if includeExclude:
            return skeleton.format("St_intersects(geog, St_geomfromgeojson(%s)) AND St_intersects(geog, St_geomfromgeojson(%s))")
        else:
            return skeleton.format("St_intersects(geog, St_geomfromgeojson(%s)) AND NOT St_intersects(geog, St_geomfromgeojson(%s))")
    else:
        return skeleton.format("St_intersects(geog, St_geomfromgeojson(%s))")


def getQueryParams(request):
    # Check Body First:
    geojson = '{}'
    exclude = '{}'
    offset = 0
    try:
        body = request.body
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        geojson = json.dumps(body.get('geojson',{}))
        exclude = json.dumps(body.get('exclude',{}))
        offset = body.get('offset', 0)
    except:
        geojson = request.GET.get('geojson', '{}')
        exclude = request.GET.get('exclude', '{}')
        offset = request.GET.get('offset', 0)
    return geojson, exclude, offset


def getUniqueBuildingNodes(nodes):
    buildings = {k: v for (k, v) in nodes.items() if (
        ('tags' in v) and ('building' in v['tags']) and ('nodes' in v))}
    return buildings

def getAllNodes(nodes_list):
    nodes = {}
    for d in nodes_list:
        nodes.update(d)
    return nodes

def filterIncludeExclude(building_shape, include, exclude):
    overlaps_include = False
    for polygon in include:
        if polygon.intersects(building_shape):
            overlaps_include = True
            break
    if overlaps_include and exclude is not None:
        for polygon in exclude:
            if polygon.intersects(building_shape):
                overlaps_include = False
                break
    return overlaps_include


def filterBuildingNodes(buildings, nodes, include, exclude):
    building_shapes = {k: {'type': 'Polygon', "coordinates": [[[nodes[n]['lon'], nodes[n]['lat']] for n in b['nodes']]]} for (k, b) in buildings.items()}
    buildings_shapely = [shape(v) for (k,v) in building_shapes.items()]
    matching_buildings = [k for (k,v) in building_shapes.items() if filterIncludeExclude(shape(v), include, exclude)]        
    return matching_buildings, building_shapes


def filterByPolygon(nodes, polygon):
    buildings = {k: v for (k, v) in nodes.items() if (
        ('tags' in v) and ('building' in v['tags']) and ('nodes' in v))}
    building_shapes = {k: shape({'type': 'Polygon', "coordinates": [
                                [[nodes[n]['lon'], nodes[n]['lat']] for n in b['nodes']]]}) for (k, b) in buildings.items()}
    return {k: v for (k, v) in nodes.items() if k not in building_shapes or building_shapes[k].intersects(polygon)}


def checkIfIncomeProvidersAvailable(include, exclude):
    switcher = {
        '60': False,
        '66': False,
        '69': False,
        '78': False,
    }
    return checkIfAvailable(include, exclude, switcher)


def checkIfPrecomputedAvailable(include, exclude):
    switcher = {
        '60': False,
        '66': False,
        '69': False,
        '78': False,
        '72': False,
    }
    return checkIfAvailable(include, exclude, switcher)


def checkIfAvailable(include, exclude, switcher): 
    resp = False
    with connections['gis_data'].cursor() as cursor:
        query_skeleton = "SELECT geoid FROM tl_2017_us_state WHERE {}"
        query_skeleton = getQueryTemplate(
            query_skeleton, exclude != '{}', True)
        cursor.execute(query_skeleton, [
                       include, exclude] if exclude != '{}' else [include])
        for row in cursor.fetchall():
            if(switcher.get(row[0], True)):
                resp = True
                break
    return resp


def getMicrosoftBuildings(include, exclude, offset):
    resp = {'error': -1}
    try:
        with connections['gis_data'].cursor() as cursor:
            query_skeleton = "SELECT St_asgeojson(geog) FROM msftcombined WHERE {} LIMIT 10001 OFFSET %s;"
            query_skeleton = getQueryTemplate(
                query_skeleton, exclude != '{}', False)
            cursor.execute(query_skeleton, [
                           include, exclude, offset] if exclude != '{}' else [include, offset])
            polygons = [row[0] for row in cursor.fetchall()]
            resp = {'error': 0, "numbuildings": len(
                polygons), 'polygons': polygons}
    except:
        resp['error'] = -2
    return resp

def computeBBSize(bb):
    size = abs((bb[0] - bb[2]) * (bb[1] - bb[3]))
    return size


def getOSMBuildings(includeGeom, excludeGeom):
    response = {'error': -1}
    try:
        # Compute BB's
        if includeGeom.geom_type == 'Polygon':
            includeGeom = [includeGeom]
        bbIncludes = [a.bounds for a in includeGeom]
        bbExclude = []
        if excludeGeom:
            bbExclude = [a.bounds for a in excludeGeom]
        # Query OSM BB's
        if any(map(lambda x: computeBBSize(x) >= 0.25, bbIncludes)):
            return {'error' : -3}
        elif any(map(lambda x: computeBBSize(x) >= 0.25, bbExclude)):
            return {'error' : -4}
        osmInclude = [getOSMNodes(bbox) for bbox in bbIncludes]
        
        # Combine all nodes into dict
        allNodes = getAllNodes(osmInclude)

        # Combine all includes into unique building keys:
        buildingNodes = getUniqueBuildingNodes(allNodes)

        # Filter Buildings
        filteredBuildingsKeys, building_geojson_dict = filterBuildingNodes(buildingNodes, allNodes, includeGeom, excludeGeom)
        
        geometries = [json.dumps(building_geojson_dict[k]) for k in filteredBuildingsKeys]
        response = {'error': 0, "numbuildings": len(filteredBuildingsKeys), "polygons": geometries}
    except Exception as e:
        logging.info("OSM query failed")

    return response

@method_decorator(csrf_exempt, name='dispatch')
class DataAvailableView(View):
    def get(self, request):
        resp = {"error": -1, "data": False}
        try:
            geojson, geojson_exclude, _ = getQueryParams(request)
            query_available = checkIfIncomeProvidersAvailable(
                geojson, geojson_exclude)
            resp = {"error": 0, "data": query_available}
        except:
            logging.info("Failed to indicate if data is available")
        return JsonResponse(resp)
    
    def post(self, request):
        return self.get(request)


@method_decorator(csrf_exempt, name='dispatch')
class BuildingsView(View):
    def get(self, request):
        geojson, geojson_exclude, offset = getQueryParams(request)
        # Parse Geojsons
        include = shape(json.loads(geojson))
        exclude = None
        try:
            exclude = shape(json.loads(geojson_exclude))
        except:
            logging.info("No Exclude Defined")
        # Check if Query is in US
        query_in_us = checkIfPrecomputedAvailable(geojson, geojson_exclude)
        if query_in_us:
            response = getMicrosoftBuildings(geojson, geojson_exclude, offset)
        else:
            if int(offset) > 0:
                response = {'error': 0, "numbuildings": 0, "polygons": []}
            else:
                response = getOSMBuildings(include, exclude)
        # Respond
        return JsonResponse(response)
    
    def post(self, request):
        return self.get(request)


def getMicrosoftBuildingsCount(include, exclude, offset):
    resp = {'error': -1}
    try:
        with connections['gis_data'].cursor() as cursor:
            query_skeleton = """SELECT Count(*) 
FROM   (SELECT * 
		FROM   msftcombined 
		WHERE  {}
		LIMIT  10001 OFFSET %s) as a;
        """
            query_skeleton = getQueryTemplate(
                query_skeleton, exclude != '{}', False)
            cursor.execute(query_skeleton, [
                           include, exclude, offset] if exclude != '{}' else [include, offset])
            row = cursor.fetchone()
            resp = {'error': 0, "buildingcount": row[0]}
    except Exception as e:
        resp['error'] = -2
    return resp


def getOSMBuildingsCount(includeGeom, excludeGeom):
    response = {'error': -1}
    try:
        # Compute BB's
        if includeGeom.geom_type == 'Polygon':
            includeGeom = [includeGeom]
        bbIncludes = [a.bounds for a in includeGeom]
        bbExclude = []
        if excludeGeom:
            bbExclude = [a.bounds for a in excludeGeom]
        # Query OSM BB's
        osmInclude = [getOSMNodes(bbox) for bbox in bbIncludes]
        osmExclude = []
        if bbExclude:
            osmExclude = [getOSMNodes(bbox) for bbox in bbExclude]
        # Filter and combine results
        # Filtering
        osmIncludeFiltered = [filterByPolygon(
            nodes, polygon) for nodes, polygon in zip(osmInclude, includeGeom)]
        osmExcludeFiltered = []
        if excludeGeom:
            osmExcludeFiltered = [filterByPolygon(
                nodes, polygon) for nodes, polygon in zip(osmExclude, excludeGeom)]

        nodesInclude = {}
        for inc in osmIncludeFiltered:
            nodesInclude.update(inc)
        nodesExclude = {}
        for exc in osmExcludeFiltered:
            nodesExclude.update(exc)
        nodes = {k: nodesInclude[k]
                 for k in set(nodesInclude) - set(nodesExclude)}
        # Get Buildings
        buildings = {k: v for (k, v) in nodes.items() if (
            ('tags' in v) and ('building' in v['tags']) and ('nodes' in v))}
        # Build Geojsons
        response = {'error': 0, "buildingcount": len(buildings)}
    except:
        logging.info("OSM query failed")

    return response

@method_decorator(csrf_exempt, name='dispatch')
class CountBuildingsView(View):
    def get(self, request):
        geojson, geojson_exclude, offset = getQueryParams(request)

        # Parse Geojsons
        include = shape(json.loads(geojson))
        exclude = None
        try:
            exclude = shape(json.loads(geojson_exclude))
        except:
            logging.info("No Exclude Defined")
        # Check if Query is in US
        query_in_us = checkIfPrecomputedAvailable(geojson, geojson_exclude)
        if query_in_us:
            response = getMicrosoftBuildingsCount(
                geojson, geojson_exclude, offset)
        else:
            response = getOSMBuildingsCount(include, exclude)
        # Respond
        return JsonResponse(response)

    def post(self, request):
        return self.get(request)


class RDOFView(View):
    def get(self, request):
        geojson, geojson_exclude, offset = getQueryParams(request)

        resp = {'error': -1}
        try:
            with connections['gis_data'].cursor() as cursor:
                query_skeleton = """SELECT cbg_id, 
       county, 
       St_asgeojson(geog), 
       reserve, 
       locations 
FROM   auction_904_shp 
WHERE  {}
LIMIT  100;
"""
                query_skeleton = getQueryTemplate(
                    query_skeleton, geojson_exclude != '{}', False)
                cursor.execute(query_skeleton, [
                               geojson, geojson_exclude] if geojson_exclude != '{}' else [geojson])
                results = [row for row in cursor.fetchall()]
                censusblockgroup = [row[0] for row in results]
                county = [row[1] for row in results]
                geojson = [row[2] for row in results]
                reserve = [row[3] for row in results]
                locations = [row[4] for row in results]

                resp = {'error': 0, "censusblockgroup": censusblockgroup, "county": county,
                        "geojson": geojson, "reserve": reserve, "locations": locations}
        except Exception as e:
            resp['error'] = -2
        return JsonResponse(resp)


income_skeleton = """SELECT Avg(avgbuildingvalues.avgincome2018building) AS avgincome2018, 
	Avg(avgbuildingvalues.avgerror2018building)  AS avgerror2018, COUNT(*) as numbuildings
FROM   (SELECT unnested_intersecting_footprints.gid, 
			Avg(tract.income2018) AS avgincome2018building, 
			Avg(tract.error2018)  AS avgerror2018building 
	 FROM   (SELECT intersecting_footprints.*, 
					Unnest(microsoftfootprint2tracts.tractgids) AS tractgid 
			 FROM   (SELECT * 
					 FROM   microsoftfootprints 
					 WHERE  {}
					 LIMIT  10001 OFFSET %s) AS intersecting_footprints 
					LEFT JOIN microsoftfootprint2tracts 
						   ON intersecting_footprints.gid = 
							  microsoftfootprint2tracts.footprintgid) AS 
			unnested_intersecting_footprints 
			LEFT JOIN tract 
				   ON tract.gid = unnested_intersecting_footprints.tractgid 
	 GROUP  BY unnested_intersecting_footprints.gid) AS avgbuildingvalues;"""

income_skeleton_simple = """SELECT AVG(median_household_income) AS avgincome2018
FROM acs2018_median_income
JOIN tl_2019_tract ON acs2018_median_income.geoid = tl_2019_tract.geoid WHERE {};
"""

provider_skeleton = """SELECT providername, 
	Max(maxaddown)               AS maxdown, 
	Max(maxadup)                 AS maxadup, 
	Array_agg(DISTINCT techcode) AS tech 
FROM   form477jun2019 
	JOIN tl_2019_blocks_census 
	  ON tl_2019_blocks_census.geoid10 = form477jun2019.blockcode 
WHERE  {}
	AND consumer > 0
GROUP  BY providername 
ORDER  BY maxdown DESC 
LIMIT  6 OFFSET %s;
"""

@method_decorator(csrf_exempt, name='dispatch')
class IncomeView(View):
    def get(self, request):
        geojson, exclude, offset = getQueryParams(request)

        resp = {'error': -1}
        precomputedAvailable = checkIfPrecomputedAvailable(geojson, exclude)
        query_skeleton = income_skeleton_simple
        if precomputedAvailable:
            query_skeleton = income_skeleton
        else:
            exclude = '{}'
        query_skeleton = getQueryTemplate(
            query_skeleton, exclude != '{}', False)
        with connections['gis_data'].cursor() as cursor:
            query_arguments = [geojson, exclude] if exclude != '{}' else [geojson]
            if precomputedAvailable:
                query_arguments.append(offset)
            cursor.execute(query_skeleton, query_arguments)
            results = cursor.fetchone()
            resp = {'avgincome':  results[0]}  # , 'avgerror' : results[1]}
            if precomputedAvailable:
                resp['numbuildings'] = results[2]
            else:
                if int(offset) > 0:
                    resp = {'avgincome' : None, "numbuildings" : 0}
                else :
                    resp['numbuildings'] = 1
        return JsonResponse(resp)

    def post(self, request):
        return self.get(request)


@method_decorator(csrf_exempt, name='dispatch')
class Form477View(View):
    def get(self, request):
        resp = {'error': -1}
        geojson, exclude, offset = getQueryParams(request)

        query_skeleton = getQueryTemplate(
            provider_skeleton, exclude != '{}', False)
        with connections['gis_data'].cursor() as cursor:
            cursor.execute(query_skeleton, [
                           geojson, exclude, offset] if exclude != '{}' else [geojson, offset])
            rows = [row for row in cursor.fetchall()]
            competitors = [row[0] for row in rows]
            maxdown = [row[1] for row in rows]
            maxup = [row[2] for row in rows]
            tech = [row[3] for row in rows]
            resp = {'error': 0, 'competitors': competitors,
                    "down_ad_speed": maxdown, "up_ad_speed": maxup, "tech_used": tech}

        return JsonResponse(resp)

    def post(self, request):
        return self.get(request)

service_provider_skeleton = """SELECT providername, 
	maxaddown              AS maxdown, 
	maxadup                AS maxadup, 
	techcode AS tech 
FROM   form477jun2019 
	JOIN tl_2019_blocks_census 
	  ON tl_2019_blocks_census.geoid10 = form477jun2019.blockcode 
WHERE  {}
	AND consumer > 0
LIMIT  100 OFFSET %s;
"""

@method_decorator(csrf_exempt, name='dispatch')
class ServiceProviders(View):
    def get(self, request):
        resp = {'error' : -1}
        geojson, exclude, offset = getQueryParams(request)

        try :
            query_skeleton = getQueryTemplate(service_provider_skeleton, exclude != '{}', False)
            with connections['gis_data'].cursor() as cursor:
                cursor.execute(query_skeleton, [geojson, exclude, offset] if exclude != '{}' else [geojson, offset])
                rows = [row for row in cursor.fetchall()]
                competitors = [row[0] for row in rows]
                maxdown = [row[1] for row in rows]
                maxup = [row[2] for row in rows]
                tech = [row[3] for row in rows]
                resp = {'error': 0, 'competitors': competitors, "down_ad_speed": maxdown, "up_ad_speed": maxup, "tech_used": tech}
        except:
            resp['error'] = -2

        return JsonResponse(resp)

    def post(self, request):
        return self.get(request)
