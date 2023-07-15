export const LOSCheckMapboxStyles = [
    // Standard Link Styling - unselected
    {
        'id': 'gl-draw-line-inactive',
        'type': 'line',
        'filter': ['all', ['==', 'active', 'false'],
            ['==', '$type', 'LineString'],
            ['!=', 'mode', 'static']
        ],
        'layout': {
            'line-cap': 'round',
            'line-join': 'round'
        },
        'paint': {
            'line-color': '#5692D1',
            'line-width': 5
        }
    },
    // Styling Selected Links
    {
        'id': 'gl-draw-line-active',
        'type': 'line',
        'filter': ['all', ['==', '$type', 'LineString'],
            ['==', 'active', 'true']
        ],
        'layout': {
            'line-cap': 'round',
            'line-join': 'round'
        },
        'paint': {
            'line-color': '#5692D1',
            'line-dasharray': [0.2, 2],
            'line-width': 5
        }
    },
    // Halos around radios - unselected
    {
        "id": "gl-draw-polygon-and-line-vertex-halo-active",
        "type": "circle",
        "filter": ["all", ["==", "$type", "LineString"]],
        "paint": {
            "circle-radius": 8,
            "circle-color": "#ffffff"
        }
    },
    // Default Circle Appearance
    {
        'id': 'gl-draw-point-inactive',
        'type': 'circle',
        'filter': ['all', ['==', 'active', 'false'],
            ['==', '$type', 'Point'],
            ['!=', 'mode', 'static']
        ],
        'paint': {
            'circle-radius': 10,
            'circle-color': '#FFFFFF'
        }
    },
    // Radio styling 
    {
        'id': 'selected_radio_render',
        'type': 'circle',
        'filter': [
            'all',
            ['==', 'meta', 'radio_point']
        ],
        'paint': {
            'circle-radius': 7,
            'circle-color': ['get', "color"],
        },
    },
    // polygon outline stroke
    // This doesn't style the first edge of the polygon, which uses the line stroke styling instead
    {
        id: 'gl-draw-polygon-stroke-active',
        type: 'line',
        filter: [
            'all',
            ['==', '$type', 'Polygon'],
            ['!=', 'mode', 'static'],
        ],
        layout: {
            'line-cap': 'round',
            'line-join': 'round',
        },
        paint: {
            'line-color': '#1172A9',
            'line-width': 4,
        },
    },
    {
        id: 'gl-draw-polygon-midpoint',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'midpoint']],
        paint: {
            'circle-radius': 6,
            'circle-color': '#fbb03b',
        },
    },
    // polygon fill
    {
        id: 'gl-draw-polygon-fill-not-static',
        type: 'fill',
        filter: [
        'all',
        ['==', '$type', 'Polygon'],
        ['!=', 'mode', 'static'],
        ],
        paint: {
        'fill-color': '#1172a9',
        'fill-outline-color': '#1172a9',
        'fill-opacity': 0.4,
        },
    },
    // Drawing Instructions
    {
        id: 'gl-draw-instructions',
        type: 'symbol',
        filter: ['all', ['==', '$type', 'Point'], ['has', 'draw_guide']],
        paint: {
            'text-halo-width': 1,
            'text-halo-color': 'rgba(0,0,0,1)',
            'text-color': 'rgba(194,216,236,1)',
        },
        layout: {
            'text-field': ['get', 'draw_guide'],
            'text-font': ['Arial Unicode MS Bold'],
            'text-justify': 'center',
            'text-offset': [0, 3],
            'text-size': 13,
            'text-letter-spacing': 0.03,
        },
    },
];