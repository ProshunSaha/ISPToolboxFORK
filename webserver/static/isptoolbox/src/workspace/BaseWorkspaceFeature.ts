import mapboxgl, * as MapboxGL from "mapbox-gl";
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import { Feature, Geometry, Point, LineString, GeoJsonProperties, Polygon }  from 'geojson';
import { WorkspaceEvents } from './WorkspaceConstants';
import { getCookie } from '../utils/Cookie';
import { getSessionID } from '../utils/MapPreferences';

const BASE_WORKSPACE_RESPONSE_FIELDS = ['uuid', 'feature_type', 'last_updated']

/**
 * Abstract class for organizing and defining interactions between UI components
 * to be saved in Workspace and the backend
 */
export abstract class BaseWorkspaceFeature{
    mapboxId: string;
    workspaceId: string;
    map: MapboxGL.Map;
    draw: MapboxDraw;

    private readonly responseFields: Array<string>
    private readonly serializerFields: Array<string>
    private readonly apiEndpoint: string

    /**
     * Base constructor for a workspace feature. Sets parameters that will be
     * useful for UI interactions in the future
     * 
     * @param map: Mapbox map object
     * @param draw Mapbox draw object
     * @param apiEndpoint The REST API endpoint for creating/updating/deleting objects.
     *  This should be defined as a constant in the subclass's constructor
     * @param responseFields Fields to be saved to feature properties from the create/update responses.
     * @param serializedFields Fields to be serialized by the serialiser. This should
     *  be defined as a constant in the subclass's constructor
     * @param featureData Feature data for an object, or a mapbox id
     */
    constructor(map: MapboxGL.Map,
                draw: MapboxDraw,
                featureData: Feature<Geometry, any> | string,
                apiEndpoint: string,
                responseFields: Array<string>,
                serializedFields: Array<string>) {
        this.map = map;
        this.draw = draw;
        if (typeof featureData == 'number') {
            this.mapboxId = featureData;
        }
        else {
            // @ts-ignore
            this.mapboxId = String(this.draw.add(featureData)[0]);
        }
        this.apiEndpoint = apiEndpoint;
        this.responseFields = responseFields.concat(BASE_WORKSPACE_RESPONSE_FIELDS);
        this.serializerFields = serializedFields;

        let feature = this.draw.get(this.mapboxId);
        // @ts-ignore
        if ('uuid' in feature.properties) {
            this.workspaceId = feature?.properties.uuid;
        }
    }

    /**
     * Sends an AJAX request to persist a newly created object into the backend.
     * This should be called upon after object creation, if a new object is to be
     * persisted to the database. Calls successFollowup, if defined, to do further
     * things after object persistence.
     * 
     * @param successFollowup Function to execute on successfully persisting new
     * object.
     */
    create(successFollowup?: (resp: any) => void) {
        $.ajax({
            url: `${this.apiEndpoint}/`,
            method: 'POST',
            data: this.serialize(),
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Accept': 'application/json'
            } 
        }).done((resp) => {
            this.workspaceId = resp.uuid;
            this.updateFeatureProperties(resp);
            if (successFollowup) {
                successFollowup(resp);
            }
        });
    }

    /**
     * Updates the object in the backend with new information. Calls successFollowup if defined.
     * 
     * @param successFollowup Function to execute on successfully updating object
     * @returns A list of BaseWorkspaceFeature objects other than this one deleted by this function,
     * intended to fire additional Mapbox events.
     */
    update(successFollowup?: (resp: any) => void) {
        let feature = this.draw.get(this.mapboxId);
        $.ajax({
            url: `${this.apiEndpoint}/${feature?.properties?.uuid}/`,
            method: 'PATCH',
            data: this.serialize(),
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Accept': 'application/json'
            } 
        }).done((resp) => {
            this.updateFeatureProperties(resp);
            PubSub.publish(WorkspaceEvents.LOS_MODAL_OPENED);
            if (successFollowup) {
                successFollowup(resp);
            }
        });
    }

    /**
     * Deletes the object in the backend. Calls successFollowup if defined.
     * 
     * @param successFollowup Function to execute on successfully deleting object
     * @returns A list of BaseWorkspaceFeature objects other than this one deleted by this function,
     * intended to fire additional Mapbox events.
     */
    delete(successFollowup?: (resp: any) => void) {
        let removedFeature = this.removeFeatureFromMap(this.mapboxId);
        $.ajax({
            url: `${this.apiEndpoint}/${removedFeature?.properties?.uuid}/`,
            method: 'DELETE',
            data: this.serialize(),
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Accept': 'application/json'
            } 
        }).done((resp) => {
            PubSub.publish(WorkspaceEvents.LOS_MODAL_OPENED);
            if (successFollowup) {
                successFollowup(resp);
            }
        });
    }

    /**
     * Gets the feature type for this workspace feature.
     * 
     * @returns A string indicating this feature's feature type
     */
    getFeatureType(): string {
        return this.getFeatureData()?.properties?.feature_type;
    }

    getFeatureData(): Feature<Geometry, any> {
        return this.draw.get(this.mapboxId) as Feature<Geometry, any>;
    }

    getFeatureGeometry(): Geometry {
        return this.getFeatureData().geometry;
    }

    /**
     * Sets the feature property of the feature underlying this workspace object.
     * @param key Key
     * @param value Value
     */
    setFeatureProperty(key: string, value: any) {
        this.draw.setFeatureProperty(this.mapboxId, key, value);
    }

    getFeatureProperty(key: string) {
        return this.getFeatureData()?.properties[key];
    }

    protected removeFeatureFromMap(mapboxId: string) {
        let feature = this.getFeatureData();
        this.draw.delete(mapboxId);
        return feature;
    }

    protected updateFeatureProperties(response: any) {
        this.responseFields.forEach(field => {
            if (field in response) {
                this.setFeatureProperty(field, response[field]);
            }
        });
    }

    protected serialize() {
        const serialization: any = {}
        let feature = this.draw.get(this.mapboxId);
        this.serializerFields.forEach(field => {
            // @ts-ignore
            if (field in feature.properties) {
                // @ts-ignore
                serialization[field] = feature.properties[field];
            }
        });
        serialization.geojson = JSON.stringify(this.featureData.geometry);
        serialization.map_session = getSessionID();
        return serialization;
    }
}

/**
 * Abstract class containing point-specific functions for Workspace objects.
 */
export abstract class WorkspacePointFeature extends BaseWorkspaceFeature {
    /**
     * Moves the selected feature to the specified lat/long coordinates. To be
     * used by other Workspace feature classes for programatically moving objects
     * in response to other things moving, not as an extension for the Mapbox API.
     *
     * @param newCoords New coordinates (lat/long)
     */
    move(newCoords: [number, number]) {
        let feature = this.draw.get(this.mapboxId);

        // @ts-ignore
        feature.geometry.coordinates = newCoords;
        // @ts-ignore
        this.draw.add(feature);
        this.map.fire('draw.update', {features: [feature], action: 'move'})
    }

    getFeatureData(): Feature<Point, any> {
        return super.getFeatureData() as Feature<Point, any>;
    }

    getFeatureGeometry(): Point {
        return super.getFeatureGeometry() as Point;
    }

    getFeatureGeometryCoordinates() {
        return this.getFeatureGeometry().coordinates;
    }
}

/**
 * Abstract class containing point-specific functions for Workspace objects.
 */
 export abstract class WorkspaceLineStringFeature extends BaseWorkspaceFeature {

    /**
     * Moves the selected vertex to the specified lat/long coordinates. To be
     * used by other Workspace feature classes for programatically moving objects
     * in response to other things moving, not as an extension for the Mapbox API.
     * 
     * Calls successFollowup if defined, presumably for updating other objects.
     * 
     * @param index Index of coordinate in LineString object to update
     * @param newCoords New coordinates (lat/long)
     * @param successFollowup Function to execute after successfully moving object
     * @returns A list of other BaseWorkspaceFeature objects affected by this move.
     */
    moveVertex(index: number,
               newCoords: [number, number]) {
        let feature = this.getFeatureData();
        if (index >= 0 && index < feature.geometry.coordinates.length) {
            let newFeature = {...feature};
            newFeature.geometry.coordinates[index] = newCoords;
            this.draw.add(newFeature);
            this.map.fire('draw.update', {features: [newFeature], action: 'move'});
        }
    }

    getFeatureData(): Feature<LineString, any> {
        return super.getFeatureData() as Feature<LineString, any>;
    }

    getFeatureGeometry(): LineString {
        return super.getFeatureGeometry() as LineString;
    }

    getFeatureGeometryCoordinates() {
        return this.getFeatureGeometry().coordinates;
    }
}

/**
 * Abstract class containing polygon-specific functions for Workspace objects.
 */
 export abstract class WorkspacePolygonFeature extends BaseWorkspaceFeature {
    getFeatureData(): Feature<Polygon, any> {
        return super.getFeatureData() as Feature<Polygon, any>;
    }

    getFeatureGeometry(): Polygon {
        return super.getFeatureGeometry() as Polygon;
    }
}