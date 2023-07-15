import { renderLinkEnds } from './LinkDrawMode.js';
import { createSupplementaryPointsForCircle } from './RadiusModeUtils.js';
import moveFeatures from '@mapbox/mapbox-gl-draw/src/lib/move_features';

export function OverrideSimple() {
  const simple_select = MapboxDraw.modes.simple_select;
  simple_select.toDisplayFeatures = function (state, geojson, display) {
    geojson.properties.active = this.isSelected(geojson.properties.id)
      ? 'true'
      : 'false';
    display(geojson);

    renderLinkEnds(geojson, display);

    this.fireActionable();

    // Turn off tap drag zoom if there are any elements selected
    if (this.getSelectedIds().length > 0) {

      // Horrible hack; no documented way of doing this :)
      this.map.handlers._handlersById.tapDragZoom.disable();
    }
    // Re-enable if nothing is selected
    else {
      this.map.handlers._handlersById.tapDragZoom.enable();
    }

    if (
      geojson.properties.active !== 'active' ||
      geojson.geometry.type === 'Point'
    ) {
      return;
    }
    const supplementaryPoints = geojson.properties.user_isCircle
      ? createSupplementaryPointsForCircle(geojson)
      : [];
    supplementaryPoints.forEach(display);
  };

  simple_select.dragMove = function (state, e) {
    // Dragging when drag move is enabled
    // $FlowFixMe[prop-missing]
    state.dragMoving = true;
    e.originalEvent.stopPropagation();

    const delta = {
      // $FlowFixMe[prop-missing]
      lng: e.lngLat.lng - state.dragMoveLocation.lng,
      // $FlowFixMe[prop-missing]
      lat: e.lngLat.lat - state.dragMoveLocation.lat,
    };
    moveFeatures(this.getSelected(), delta);

    this.getSelected()
      .filter(feature => feature.properties.isCircle)
      .map(circle => circle.properties.center)
      .forEach(center => {
        center[0] += delta.lng;
        center[1] += delta.lat;
      });
    // $FlowFixMe[prop-missing]
    state.dragMoveLocation = e.lngLat;
  };
  return simple_select;
}