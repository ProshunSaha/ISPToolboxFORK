import {LinkCheckPage} from './LinkCheckPage'
mapboxgl.accessToken = 'pk.eyJ1IjoiZmJtYXBzIiwiYSI6ImNqOGFmamkxdTBmbzUyd28xY3lybnEwamIifQ.oabgbuGc81ENlOJoPhv4OQ';

function isBeta(){
    return JSON.parse(document.getElementById('los_beta').textContent);;
}

$(document).ready(function () {
    if(isBeta()){
        console.log('Beta Mode On!');
    } else {
        console.log('Beta Off!');
    }
    const networkID = window.networkID;
    const userRequestIdentity = window.userRequestIdentity;
    const radio_names = window.radio_names;
    const los_check = new LinkCheckPage(networkID, userRequestIdentity, radio_names);
});