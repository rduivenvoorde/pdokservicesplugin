## PDOK Service Plugin

## English

This plugin is probably only interesting for the dutch audience.

It shows a list of available web services (WMS, WMTS, WFS, OGC:API tiles/features etc) from our
national data services (in our national crs EPSG:28992).
Further information in dutch below.

If you think this plugin is useful sent me a kind email :-)

## Nederlands

PDOK (Publieke Dienstverlening Op de Kaart) is een plugin om de verschillende
PDOK services te testen of te bekijken.

Op basis van een json bestand (IN de plugin) met alle op dit moment beschikbare services wordt een dialoog opgebouwd met daarin

- het soort service (WMS, WMTS, WFS, TMS, OGC:API tiles/features)
- de naam van de service
- een regel per laag van de service

Door op een item te klikken wordt de service direct aangeroepen een getoond.

Alle services zijn minstens in EPSG:28992 beschikbaar

## Developers

Install dev tools with:

```sh
pip3 install -r pdokservicesplugin/requirements/dev.txt
```

Lint python code with:

```sh
pylint --errors-only --disable=E0611 pdokservicesplugin
```

Format python code with:

```sh
black pdokservicesplugin
```

Update layers config file in [`pdokservicesplugin/resources/layers-pdok.json`](pdokservicesplugin/resources/layers-pdok.json) (run from root of repo):
Note: some layers (specifically OpenBasisKaart) are added manually, make sure not to delete those.

```sh
./scripts/generate-pdok-layers-config.sh pdokservicesplugin/resources/layers-pdok.json
```

Create symlink to QGIS plugin directory from repository directory: 

- Windows:

```bat
Rem maak een QGIS profiel aan met de naam "pdokplugin-develop"
mklink /d "%APPDATA%\QGIS\QGIS3\profiles\pdokplugin-develop\python\plugins\pdokservicesplugin" "%REPODIR%\pdokservicesplugin"
```

- Linux (Ubuntu):

```sh
# maak een QGIS profiel aan met de naam "pdokplugin-develop"
symlink_path "$(realpath ~)/.local/share/QGIS/QGIS3/profiles/pdokplugin-develop/python/plugins/pdokservicesplugin"
mkdir -p $(dirname "$symlink_path")
ln -s "$(pwd)/pdokservicesplugin" "$symlink_path" # uitvoeren vanuit root van repo
```

- macOS:

```sh
# maak een QGIS profiel aan met de naam "pdokplugin-develop"
symlink_path="/Users/$USER/Library/Application Support/QGIS/QGIS3/profiles/pdokplugin-develop/python/plugins/pdokservicesplugin"
mkdir -p $(dirname "$symlink_path")
ln -s "$(pwd)/pdokservicesplugin" "$symlink_path" # uitvoeren vanuit root van repo
```

Optionally: extend the layers config file using OGC:API urls, see [`scripts/modify-layers-pdok-ogcapi.py`](scripts/modify-layers-pdok-ogcapi.py) for more detailed instructions.