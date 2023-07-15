import mapboxgl from 'mapbox-gl';
import * as _ from 'lodash';
import { createGeoJSONCircle } from '../isptoolbox-mapbox-draw/DrawModeUtils';
import { Geometry, GeoJsonProperties, FeatureCollection, Feature } from 'geojson';
import * as StyleConstants from '../isptoolbox-mapbox-draw/styles/StyleConstants';
import { BuildingCoverage, EMPTY_BUILDING_COVERAGE } from '../workspace/BuildingCoverage';
import {
    SQM_2_SQFT,
    WorkspaceEvents,
    WorkspaceFeatureTypes
} from '../workspace/WorkspaceConstants';
import { AccessPoint, CoverageArea, CPE } from '../workspace/WorkspaceFeatures';
import LOSCheckWS from '../LOSCheckWS';
import { AccessPointCoverageResponse, LOSWSEvents } from '../workspace/WorkspaceConstants';
import { LOSCheckWorkspaceManager } from '../workspace/LOSCheckWorkspaceManager';
import {
    LinkCheckTowerPopup,
    MarketEvaluatorTowerPopup
} from '../isptoolbox-mapbox-draw/popups/TowerPopups';
import { MarketEvaluatorWorkspaceManager } from '../workspace/MarketEvaluatorWorkspaceManager';
import { MapboxSDKClient } from '../MapboxSDKClient';
import { LinkCheckBasePopup } from '../isptoolbox-mapbox-draw/popups/LinkCheckBasePopup';
import {
    LinkCheckCPEClickCustomerConnectPopup,
    LinkCheckCustomerConnectPopup
} from '../isptoolbox-mapbox-draw/popups/LinkCheckCustomerConnectPopup';
import { getCookie } from '../utils/Cookie';
import MarketEvaluatorWS, {
    BuildingOverlaysResponse,
    MarketEvalWSEvents,
    MarketEvalWSRequestType
} from '../MarketEvaluatorWS';
import { GeometryCollection } from '@turf/helpers';
//@ts-ignore
import geojsonArea from '@mapbox/geojson-area';
import { MapLayerSidebarManager } from '../workspace/MapLayerSidebarManager';
import { BaseWorkspaceManager } from '../workspace/BaseWorkspaceManager';
import { ViewshedTool } from './ViewshedTool';
import { miles2km } from '../LinkCalcUtils';

const ACCESS_POINT_RADIUS_VIS_DATA = 'ap_vis_data_source';
const ACCESS_POINT_RADIUS_VIS_LAYER_LINE = 'ap_vis_data_layer-line';
export const ACCESS_POINT_RADIUS_VIS_LAYER_FILL = 'ap_vis_data_layer-fill';

const BUILDING_DATA_SOURCE = 'building_data_source';
export const BUILDING_LAYER = 'building_layer';

const BUILDING_OUTLINE_LAYER = 'building_outline_layer';

const EMPTY_SOURCE_AFTER_BUILDING = 'empty_building_source';
export const EMPTY_LAYER_AFTER_BUILDING = 'empty_building_layer';

const IS_ACTIVE_AP = 'active_ap';
const ACTIVE_AP = 'true';
const INACTIVE_AP = 'false';

const IS_HIDDEN_AP = 'hidden';

abstract class RadiusAndBuildingCoverageRenderer {
    map: mapboxgl.Map;
    draw: MapboxDraw;
    workspaceManager: any;
    apPopup: any;
    renderCloudRF: boolean;
    last_selection: string = '';

    constructor(
        map: mapboxgl.Map,
        draw: MapboxDraw,
        workspaceManagerClass: any,
        apPopupClass: any,
        options?: {
            renderCloudRF?: boolean;
        }
    ) {
        this.map = map;
        this.draw = draw;
        this.apPopup = apPopupClass.getInstance();
        this.workspaceManager = BaseWorkspaceManager.getInstance();

        this.renderCloudRF = options?.renderCloudRF || false;

        this.map.addSource(BUILDING_DATA_SOURCE, {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] }
        });
        this.addBuildingLayer();

        this.map.addSource(ACCESS_POINT_RADIUS_VIS_DATA, {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] }
        });
        this.map.addLayer(
            {
                id: ACCESS_POINT_RADIUS_VIS_LAYER_FILL,
                type: 'fill',
                source: ACCESS_POINT_RADIUS_VIS_DATA,
                layout: {},
                paint: {
                    'fill-color': [
                        'match',
                        ['get', IS_ACTIVE_AP],
                        ACTIVE_AP,
                        '#5692d1',
                        INACTIVE_AP,
                        '#1172a9',
                        '#1172a9'
                    ],
                    'fill-opacity': 0.4
                }
            },
            BUILDING_LAYER
        );
        this.map.addLayer(
            {
                id: ACCESS_POINT_RADIUS_VIS_LAYER_LINE,
                type: 'line',
                source: ACCESS_POINT_RADIUS_VIS_DATA,
                layout: {},
                paint: {
                    'line-color': [
                        'match',
                        ['get', IS_ACTIVE_AP],
                        ACTIVE_AP,
                        '#5692d1',
                        INACTIVE_AP,
                        '#1172a9',
                        '#1172a9'
                    ],
                    'line-dasharray': [0.2, 2],
                    'line-width': 0.4
                }
            },
            BUILDING_LAYER
        );

        this.map.addSource(EMPTY_SOURCE_AFTER_BUILDING, {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] }
        });
        this.map.addLayer(
            {
                id: EMPTY_LAYER_AFTER_BUILDING,
                type: 'fill',
                source: EMPTY_SOURCE_AFTER_BUILDING,
                layout: {},
                paint: {}
            },
            BUILDING_LAYER
        );

        this.map.on('draw.delete', this.drawDeleteCallback.bind(this));
        this.map.on('draw.selectionchange', this.drawSelectionChangeCallback.bind(this));
        PubSub.subscribe(WorkspaceEvents.AP_UPDATE, this.AP_updateCallback.bind(this));
    }

    /**
     * Make sure to add a layer with `BUILDING_LAYER` as the `id`
     * and `BUILDING_DATA_SOURCE` as the `source`.
     */
    abstract addBuildingLayer(): void;

    abstract sendCoverageRequest({ features }: any): void;

    drawDeleteCallback({ features }: { features: Array<any> }) {
        this.renderAPRadius();
        this.renderBuildings();
    }

    drawSelectionChangeCallback({ features }: { features: Array<GeoJSON.Feature> }) {
        // Mapbox will count dragging a point features as a selection change event
        // Use this to determine if we are dragging or just selected a new feature
        let dragging = false;
        if (features.length === 1) {
            if (features[0].id === this.last_selection) {
                dragging = true;
                // Hide AP tooltip if user is dragging AP.
                this.apPopup.hide();
            } else {
                const selectedAPs = this.workspaceManager.filterByType(
                    features,
                    WorkspaceFeatureTypes.AP
                );
                if (selectedAPs.length === 1) {
                    this.last_selection = features[0].id as string;
                    let ap = BaseWorkspaceManager.getFeatureByUuid(
                        selectedAPs[0].properties.uuid
                    ) as AccessPoint;
                    this.apPopup.setAccessPoint(ap);
                    this.apPopup.show();
                }
            }
        } else {
            this.last_selection = '';
        }
        // Hide AP tooltip if user is dragging AP.
        if (dragging) {
            this.apPopup.hide();
        } else {
            // Unhide hidden APs
            features.forEach((f: any) => {
                if (f.properties.feature_type === WorkspaceFeatureTypes.AP) {
                    MapLayerSidebarManager.getInstance().setFeatureVisibility(
                        f.properties.uuid,
                        true
                    );
                }
            });
            this.sendCoverageRequest({ features });
            this.renderAPRadius();
            this.renderBuildings();
        }
    }

    AP_updateCallback(msg: string, { features }: { features: Array<any> }) {
        this.sendCoverageRequest({ features });
        this.renderAPRadius();
        this.renderBuildings();
        if (
            features.length === 1 &&
            features[0].properties?.feature_type === WorkspaceFeatureTypes.AP
        ) {
            let ap = BaseWorkspaceManager.getFeatureByUuid(
                features[0].properties.uuid
            ) as AccessPoint;
            if (this.apPopup.getAccessPoint() !== ap) {
                this.apPopup.hide();
                this.apPopup.setAccessPoint(ap);
                this.apPopup.show();
            }
        }
    }

    updateBuildingCoverage(msg: string, data: { features: Array<GeoJSON.Feature> }) {
        data.features.forEach((f: GeoJSON.Feature) => {
            if (f.properties) {
                this.sendCoverageRequest(f);
            }
        });
    }

    /**
     * Renders access point circles
     */
    renderAPRadius() {
        const circle_feats: { [id: string]: Feature<Geometry, GeoJsonProperties> } = {};
        let fc = this.draw.getSelected();
        let selectedAPs = new Set(
            fc.features
                .filter((f) => f.properties?.feature_type === WorkspaceFeatureTypes.AP)
                .map((f) => f.id)
        );
        let aps = this.draw
            .getAll()
            .features.filter((f) => f.properties?.feature_type === WorkspaceFeatureTypes.AP);

        // Render all APs.
        aps.forEach((feat: any) => {
            if (feat && (feat.properties.radius || feat.properties.radius_miles)) {
                if (feat.geometry.type === 'Point') {
                    let new_feat;
                    if (this.renderCloudRF && this.cloudRFExists(feat)) {
                        // CloudRF coverage is a geometrycollection; turn this into a feature.
                        let geometryCollection = JSON.parse(
                            feat.properties?.cloudrf_coverage_geojson_json
                        );
                        new_feat = {
                            type: 'Feature',
                            geometry: geometryCollection,
                            properties: {}
                        } as Feature<GeometryCollection, GeoJsonProperties>;
                    } else {
                        let radius =
                            feat.properties.radius || miles2km(feat.properties.radius_miles);
                        new_feat = createGeoJSONCircle(feat.geometry, radius, feat.id);
                    }

                    // @ts-ignore
                    new_feat.properties[IS_ACTIVE_AP] = selectedAPs.has(feat.id)
                        ? ACTIVE_AP
                        : INACTIVE_AP;

                    if (
                        !MapLayerSidebarManager.getInstance().hiddenAccessPointIds.includes(feat.id)
                    ) {
                        circle_feats[feat.id] = new_feat;
                    }
                }
            }
        });

        // Replace radius features with selected
        const radiusSource = this.map.getSource(ACCESS_POINT_RADIUS_VIS_DATA);
        if (radiusSource.type === 'geojson') {
            radiusSource.setData({
                type: 'FeatureCollection',
                features: Object.values(circle_feats)
            });
        }
    }

    /**
     * Renders building layer
     */
    renderBuildings() {
        let fc = this.draw.getSelected();
        let aps = fc.features.filter(this.shouldRenderFeature);
        if (aps.length === 0) {
            fc = this.draw.getAll();
        }
        const renderFeatures = fc.features.filter(this.shouldRenderFeature);
        // Replace building features with selected

        const buildingSource = this.map.getSource(BUILDING_DATA_SOURCE);
        if (buildingSource.type === 'geojson') {
            const coverage = BuildingCoverage.union(
                renderFeatures.map((feat) => {
                    let coverage_object = BaseWorkspaceManager.getFeatureByUuid(
                        feat.properties?.uuid
                    ) as AccessPoint;
                    return coverage_object?.coverage || EMPTY_BUILDING_COVERAGE;
                })
            );
            buildingSource.setData({
                type: 'FeatureCollection',
                features: coverage.toFeatureArray()
            });
        }
    }

    protected cloudRFExists(feat: Feature) {
        return (
            feat.properties?.cloudrf_coverage_geojson_json &&
            feat.properties?.cloudrf_coverage_geojson_json !== null
        );
    }

    protected shouldRenderFeature(f: any) {
        if (f.properties?.feature_type === WorkspaceFeatureTypes.AP) {
            return !MapLayerSidebarManager.getInstance().hiddenAccessPointIds.includes(f.id);
        } else if (f.properties?.feature_type === WorkspaceFeatureTypes.COVERAGE_AREA) {
            return !(f.id in MapLayerSidebarManager.getInstance().hiddenCoverageAreas);
        } else {
            return false;
        }
    }
}

export class LinkCheckRadiusAndBuildingCoverageRenderer extends RadiusAndBuildingCoverageRenderer {
    ws: LOSCheckWS;
    last_selection: string = '';

    constructor(map: mapboxgl.Map, draw: MapboxDraw, ws: LOSCheckWS) {
        super(map, draw, LOSCheckWorkspaceManager, LinkCheckTowerPopup);
        this.ws = ws;

        // Building Layer click callback
        this.map.on('click', BUILDING_LAYER, (e: any) => {
            // Only activate if in simple select mode
            if (this.draw.getMode() == 'simple_select') {
                // Check if we clicked on a CPE
                const features = this.map.queryRenderedFeatures(e.point);
                if (
                    !features.some((feat) => {
                        return feat.source.includes('mapbox-gl-draw');
                    })
                ) {
                    let building = this.map.queryRenderedFeatures(e.point, {
                        layers: [BUILDING_LAYER]
                    })[0];
                    let buildingId = building.properties?.msftid;
                    let lngLat: [number, number] = [e.lngLat.lng, e.lngLat.lat];
                    let mapboxClient = MapboxSDKClient.getInstance();
                    mapboxClient.reverseGeocode(lngLat, (response: any) => {
                        let popup = LinkCheckBasePopup.createPopupFromReverseGeocodeResponse(
                            LinkCheckCustomerConnectPopup,
                            lngLat,
                            response
                        );
                        popup.setBuildingId(buildingId);

                        // Render all APs
                        popup.show();
                    });
                }
            }
        });

        PubSub.subscribe(LOSWSEvents.AP_MSG, this.accessPointStatusCallback.bind(this));

        // Change the cursor to a pointer when the mouse is over the states layer.
        this.map.on('mouseenter', BUILDING_LAYER, () => {
            this.map.getCanvas().style.cursor = 'pointer';
        });

        // Change it back to a pointer when it leaves.
        this.map.on('mouseleave', BUILDING_LAYER, () => {
            this.map.getCanvas().style.cursor = '';
        });

        this.map.on(
            'draw.selectionchange',
            ({ features }: { features: Array<GeoJSON.Feature> }) => {
                let cpePopup = LinkCheckCPEClickCustomerConnectPopup.getInstance();
            // Show tooltip if only one CPE is selected.
                let dragging = false;
                if (features.length === 1) {
                    if (features[0].id === this.last_selection) {
                        dragging = true;
                        cpePopup.hide();
                    } else {
                        const selectedCPEs = features.filter(f => f.properties?.feature_type === WorkspaceFeatureTypes.CPE);
            if (selectedCPEs.length === 1) {
                            this.last_selection = features[0].id as string;
                let cpe = BaseWorkspaceManager.getFeatureByUuid(
                                selectedCPEs[0].properties?.uuid
                ) as CPE;
                let mapboxClient = MapboxSDKClient.getInstance();
                            let lngLat = cpe.getFeatureGeometry().coordinates as [number, number];
                mapboxClient.reverseGeocode(lngLat, (resp: any) => {
                    cpePopup = LinkCheckBasePopup.createPopupFromReverseGeocodeResponse(
                        LinkCheckCPEClickCustomerConnectPopup,
                        lngLat,
                        resp
                    );
                    cpePopup.hide();
                    cpePopup.setCPE(cpe);
                    cpePopup.show();
                });
                        }
                    }
                } else {
                    this.last_selection = '';
                cpePopup.hide();
            }
                }
        );
    }

    addBuildingLayer() {
        this.map.addLayer({
            id: BUILDING_OUTLINE_LAYER,
            type: 'line',
            source: BUILDING_DATA_SOURCE,
            layout: {},
            paint: {
                'line-color': [
                    'match',
                    ['get', 'serviceable'],
                    'unserviceable',
                    StyleConstants.UNSERVICEABLE_BUILDINGS_COLOR,
                    'serviceable',
                    StyleConstants.SERVICEABLE_BUILDINGS_COLOR,
                    /* other */ StyleConstants.UNKNOWN_BUILDINGS_COLOR
                ],
                'line-width': 1,
                'line-opacity': 0.9
            }
        });

        this.map.addLayer(
            {
                id: BUILDING_LAYER,
                type: 'fill',
                source: BUILDING_DATA_SOURCE,
                layout: {},
                paint: {
                    'fill-opacity': 0
                }
            },
            BUILDING_OUTLINE_LAYER
        );
    }

    sendCoverageRequest({ features }: { features: Array<any> }) {
        features.forEach((f: GeoJSON.Feature) => {
            if (f.properties && f.properties.feature_type === WorkspaceFeatureTypes.AP) {
                this.ws.sendAPRequest(f.properties.uuid, f.properties.height);
            }
        });
    }

    AP_updateCallback(msg: string, { features }: { features: Array<any> }) {
        let viewshedTool = ViewshedTool.getInstance();
        let feature = this.draw.get(viewshedTool.viewshed_feature_id as string);
        if (feature) {
            viewshedTool.setVisibleLayer(this.shouldRenderFeature(feature));
        }
        super.AP_updateCallback(msg, { features: features });
    }

    accessPointStatusCallback(msg: string, message: AccessPointCoverageResponse) {
        $.ajax({
            url: `/pro/workspace/api/ap-los/coverage/${message.uuid}/`,
            success: (resp) => {
                this.updateCoverageFromAjaxResponse(resp, message.uuid);
            },
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });
        $.ajax({
            url: `/pro/workspace/api/ap-los/coverage/stats/${message.uuid}/`,
            success: (resp) => {
                const features = this.draw.getAll().features.filter((f: GeoJSON.Feature) => {
                    return f.properties?.uuid === message.uuid;
                });

                // Set last updated time
                // TODO: non-US formats when we expand internationally with isUnitsUS false
                const now = Intl.DateTimeFormat('en-US', {
                    year: '2-digit',
                    month: '2-digit',
                    day: '2-digit'
                }).format(Date.now());

                // Set serviceable, unserviceable, and unknown
                features.forEach((feat: GeoJSON.Feature) => {
                    for (const [key, value] of Object.entries(resp)) {
                        this.draw.setFeatureProperty(feat.id as string, key, value);
                    }
                    this.draw.setFeatureProperty(feat.id as string, 'last_updated', now);
                });
                this.apPopup.onAPUpdate(
                    BaseWorkspaceManager.getFeatureByUuid(message.uuid) as AccessPoint
                );
            },
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });
    }

    updateCoverageFromAjaxResponse(resp: any, uuid: string) {
        const ap = BaseWorkspaceManager.getFeatureByUuid(uuid) as AccessPoint;
        ap.setCoverage(resp.features);
        this.renderBuildings();
        PubSub.publish(WorkspaceEvents.AP_COVERAGE_UPDATED, { uuid: uuid });
    }
}

export class MarketEvaluatorRadiusAndBuildingCoverageRenderer extends RadiusAndBuildingCoverageRenderer {
    buildingOverlays: GeometryCollection;
    buildingFilterSize: [number, number];
    constructor(map: mapboxgl.Map, draw: MapboxDraw) {
        super(map, draw, MarketEvaluatorWorkspaceManager, MarketEvaluatorTowerPopup, {
            renderCloudRF: true
        });

        this.buildingOverlays = {
            type: 'GeometryCollection',
            geometries: []
        };
        PubSub.subscribe(
            MarketEvalWSEvents.BUILDING_OVERLAYS_MSG,
            this.onBuildingOverlayMsg.bind(this)
        );
    }

    updateBuildingFilterSize(range: [number, number]) {
        this.buildingFilterSize = range;
        this.renderBuildings();
    }

    addBuildingLayer() {
        this.map.addLayer({
            id: BUILDING_LAYER,
            type: 'fill',
            source: BUILDING_DATA_SOURCE,
            layout: {},
            paint: {
                'fill-color': '#42B72A',
                'fill-opacity': 0.8
            }
        });
    }

    drawDeleteCallback({ features }: { features: Array<any> }) {
        this.sendCoverageRequest({ features: [] });
        super.drawDeleteCallback({ features });
    }

    sendCoverageRequest({ features }: any) {
        let geometries: Geometry[] = [];

        features = this.draw.getSelected().features.filter(this.shouldRenderFeature);

        let featuresToProcess;
        if (features.length === 0) {
            featuresToProcess = this.draw.getAll().features;
        } else {
            featuresToProcess = features;
        }
        MarketEvaluatorWS.getInstance().cancelCurrentRequest(MarketEvalWSRequestType.POLYGON);
        this.buildingOverlays.geometries = [];

        featuresToProcess.forEach((f: GeoJSON.Feature) => {
            if (f.properties && f.properties.feature_type && this.shouldRenderFeature(f)) {
                switch (f.properties.feature_type) {
                    case WorkspaceFeatureTypes.AP:
                        if (this.cloudRFExists(f)) {
                            const geometryCollection = JSON.parse(
                                f.properties?.cloudrf_coverage_geojson_json
                            );
                            geometries.push(...geometryCollection.geometries);
                        } else {
                            const new_feat = createGeoJSONCircle(
                                f.geometry,
                                f.properties.radius ?? 0.1,
                                f.id
                            );
                            geometries.push(new_feat.geometry);
                        }
                    case WorkspaceFeatureTypes.COVERAGE_AREA:
                        geometries.push(f.geometry);
                }
            }
        });

        if (geometries.length > 0) {
            MarketEvaluatorWS.getInstance().sendPolygonRequest({
                type: 'GeometryCollection',
                geometries: geometries
            });
        } else {
            PubSub.publish(WorkspaceEvents.NO_ITEMS);
        }
    }

    renderBuildings() {
        const buildingSource = this.map.getSource(BUILDING_DATA_SOURCE);
        if (buildingSource.type === 'geojson') {
            const polygons = [];
            for (const poly of this.buildingOverlays.geometries) {
                const area = SQM_2_SQFT * geojsonArea.geometry(poly);
                if (this.buildingFilterSize[0] <= area && area <= this.buildingFilterSize[1]) {
                    polygons.push(poly);
                }
            }
            buildingSource.setData({
                type: 'Feature',
                geometry: { type: 'GeometryCollection', geometries: polygons },
                properties: {}
            });
        }
    }

    onBuildingOverlayMsg(msg: string, response: BuildingOverlaysResponse) {
        if (response.gc !== null && response.offset !== null) {
            if (response.offset === '0') {
                this.buildingOverlays.geometries = [];
            }
            this.buildingOverlays.geometries.push(...response.gc.geometries);
        }
        PubSub.publish('filter.bounds_update', this.calculateMinMaxBuildingSizes());
        this.renderBuildings();
    }

    calculateMinMaxBuildingSizes() {
        const areas = this.buildingOverlays.geometries.map((g) => {
            return geojsonArea.geometry(g);
        });
        return [SQM_2_SQFT * Math.min(...areas), SQM_2_SQFT * Math.max(...areas)];
    }
}
