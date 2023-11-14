## PDOK Service Plugin

## English

This plugin is probably only interesting for the dutch audience.

It shows a list of available web services (WMS, WMTS, WFS, OGC:API tiles etc) from our
national data services (in our national crs EPSG:28992).
Further information in dutch below.

If you think this plugin is useful, consider to donate via Paypal button below, OR sent me a kind email of tweet :-)

## Nederlands

PDOK (Publieke Dienstverlening Op de Kaart) is een plugin om de verschillende
PDOK services te testen of te bekijken.

Op basis van een json bestand (IN de plugin) met alle op dit moment beschikbare services wordt een dialoog opgebouwd met daarin

- het soort service (WMS, WMTS, WFS, TMS, OGC:API tiles)
- de naam van de service
- een regel per laag van de service

Door op een item te klikken wordt de service direct aangeroepen een getoond.

Alle services zijn minstens in EPSG:28992 beschikbaar

[![paypal](https://www.paypalobjects.com/en_US/NL/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=DZ8R5JPAW55CJ&currency_code=EUR&source=url)

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

Generate `ui_pdokservicesplugindialog.py` from `ui_pdokservicesplugindialog.ui`:

```sh
cd pdokservicesplugin
pyuic5 ui_pdokservicesplugindialog.ui -o ui_pdokservicesplugindialog.py
```

Escape HTML info pagina and insert into `ui_pdokservicesplugindialog.ui` and regenerate `ui_pdokservicesplugindialog.py`:

```sh
cd pdokservicesplugin
xmlstarlet ed -u  ".//widget[@name='webView']/property[@name='html']/string" -v "$(sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g; s/'"'"'/\&#39;/g' < resources/infotab.html)" ui_pdokservicesplugindialog.ui |\
    xmlstarlet unesc |\
    sponge ui_pdokservicesplugindialog.ui &&\
        pyuic5 ui_pdokservicesplugindialog.ui -o ui_pdokservicesplugindialog.py &&\
            black ui_pdokservicesplugindialog.py
```

Compile `resources_rc.py` file:

```sh
cd pdokservicesplugin
pyrcc5 resources.qrc -o resources_rc.py &&
    black resources_rc.py
```

Update layers config file in [`pdokservicesplugin/resources/layers-pdok.json`](pdokservicesplugin/resources/layers-pdok.json) (run from root of repo):

```sh
scripts/generate-pdok-layers-config.sh pdokservicesplugin/resources/layers-pdok.json
```

Create symlink to QGIS plugin directory from repository directory (Windows):

```bat
Rem maak een QGIS profiel aan met de naam "pdokplugin-develop"
mklink /d "%APPDATA%\QGIS\QGIS3\profiles\pdokplugin-develop\python\plugins\pdokservicesplugin" "%REPODIR%\pdokservicesplugin"
```

Create symlink to QGIS plugin directory from repository directory (Ubuntu):

```sh
# maak een QGIS profiel aan met de naam "pdokplugin-develop"
symlink_path "$(realpath ~)/.local/share/QGIS/QGIS3/profiles/pdokplugin-develop/python/plugins/pdokservicesplugin"
mkdir -p $(dirname "$symlink_path")
ln -s "$(pwd)/pdokservicesplugin" "$symlink_path" # uitvoeren vanuit root van repo
```
