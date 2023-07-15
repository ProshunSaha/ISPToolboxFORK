export enum WorkspaceEvents {
    AP_UPDATE = 'ap.update',
    AP_RENDER_GIVEN = 'ap.render_given',
    AP_SELECTED = 'ap.selected',
    AP_COVERAGE_UPDATED = 'ap.coverage_updated',
    NO_ITEMS = 'workspace.no_items',
    FEATURES_LOADED = 'workspace.features_loaded'
}

export enum WorkspaceFeatureTypes {
    AP = 'access_point',
    CPE = 'cpe',
    AP_CPE_LINK = 'ap_cpe_link',
    COVERAGE_AREA = 'coverage_area'
}

export enum WorkspaceTools {
    MARKET_EVALUATOR = 'market_evaluator',
    LOS_CHECK = 'los_check'
}
