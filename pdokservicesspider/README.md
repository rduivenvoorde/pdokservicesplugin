# PDOK Spider Python

    PDOK service spider written in Python (3.8.5).

## Usage

Install dependencies from `requirements.txt` and run:

```
./spider.py --help
```

Example to create a valid/full pdok.json usable ik (old) psokservicesplugin:

```
# -n 250 tries to retrieve 250 services of every protocol (WMS,WFS etc) 
# that is for now enough (WMS is max 164 currently)
# pdok.json is the default name of the json file used in the psokservicesplugin
./spider.py -n 250 pdok.json
```

## Output Example

Outputs list of layers in the following format

For every service one example below: WMS, WMTS, WFS and WCS

```json
services: {[
{
"name": "2020_ortho25IR",
"title": "Luchtfoto 2020 Ortho 25cm Infrarood",
"tilematrixsets": "EPSG:28992,EPSG:3857,EPSG:4258,EPSG:4326,EPSG:25831,EPSG:25832,OGC:1.0:GoogleMapsCompatible",
"imgformats": "image/jpeg",
"servicetitle": "Landelijke Voorziening Beeldmateriaal",
"url": "https://service.pdok.nl/hwh/luchtfotocir/wmts/v1_0?request=GetCapabilities&service=WMTS",
"type": "wmts"
},
{
"type":"wfs",
"title":"inspireadressen",
"abstract":"INSPIRE Adressen afkomstig uit de basisregistratie Adressen, beschikbaar voor heel Nederland",
"url":"https://geodata.nationaalgeoregister.nl/inspireadressen/wfs",
"layers":"inspireadressen:inspireadressen",
"servicetitle":"INSPIRE Adressen WFS"
},
{
"name": "SD.AlopochenAegyptiaca",
"title": "Invasieve Exoten Nederland EU2018 - alopochen aegyptiaca",
"style": "verspreiding:DEFAULT",
"crs": "EPSG:28992,EPSG:25831,EPSG:25832,EPSG:3034,EPSG:3035,EPSG:3857,EPSG:4258,EPSG:4326,CRS:84",
"minscale": "",
"maxscale": "1e+12",
"imgformats": "image/png,image/jpeg,image/png; mode=8bit,image/vnd.jpeg-png,image/vnd.jpeg-png8",
"url": "https://geodata.nationaalgeoregister.nl/rvo/invasieve-exoten/wms/v1_0?request=GetCapabilities&service=WMS",
"servicetitle": "Invasieve Exoten EU2018",
"type": "wms"
},
{
"type":"wcs",
"title":"ahn1_100m",
"abstract":"",
"url":"https://geodata.nationaalgeoregister.nl/ahn1/wcs?",
"layers":"ahn1_100m",
"servicetitle":"Actueel Hoogtebestand Nederland 1"
}
]
}
```

TODO
----

- make output smaller: remove redundant keys from json
- make output easier to view in editor by making it possible to output one service on one line (also compact)
- make it possible to do some kind of sorting (so the most used WMTS layers are on top)
- pdokservices plugin: actually USE the Metadata-id by creating an url for it
- add styles to layers
- make sure crs's work