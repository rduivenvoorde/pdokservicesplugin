# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin pdok2json.py

 Dit is een ruw python script om op basis van een rij service-url's
 (wms, wfs, wcs en wmts) de capabilities van elke service op te halen, en 
 van elke 'laag' in die service een json object aan te maken me wat gegevens
 van die laag.

 Deze json wordt gebruikt om het bestandje pdok.json aan te maken
 python:
    python pdok2json.py > pdok.json
 Dit bestand wordt in de PdokServicePlugin ingeladen om alle lagen te tonen.

 Op dit moment werkt het voor alle services die in het 'services' object 
 onderin deze file staan. 
 De PDOK services zijn echter een bonte mengeling van versie en services en
 hier en daar was een kleine hack nodig om ze allemaal te kunnen parsen.
 
 Theoretisch kun je dus zelf een paar services toevoegen, maar houd rekening
 met hickups :-)

    begin                : 2013-11-01
    copyright            : (C) 2012 by Richard Duivenvoorde
    email                : richard@duif.net
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""


"""

NOTE: THIS FILE IS NOT USED ANYMORE FOR RECENT GENERATION OF pdok.json file

PLEASE GO TO THE QGIS3 VERSION OF THE PLUGIN TO SEE CURRENT VERSION

"""