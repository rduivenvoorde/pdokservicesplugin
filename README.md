## PDOK Service Plugin

## English

This plugin is probably only interesting for the dutch audience.

It shows a list of available web services (WMS, WMTS, WFS etc) from our
national data services (in our national crs epsg:28992).
Further information in dutch below.

If you think this plugin is usefull, consider to donate via Paypal button below, OR sent me a kind email of tweet :-)

## Nederlands

PDOK (Publieke Data Op de Kaart) is een plugin om de verschillende
PDOK services te testen of te bekijken.

Op basis van een json bestand (IN de plugin) met alle op dit moment beschikbare services wordt een dialoog opgebouwd met daarin

- het soort service (WMS, WMTS, WFS of TMS)
- de naam van de service
- een regel per laag van de service

Door op een item te klikken wordt de service direkt aangeroepen een getoond.

Alle services zijn epsg:28992

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

Create symlink to QGIS plugin directory from repository directory (Windows):

```bat
Rem maak eenv QGIS profiel aan met de naam "pdokplugin-develop"
mklink /d "%APPDATA%\QGIS\QGIS3\profiles\pdokplugin-develop\python\plugins\pdokservicesplugin" "%REPODIR%\pdokservicesplugin"
```

### Update PDOK Layer Config File

To update the [PDOK layers config file](./pdokservicesplugin/resources/layers-pdok.json) run the [`spider/update-pdok-layers.sh`](spider/update-pdok-layers.sh) Bash script. The bash script runs a docker container running 
[pdok/ngr-services-spider](https://github.com/pdok/ngr-services-spider). 

Run script without arguments to update PDOK layers configuration file:

```sh
spider/update-pdok-layers.sh
```

To inspect the options to the script run:


```sh
spider/update-pdok-layers.sh -h
```
