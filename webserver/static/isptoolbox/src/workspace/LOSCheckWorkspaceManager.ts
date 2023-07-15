import mapboxgl, * as MapboxGL from 'mapbox-gl';
import * as _ from 'lodash';
import { WorkspaceFeatureTypes } from './WorkspaceConstants';
import { BaseWorkspaceFeature } from './BaseWorkspaceFeature';
import { AccessPoint, APToCPELink, CPE } from './WorkspaceFeatures';
import { MapboxSDKClient } from '../MapboxSDKClient';
import { BuildingCoverageStatus } from './BuildingCoverage';
import { LinkCheckTowerPopup } from '../isptoolbox-mapbox-draw/popups/TowerPopups';
import { getStreetAndAddressInfo } from '../LinkCheckUtils';

import {
    BaseWorkspaceManager,
    DEFAULT_AP_HEIGHT,
    DEFAULT_AP_NAME,
    DEFAULT_NO_CHECK_RADIUS
} from './BaseWorkspaceManager';

const SUPPORTED_FEATURE_TYPES = [
    WorkspaceFeatureTypes.AP_CPE_LINK,
    WorkspaceFeatureTypes.AP,
    WorkspaceFeatureTypes.CPE
];

export class LOSCheckWorkspaceManager extends BaseWorkspaceManager {
    constructor(map: MapboxGL.Map, draw: MapboxDraw) {
        super(map, draw, SUPPORTED_FEATURE_TYPES);
        if (!BaseWorkspaceManager._instance) {
            BaseWorkspaceManager._instance = this;
        }
    }

    initSaveFeatureHandlers() {
        this.saveFeatureDrawModeHandlers.draw_ap = this.createApFeature.bind(this);

        this.saveFeatureDrawModeHandlers.simple_select = (feature: any) => {
            // It is possible to add either an AP or CPE while in simple_select so determine based on feature properties
            // Adding CPE also adds link from CPE to specified AP (see customer popup)
            if (feature.geometry.type == 'Point' && !feature.properties.radius) {
                let workspaceFeature = new CPE(this.map, this.draw, feature);
                this.saveWorkspaceFeature(workspaceFeature, (resp) => {
                    let cpe = workspaceFeature as CPE;
                    let apUUID = feature.properties.ap;
                    let ap = this.features[apUUID] as AccessPoint;
                    let link = cpe.linkAP(ap);
                    this.saveWorkspaceFeature(link, (resp) => {
                        this.map.fire('draw.create', { features: [link.getFeatureData()] });
                    });
                });
            } else if (feature.properties.radius) {
                this.createApFeature(feature);
            }
        };

        this.saveFeatureDrawModeHandlers.direct_select = (feature: any) => {
            if (feature.properties.radius) {
                this.createApFeature(feature);
            }
        };
    }

    initDeleteFeatureHandlers() {
        this.deleteFeaturePreAjaxHandlers[WorkspaceFeatureTypes.AP] = (
            workspaceFeature: BaseWorkspaceFeature
        ) => {
            let popup = LinkCheckTowerPopup.getInstance();
            let ap = workspaceFeature as AccessPoint;

            // Get rid of tower tooltip if the APs match
            if (popup.getAccessPoint() === ap) {
                popup.hide();
            }
        };

        this.deleteFeaturePreAjaxHandlers[WorkspaceFeatureTypes.AP_CPE_LINK] = (
            workspaceFeature: BaseWorkspaceFeature
        ) => {
            let link = workspaceFeature as APToCPELink;
            if (!this.draw.get(link.ap.mapboxId) || !this.draw.get(link.cpe.mapboxId)) {
                delete this.features[workspaceFeature.workspaceId];
                return false;
            } else {
                return true;
            }
        };
    }

    initUpdateFeatureHandlers() {
        this.updateFeatureAjaxHandlers[WorkspaceFeatureTypes.AP].post_update = (
            workspaceFeature: BaseWorkspaceFeature
        ) => {
            let ap = workspaceFeature as AccessPoint;
            Object.keys(BuildingCoverageStatus).forEach((status: string) => {
                ap.setFeatureProperty(status, null);
            });
            LinkCheckTowerPopup.getInstance().onAPUpdate(ap);
            LinkCheckTowerPopup.getInstance().show();
        };

        this.updateFeatureAjaxHandlers[WorkspaceFeatureTypes.CPE].post_update = (
            workspaceFeature: BaseWorkspaceFeature
        ) => {
            // I hate this hack
            let cpe = workspaceFeature as CPE;
            $(`#radio_name-1`).text(cpe.getFeatureProperty('name'));
        };
    }

    private createApFeature(feature: any) {
        const mapboxClient = MapboxSDKClient.getInstance();

        if (feature.geometry.type == 'Point') {
            const newCircle = {
                ...feature,
                properties: {
                    radius: feature.properties.radius / 1000,
                    max_radius: feature.properties.radius / 1000,
                    center: feature.geometry.coordinates,
                    height: DEFAULT_AP_HEIGHT,
                    no_check_radius: DEFAULT_NO_CHECK_RADIUS,
                    name: DEFAULT_AP_NAME
                },
                id: feature.id
            };
            let ap = new AccessPoint(this.map, this.draw, newCircle);
            this.saveWorkspaceFeature(ap, (resp) => {
                const apPopup = LinkCheckTowerPopup.getInstance();
                apPopup.setAccessPoint(ap);
                apPopup.show();
                if (feature.properties.ptpLinksToRemove) {
                    feature.properties.ptpLinksToRemove.forEach((id: string) => {
                        let featToDelete = this.draw.get(id);
                        this.draw.delete(id);
                        this.map.fire('draw.delete', { features: [featToDelete] });
                    });
                }

                if (feature.properties.cpeLngLats) {
                    feature.properties.cpeLngLats.forEach((lngLat: [number, number]) => {
                        mapboxClient.reverseGeocode(lngLat, (mapboxResponse: any) => {
                            let result = mapboxResponse.body.features;
                            let street = getStreetAndAddressInfo(result[0].place_name);
                            let newCPE = {
                                type: 'Feature',
                                geometry: {
                                    type: 'Point',
                                    coordinates: lngLat
                                },
                                properties: {
                                    name: street.street,
                                    ap: ap.workspaceId,
                                    feature_type: WorkspaceFeatureTypes.CPE
                                }
                            };
                            this.map.fire('draw.create', { features: [newCPE] });
                        });
                    });
                }
            });
        }
    }
}
