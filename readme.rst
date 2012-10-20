PDOK Service Plugin
-------------------

English
-------

This plugin is probably only interesting for the dutch audience.

It shows a list of available web services (WMS, WMTS, WFS etc) from our
national data services (in our national crs epsg:28992).
Further information in dutch below.

Nederlands
----------

PDOK (Publieke Data Op de Kaart) is een eenvoudige plugin om de verschillende 
PDOK services te testen of te bekijken.

Op basis van een json bestand (IN de plugin) met alle op dit moment beschikbare
services wordt een dialoog opgebouwd met daarin 
- het soort service (WMS, WMTS, WFS of TMS)
- de naam van de service
- een regel per laag van de service

Door op een item te klikken wordt de service direkt aangeroepen een getoond.

Alle services zijn epsg:28992

QGIS versie 1.8 kan alleen de WMS en WFS services van PDOK laden

QGIS ontwikkel versie (master) kan WMS, WMTS en WFS services laden

