// Create new mapbox Map
import * as MapboxGL from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import MarketEvaluatorWS from './MarketEvaluatorWS';
import { MarketEvaluatorSidebarManager } from './organisms/MarketEvaluatorSidebarManager';

import {
    OverrideDirect,
    OverrideSimple,
    APDrawMode,
    OverrideDrawPolygon
} from './isptoolbox-mapbox-draw/index';
import { ISPToolboxAbstractAppPage } from './ISPToolboxAbstractAppPage';
import { MarketEvaluatorWorkspaceManager } from './workspace/MarketEvaluatorWorkspaceManager';
import { MarketEvaluatorTowerPopup } from './isptoolbox-mapbox-draw/popups/TowerPopups';
import { MarketEvaluatorRadiusAndBuildingCoverageRenderer } from './organisms/MarketEvaluatorRadiusAndBuildingCoverageRenderer';
import { MultiThumbSlider } from './atoms/MultiThumbSlider';
import MarketEvaluatorMapLayerSidebarManager from './MarketEvaluatorMapLayerSidebarManager';
import { AjaxTowerPopup } from './isptoolbox-mapbox-draw/popups/AjaxTowerPopup';
import { MarketEvaluatorSectorPopup } from './isptoolbox-mapbox-draw/popups/AjaxSectorPopups';
import { ISPToolboxTool } from './workspace/WorkspaceConstants';

export class MarketEvaluatorPage extends ISPToolboxAbstractAppPage {
    map: MapboxGL.Map;
    draw: MapboxDraw;
    marketEvalWS: MarketEvaluatorWS;
    overlayManager: MarketEvaluatorMapLayerSidebarManager;

    constructor() {
        super(
            {
                // @ts-ignore
                simple_select: OverrideSimple(true),
                direct_select: OverrideDirect(),
                draw_ap: APDrawMode(),
                draw_polygon: OverrideDrawPolygon()
            },
            'market_eval',
            true
        );

        new MarketEvaluatorWS([]);
        MarketEvaluatorSidebarManager.getInstance().initializePopovers();
        this.windowResizeCallback();
        window.addEventListener('resize', this.windowResizeCallback);
    }

    windowResizeCallback() {
        const window_height = $(window).height() ?? 0;
        const window_width = $(window).width() ?? 0;
        const disclaimer_height = $('footer').outerHeight() ?? 0;

        if (window_height - disclaimer_height - 50 < 400 || window_width < 768) {
            $('#map, .workspace-container').css('min-height', `400px`);
            $('#map-layer-sidebar').css('max-height', `400px`);
        } else {
            $('#map, .workspace-container').css(
                'min-height',
                `calc(100vh - 50px - ${disclaimer_height}px)`
            );
            $('#map-layer-sidebar').css(
                'max-height',
                `calc(100vh - 50px - ${disclaimer_height}px)`
            );
        }
        $('.workspace-container').css('height', `calc(100vh - 50px - ${disclaimer_height}px)`);

        if (this.map?.resize) {
            this.map.resize();
        }
    }

    onMapLoad() {
        new MarketEvaluatorWorkspaceManager(this.map, this.draw);
        new MarketEvaluatorMapLayerSidebarManager(this.map, this.draw);

        // Tooltips
        new AjaxTowerPopup(this.map, this.draw, ISPToolboxTool.MARKET_EVAL);
        new MarketEvaluatorSectorPopup(this.map, this.draw);
        new MarketEvaluatorTowerPopup(this.map, this.draw);
        const radius_building_render = new MarketEvaluatorRadiusAndBuildingCoverageRenderer(
            this.map,
            this.draw
        );

        // Building Size Filter
        document.querySelectorAll('[role=multi-thumb-slider]').forEach((slider) => {
            var filter = new MultiThumbSlider(slider, (range) => {
                radius_building_render.updateBuildingFilterSize(range);
                MarketEvaluatorSidebarManager.getInstance().updateBuildingFilter(range);
            });
            $('#collapseBuildingFilter').on('shown.bs.collapse', filter.resetSliders.bind(filter));
            $('#collapseBuildingFilter').on('shown.bs.collapse', filter.redraw.bind(filter));
            PubSub.subscribe('filter.bounds_update', (msg: string, data: [number, number]) => {
                filter.setRange(data[0], data[1]);
            });
        });
    }

    onGeocoderLoad() {}
}
