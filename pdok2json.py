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

from xml.dom.minidom import parse
import urllib

def childNodeValue(node, childName):
    nodes = node.getElementsByTagName(childName)
    if len(nodes)==1 and nodes[0].hasChildNodes():
        return nodes[0].childNodes[0].nodeValue
    if len(nodes)>1:
        arr = u''
        for child in nodes:
            # extra check, we only want direct childs
            if child.parentNode.nodeName==node.nodeName and child.hasChildNodes():
                arr+=(child.childNodes[0].nodeValue)
                arr+=','
        return arr.rstrip(',')
    return ""

def handleWCS(wcscapsurl):
    dom = parse(urllib.urlopen(wcscapsurl))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/ahn25m/wcs?request=getcapabilities'))
    contents = dom.getElementsByTagName('wcs:Contents')[0]
    url = ''
    for subelement in dom.getElementsByTagName('ows:Operation'):
        if subelement.getAttribute('name')=='GetCoverage':
            url = subelement.getElementsByTagName('ows:Get')[0].getAttribute('xlink:href')
    global firstOne
    comma = ''
    servicetitle = childNodeValue(dom.getElementsByTagName('ows:ServiceIdentification')[0], 'ows:Title')
    for coverage in contents.getElementsByTagName('wcs:CoverageSummary'):
        title = childNodeValue(coverage, 'ows:Title')
        layername = childNodeValue(coverage, 'wcs:Identifier')
        abstract = childNodeValue(coverage, 'ows:Abstract')
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = unicode('%s{"type":"wcs","title":"%s","abstract":"%s","url":"%s","layers":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            print s,
            firstOne=False
        except Exception, e:
            #pass
            print "\n\nFout!! In laag: %s" % layername
            print e
            return

def handleWFS(wfscapsurl):
    dom = parse(urllib.urlopen(wfscapsurl))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/ahn25m/wfs?version=1.0.0&request=GetCapabilities'))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/bagviewer/wfs?request=getcapabilities'))
    global firstOne
    # some service run WFS 1.0.0 while others run 2.0.0
    servicetitle = ''
    if len(dom.getElementsByTagName('Service'))>0:
        servicetitle = childNodeValue(dom.getElementsByTagName('Service')[0], 'Title')
    elif len(dom.getElementsByTagName('ows:ServiceIdentification'))>0:
        servicetitle = childNodeValue(dom.getElementsByTagName('ows:ServiceIdentification')[0], 'ows:Title')
    featuretypes = dom.getElementsByTagName('FeatureType')
    for featuretype in featuretypes:
        layername = childNodeValue(featuretype, 'Name')
        title = childNodeValue(featuretype, 'Title')
        abstract = childNodeValue(featuretype, 'Abstract')
        # abstract can have newlines in it, which create havoc in json
        # because we only use abstract in html, we make <br/> of them
        abstract = abstract.replace('\r', '')
        abstract = abstract.replace('\t', ' ')
        abstract = abstract.replace('\n', '<br/>')
        url = wfscapsurl
        comma = ''
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = unicode('%s{"type":"wfs","title":"%s","abstract":"%s","url":"%s","layers":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            print s,
            firstOne=False
        except Exception, e:
            #pass
            print "\n\nFout!! In laag: %s" % layername
            print e
            return


def handleWMTS(wmtscapsurl):
    #dom = parse("wmts-getcapabilities_1.0.0.xml")
    dom = parse(urllib.urlopen(wmtscapsurl))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/wmts?VERSION=1.0.0&request=GetCapabilities'))
    #dom = parse(urllib.urlopen('http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml'))
    #url = dom.getElementsByTagName('ows:ProviderSite')[0].getAttribute('xlink:href')
    url = wmtscapsurl
    servicetitle = dom.getElementsByTagName('ows:ServiceIdentification')[0].getElementsByTagName('ows:Title')[0].childNodes[0].nodeValue
    contents = dom.getElementsByTagName('Contents')[0]
    global firstOne
    for layer in contents.getElementsByTagName('Layer'):
        title = childNodeValue(layer, 'ows:Title')
        layername = childNodeValue(layer, 'ows:Identifier')
        imgformats = childNodeValue(layer, 'Format')
        tilematrixsets = childNodeValue(layer, 'TileMatrixSet')
        #print '\n'
        #print title
        #print layername
        #print imgformats
        #print tilematrixsets
        # wmts does not have some kind of abstract or description :-(
        abstract = ''
        # {"naam":"WMTS Agrarisch Areaal Nederland","url":"http://geodata.nationaalgeoregister.nl/tiles/service/wmts/aan","layers":["aan"],"type":"wmts","pngformaat":"image/png"},
        comma = ''
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = unicode('%s{"type":"wmts","title":"%s","abstract":"%s","url":"%s","layers":"%s","imgformats":"%s","tilematrixsets":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, imgformats, tilematrixsets, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            print s,
            firstOne=False
        except Exception, e:
            #pass
            print "\n\nFout!! In laag: %s" % layername
            print e
            return

def handleWMS(wmscapsurl):
    #dom = parse("wms-getcapabilities_1.3.0.xml")
    #dom = parse("wms_cbs.xml")
    #dom = parse("problem.xml")
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/cbsvierkanten100m/wms?request=GetCapabilities'))
    dom = parse(urllib.urlopen(wmscapsurl))
    cap = dom.getElementsByTagName('Capability')
    getmap = cap[0].getElementsByTagName('GetMap');
    url = getmap[0].getElementsByTagName('OnlineResource')[0].getAttribute('xlink:href')
    servicetitle = childNodeValue(dom.getElementsByTagName('Service')[0], 'Title')
    global firstOne
    root = dom.getElementsByTagName('Layer')[0]
    for layer in root.getElementsByTagName('Layer'):
        title = childNodeValue(layer, 'Title')
        layername = childNodeValue(layer, 'Name')
        abstract = childNodeValue(layer, 'Abstract')
        maxscale = childNodeValue(layer, 'MaxScaleDenominator')
        minscale = childNodeValue(layer, 'MinScaleDenominator')
        # abstract can have newlines in it, which create havoc in json
        # because we only use abstract in html, we make <br/> of them
        abstract = abstract.replace('\r', '')
        abstract = abstract.replace('\t', ' ')
        abstract = abstract.replace('\n', '<br/>')
        comma = ''
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = unicode('%s{"type":"wms","title":"%s","abstract":"%s","url":"%s","layers":"%s","minscale":"%s","maxscale":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, minscale, maxscale, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            print s,
            firstOne=False
        except Exception, e:
            #pass
            print "\n\nFout!! In laag: %s" % layername
            print e
            return

# services zoals genoemd in https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/
services = [
# alle wmts lagen (behalve luchtfoto) zitten in 1 service
('wmts', 'PDOK luchtfoto', 'http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml'),
('wmts', 'PDOK overige services', 'http://geodata.nationaalgeoregister.nl/wmts?VERSION=1.0.0&request=GetCapabilities'),
# GESLOTEN
#('wms', 'Asbest scholenkaart (WMS | PDOK Basis)', 'http://geodata.nationaalgeoregister.nl/asbestscholenkaart/wms?SERVICE=WMS&request=GetCapabilities'),
# GESLOTEN
#('wfs', 'Asbest scholenkaart (WFS | PDOK Basis)', 'http://geodata.nationaalgeoregister.nl/asbestscholenkaart/wfs?version=1.0.0&request=GetCapabilities'),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/a
('wms', 'AAN (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/aan/wms?request=GetCapabilities') ,
('wfs','AAN (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/aan/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'Adressen (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/inspireadressen/wms?SERVICE=WMS&request=GetCapabilities') ,
('wfs', 'Adressen (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/inspireadressen/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'Ahn25m (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/ahn25m/wms?service=wms&request=getcapabilities') ,
('wfs' , 'Ahn25m (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/ahn25m/wfs?version=1.0.0&request=GetCapabilities') ,
('wcs','AHN (WCS | Open)', 'http://geodata.nationaalgeoregister.nl/ahn25m/wcs?request=getcapabilities') ,
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/b
('wfs' , 'BAG (tijdelijk) (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/bagviewer/wfs?request=getcapabilities') ,
('wms', 'BAG (tijdelijk) (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/bagviewer/wms?request=getcapabilities') ,
('wfs' , 'BBG 2008 (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'BBG 2008 (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wms?request=getcapabilities') ,
('wfs' , 'Bekendmakingen (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/pdok/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'Beschermde natuurmonumenten (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/ows?service=wms&request=getcapabilities') ,
('wfs' , 'Beschermde natuurmonumenten (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'Bestuurlijke grenzen (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wms?&Request=getcapabilities') ,
('wfs' , 'Bestuurlijke grenzen (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'BRP Gewaspercelen (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/brpgewaspercelen/wms?request=GetCapabilities') ,
('wfs' , 'BRP Gewaspercelen (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/brpgewaspercelen/wfs?version=1.0.0&request=GetCapabilities') ,
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/c
('wms', 'CBS Bevolkingskernen 2008 (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wms?request=getcapabilities') ,
('wfs' , 'CBS Bevolkingskernen 2008 (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Vierkantstatistieken 100m (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/cbsvierkanten100m/wms?request=GetCapabilities') ,
('wfs' , 'CBS Vierkantstatistieken 100m (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/cbsvierkanten100m/wfs?request=GetCapabilities') ,
('wms', 'CBS Vierkantstatistieken 500m (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/cbsvierkanten500m/wms?request=GetCapabilities') ,
('wfs' , 'CBS Vierkantstatistieken 500m (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/cbsvierkanten500m/wfs?request=GetCapabilities') ,
('wms', 'CBS Wijken en Buurten 2009 (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wms?request=getcapabilities') ,
('wfs' , 'CBS Wijken en Buurten 2009 (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wfs?version=1.0.0&request=getcapabilities') ,
('wms', 'CBS Wijken en Buurten 2010 (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wms?request=getcapabilities') ,
('wfs' , 'CBS Wijken en Buurten 2010 (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wfs?version=1.0.0&request=getcapabilities') ,
('wms', 'CBS Wijken en Buurten 2011 (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wms?request=getcapabilities') ,
('wfs' , 'CBS Wijken en Buurten 2011 (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wfs?version=1.0.0&request=getcapabilities') ,
('wms', 'CBS Wijken en Buurten 2012 (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wms?request=getcapabilities') ,
('wfs' , 'CBS Wijken en Buurten 2012 (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wfs?version=1.0.0&request=getcapabilities') ,
('wms', 'CultGIS (WMS | Open) ', 'http://geodata.nationaalgeoregister.nl/cultgis/wms?SERVICE=WMS&request=GetCapabilities') ,
('wfs', 'CultGIS (WFS | Open) ', 'http://geodata.nationaalgeoregister.nl/cultgis/wfs?version=1.0.0&request=GetCapabilities') ,
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/d
('wms', 'DTB (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'DTB (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wfs?version=1.0.0&request=GetCapabilities'),
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/f
('wms', 'Fietsknooppunten (WMS | Open)','http://geodata.nationaalgeoregister.nl/fietsknooppuntennetwerk/wms?request=GetCapabilities'),
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/k
# GESLOTEN alleen na aanmelding: 
#('wms', 'Kadastrale kaart (WMS | PDOK Basis)','http://geodata.nationaalgeoregister.nl/kadastralekaart/wms?SERVICE=WMS&request=GetCapabilities'),
# GESLOTEN alleen na aanmelding, maar zit ook al in de algemene service
# ('wmts',  'Kadastrale kaart (WMTS | PDOK Basis)', 'http://geodata.nationaalgeoregister.nl/wmts/kadastralekaart?VERSION=1.0.0&request=GetCapabilities'),
# zit in algememe wmts caps: Kadastrale kaart (WMTS | PDOK Basis) http://geodata.nationaalgeoregister.nl/wmts/kadastralekaart?VERSION=1.0.0&request=GetCapabilities
# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/l
('wms', 'Landelijke fietsroutes (WMS | Open) ','http://geodata.nationaalgeoregister.nl/lfroutes/wms?request=GetCapabilities'),
('wms', 'Lange afstandswandelroutes (WMS | Open) ','http://geodata.nationaalgeoregister.nl/lawroutes/wms?request=GetCapabilities'),
('wms', 'Luchtfoto (PDOK-achtergrond) (WMS | Open) ','http://geodata1.nationaalgeoregister.nl/luchtfoto/wms?request=GetCapabilities'),
# zit in algememe wmts caps: Luchtfoto (PDOK-achtergrond) (WMTS | Open) http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml
# GESLOTEN ACHTER PKI
#('wms', 'Luchtfoto Landelijke Voorziening Beeldmateriaal (2012) (WMS | Gesloten) ','https://secure.geodata2.nationaalgeoregister.nl/lv-beeldmateriaal/2012/wms?'),
# GESLOTEN ACHTER PKI
#('wms', 'Luchtfoto Landelijke Voorziening Beeldmateriaal (2013) (WMS | Gesloten) ','https://secure.geodata2.nationaalgeoregister.nl/lv-beeldmateriaal/2013/wms?'),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/n
('wms', 'Nationale Streekpaden (WMS | Open) ','http://geodata.nationaalgeoregister.nl/streekpaden/wms?request=GetCapabilities'),
('wms', 'NationaleParken (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nationaleparken/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'NationaleParken (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nationaleparken/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Natura 2000 (WMS | Open) ','http://geodata.nationaalgeoregister.nl/natura2000/wms?&request=getcapabilities'),
('wfs', 'Natura 2000 (WFS | Open) ','http://geodata.nationaalgeoregister.nl/natura2000/wfs?version=1.0.0&request=GetCapabilities'),
# zit in algememe wmts caps: Natura 2000 (WMTS | Open) http://geodata.nationaalgeoregister.nl/tiles/service/wmts/natura2000?VERSION=1.0.0&request=GetCapabilities
# geen TMS: Natura 2000 (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/natura2000@EPSG:28992@png8
('wms', 'NHI  (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nhi/ows?service=wms&request=getcapabilities'),
('wfs', 'NHI  (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nhi/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'NOK 2007 (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nok2007/wms?service=wms&request=getcapabilities'),
('wms', 'NOK 2010 (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nok2010/wms?service=wms&request=getcapabilities'),
('wfs', 'NOK 2011 (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nok2011/wfs?version=1.0.0&request=GetCapabilities'),
# zit in algememe wmts caps: NOK 2011 (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/nok2011?VERSION=1.0.0&request=GetCapabilities
('wms', 'NOK 2011 (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nok2011/wms?service=wms&request=getcapabilities'),
# geen TMS: NOK 2011 (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/nok2011@EPSG:28992@png8
('wms', 'NOK 2012 (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nok2012/wms?request=GetCapabilities'),
('wfs', 'NOK 2012 (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nok2012/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'Noordzee Kabels en Leidingen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/noordzeekabelsenleidingen/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'Noordzee Maritieme grenzen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/maritiemegrenzen/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'Noordzee Vaarwegmarkeringen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/noordzeevaarwegmarkeringenrd/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'Noordzee Wingebieden (WFS | Open) ','http://geodata.nationaalgeoregister.nl/noordzeewingebieden/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'NWB-Spoorwegen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nwbspoorwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'NWB-Spoorwegen (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nwbspoorwegen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'NWB-Vaarwegen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nwbvaarwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'NWB-Vaarwegen (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nwbvaarwegen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'NWB-Wegen (WFS | Open) ','http://geodata.nationaalgeoregister.nl/nwbwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'NWB-Wegen (WMS | Open) ','http://geodata.nationaalgeoregister.nl/nwbwegen/wms?SERVICE=WMS&request=GetCapabilities'),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/r
('wms', 'RDinfo (WMS | Open) ','http://geodata.nationaalgeoregister.nl/rdinfo/wms?service=wms&request=getcapabilities'),
('wfs', 'RDinfo (WFS | Open) ','http://geodata.nationaalgeoregister.nl/rdinfo/wfs?version=1.0.0&request=GetCapabilities'),
# OP DIT MOMENT STUK: 
('wms', 'Ruimtelijke plannen (WMS | Open) ','http://geodata.nationaalgeoregister.nl/plu/wms?service=wms&request=getcapabilities'),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/t
# zit in algememe wmts caps: TOP10NL (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top10nl?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP10NL (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top10nl@EPSG:28992@png8
('wms', 'TOP10NL (WMS | Open) ','http://geodata.nationaalgeoregister.nl/top10nl/wms?SERVICE=WMS&request=GetCapabilities'),
# zit in algememe wmts caps: TOP250raster (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top250raster?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP250raster (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top250raster@EPSG:28992@png8
('wms', 'TOP250raster (WMS | Open) ','http://geodata.nationaalgeoregister.nl/top250raster/wms?&Request=getcapabilities'),
# zit in algememe wmts caps: TOP50raster (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top50raster?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP50raster (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top50raster@EPSG:28992@png8
('wms', 'TOP50raster (WMS | Open) ','http://geodata.nationaalgeoregister.nl/top50raster/wms?&Request=getcapabilities'),
# zit in algememe wmts caps: TOP50vector (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top50vector?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP50vector (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top50vector@EPSG:28992@png8
('wms', 'TOP50vector (WMS | Open) ','http://geodata.nationaalgeoregister.nl/top50vector/wms?&Request=getcapabilities'),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/v
('wms', 'ViN (WMS | Open) ','http://geodata.nationaalgeoregister.nl/vin/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'ViN (WFS | Open) ','http://geodata.nationaalgeoregister.nl/vin/wfs?version=1.0.0&request=GetCapabilities '),
# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/w
('wms', 'Weggeg (WMS | Open) ','http://geodata.nationaalgeoregister.nl/weggeg/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Weggeg (WFS | Open) ','http://geodata.nationaalgeoregister.nl/weggeg/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Wetlands (WMS | Open) ','http://geodata.nationaalgeoregister.nl/wetlands/ows?service=wms&request=getcapabilities'),
('wfs', 'Wetlands (WFS | Open) ','http://geodata.nationaalgeoregister.nl/wetlands/wfs?version=1.0.0&request=GetCapabilities'),
]

# testing
#services = [ ('wcs', 'ff', 'ff') ]

#services = [
## https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/a
#('wms', 'AAN (WMS | Open)',
#'http://geodata.nationaalgeoregister.nl/aan/wms?request=GetCapabilities')
#,
#('wfs','AAN (WFS | Open)',
#'http://geodata.nationaalgeoregister.nl/aan/wfs?version=1.0.0&request=GetCapabilities')
#,
#('wcs','AHN (WCS | Open)',
#'http://geodata.nationaalgeoregister.nl/ahn25m/wcs?request=getcapabilities')
#,
#('wmts', 'PDOK luchtfoto',
#'http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml')
#]

#services = [ 
## GESLOTEN
#('wms', 'Asbest scholenkaart (WMS | PDOK Basis)','http://geodata.nationaalgeoregister.nl/asbestscholenkaart/wms?SERVICE=WMS&request=GetCapabilities'),
## GESLOTEN
#('wfs', 'Asbest scholenkaart (WFS | PDOK Basis)','http://geodata.nationaalgeoregister.nl/asbestscholenkaart/wfs?version=1.0.0&request=GetCapabilities'),
## GESLOTEN alleen na aanmelding: 
#('wms', 'Kadastrale kaart (WMS | PDOK Basis)','http://geodata.nationaalgeoregister.nl/kadastralekaart/wms?SERVICE=WMS&request=GetCapabilities'),
#('wmts',  'Kadastrale kaart (WMTS | PDOK Basis)', 'http://geodata.nationaalgeoregister.nl/wmts/kadastralekaart?VERSION=1.0.0&request=GetCapabilities'),
## GESLOTEN ACHTER PKI
##('wms', 'Luchtfoto Landelijke Voorziening Beeldmateriaal (2012) (WMS | Gesloten) ','https://secure.geodata2.nationaalgeoregister.nl/lv-beeldmateriaal/2012/wms?'),
## GESLOTEN ACHTER PKI
#('wms', 'Luchtfoto Landelijke Voorziening Beeldmateriaal (2013) (WMS | Gesloten) ','https://secure.geodata2.nationaalgeoregister.nl/lv-beeldmateriaal/2013/wms?'),
## OP DIT MOMENT STUK: 
#('wms', 'Ruimtelijke plannen (WMS | Open) ','http://geodata.nationaalgeoregister.nl/plu/wms?service=wms&request=getcapabilities'),
#

firstOne = True
print '{"services":[',

for (stype, title, url) in services:
    if stype == 'wms':
        handleWMS(url)
    elif stype == 'wmts':
        handleWMTS(url)
    elif stype == 'wfs':
        handleWFS(url)
    elif stype == 'wcs':
        handleWCS(url)

print ']}'
