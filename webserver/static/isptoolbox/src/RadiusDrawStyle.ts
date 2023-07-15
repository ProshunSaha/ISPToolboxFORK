export const RadiusDrawStyle = [
  // polygon fill
  {
    id: 'gl-draw-polygon-fill',
    type: 'fill',
    filter: [
      'all',
      ['==', '$type', 'Polygon'],
    ],
    paint: {
      'fill-color': '#1172a9',
      'fill-outline-color': '#1172a9',
      'fill-opacity': 0.4,
    },
  },
  {
    id: 'gl-draw-radius-label',
    type: 'symbol',
    filter: ['==', 'meta', 'currentPosition'],
    layout: {
      'text-field': '{radiusKm}',
      'text-anchor': 'left',
      'text-offset': [1, 0],
      'text-size': 22,
    },
    paint: {
      'text-color': 'rgba(0, 0, 0, 1)',
      'text-halo-color': 'rgba(255, 255, 255, 1)',
      'text-halo-width': 3,
      'icon-opacity': {
        base: 1,
        stops: [
          [7.99, 1],
          [8, 0],
        ],
      },
      'text-halo-blur': 1,
    },
  },
]