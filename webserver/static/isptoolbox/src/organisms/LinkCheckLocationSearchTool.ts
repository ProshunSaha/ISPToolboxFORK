import mapboxgl, * as MapboxGL from 'mapbox-gl';
import { isBeta } from '../LinkCheckUtils';
import { LinkCheckBasePopup } from '../isptoolbox-mapbox-draw/popups/LinkCheckBasePopup';
import { LinkCheckCustomerConnectPopup } from '../isptoolbox-mapbox-draw/popups/LinkCheckCustomerConnectPopup';
import { MapboxSDKClient } from '../MapboxSDKClient';
import { ClickableMarker } from '../molecules/ClickableMarker';
import { BaseWorkspaceManager } from '../workspace/BaseWorkspaceManager';
import MapboxGeocoder from 'mapbox__mapbox-gl-geocoder';

export class LinkCheckLocationSearchTool {
    private map: mapboxgl.Map;
    private marker: ClickableMarker;
    private workspaceManager: BaseWorkspaceManager;
    private geocoder: MapboxGeocoder | null = null;
    private reverseGeocodeResponse: any;
    private isPopupOpen: boolean;
    private static _instance: LinkCheckLocationSearchTool;

    constructor(map: mapboxgl.Map, workspaceManager: BaseWorkspaceManager) {
        if (!LinkCheckLocationSearchTool._instance) {
            LinkCheckLocationSearchTool._instance = this;

            this.workspaceManager = workspaceManager;
            this.marker = new ClickableMarker({
                draggable: true,
                color: '#28F2BF'
            });
            this.isPopupOpen = false;
            this.map = map;

            // Clicking on point -> show popup on desktop
            this.marker.onClick((e: any) => {
                if (e.originalEvent.button == 0) {
                    this.showPopup();
                }
            });

            this.marker.on('dragstart', () => {
                // have to do this so that after popup cleanup function we still remember if it was open or not
                if (this.isPopupOpen) {
                    LinkCheckCustomerConnectPopup.getInstance().hide();
                    this.isPopupOpen = true;
                }
            });

            this.marker.on('dragend', () => {
                this.onLocationChange(() => {
                    if (this.isPopupOpen) {
                        this.showPopup();
                    }
                });
            });
        }
    }

    setGeocoder(geocoder: MapboxGeocoder) {
        this.geocoder = geocoder;
        if (isBeta()) {
            this.geocoder.on('result', ({ result }: any) => {
                this.setLngLat(result.center);
                this.show();
            });

            this.geocoder.on('clear', () => {
                this.marker.remove();
            });
        }
    }

    onPopupClose() {
        this.isPopupOpen = false;
    }

    show() {
        this.marker.addTo(this.map);
    }

    hide() {
        if (this.isPopupOpen) {
            this.marker.remove();
            //@ts-ignore
            this.geocoder?.clear();
        }
    }

    setLngLat(lngLatInput: any) {
        this.marker.setLngLat(lngLatInput);
        this.onLocationChange();
    }

    private onLocationChange(followup?: (response: any) => void) {
        let mapboxClient = MapboxSDKClient.getInstance();
        let lngLat = [this.marker.getLngLat().lng, this.marker.getLngLat().lat];
        mapboxClient.reverseGeocode(lngLat, (response: any) => {
            let result = response.body.features;
            this.geocoder?.setInput(result[0].place_name);
            this.reverseGeocodeResponse = response;

            if (followup) {
                followup(response);
            }
        });
    }

    private showPopup() {
        let lngLat: [number, number] = [this.marker.getLngLat().lng, this.marker.getLngLat().lat];
        let popup = LinkCheckBasePopup.createPopupFromReverseGeocodeResponse(
            LinkCheckCustomerConnectPopup,
            lngLat,
            this.reverseGeocodeResponse
        ) as LinkCheckCustomerConnectPopup;
        popup.show();
        this.isPopupOpen = true;
    }

    public static getInstance() {
        if (!LinkCheckLocationSearchTool._instance) {
            throw new Error('Not instantiated');
        } else {
            return LinkCheckLocationSearchTool._instance;
        }
    }
}
