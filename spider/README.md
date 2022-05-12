# PDOK Spider Python

PDOK service spider written in Python (3.8.5).

## Usage

Optionally you can use a virtual environment for all this:

```sh
python -m venv venv
cd venv
# on linux
source bin/activate
# on windows
.\venv\Scripts\activate
# you are now 'working' in your virtual environment, you should see (venv) in your prompt

# NOTE to 'deactivate' your venv (to go out) run
deactivate
```

Install python module dependencies from `requirements.txt`

```sh
pip install -r requirements.txt
```

and run:

```sh
./spider.py --help
```

Spider has two subcommands: `layers` and `services`:

- `layers` will output a JSON document will all layers of all PDOK services, with some additional service metadata
- `services` will output a JSON document will all PDOK services, containing `md_id`, `title`, `url` and `protocol` of service.

Example to create a valid/full pdok.json usable in (old) pdokservicesplugin:

```sh
# -n  tries to retrieve 250 services of every protocol (WMS,WFS etc)
# use sort flag, to ensure popular services are on top of service list
./spider.py -n 10 --sort pdok.json
```

## Output Example

Outputs list of layers in the following format

For every service one example below: WMS, WMTS, WFS and WCS

```json
{
    "services": [
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
            "type": "wfs",
            "title": "inspireadressen",
            "abstract": "INSPIRE Adressen afkomstig uit de basisregistratie Adressen, beschikbaar voor heel Nederland",
            "url": "https://geodata.nationaalgeoregister.nl/inspireadressen/wfs",
            "layers": "inspireadressen:inspireadressen",
            "servicetitle": "INSPIRE Adressen WFS"
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
            "type": "wcs",
            "title": "ahn1_100m",
            "abstract": "",
            "url": "https://geodata.nationaalgeoregister.nl/ahn1/wcs?",
            "layers": "ahn1_100m",
            "servicetitle": "Actueel Hoogtebestand Nederland 1"
        }
    ]
}
```

# TODO
----

- pdokservices plugin: actually USE the Metadata-id by creating an url for it
- add styles to layers

