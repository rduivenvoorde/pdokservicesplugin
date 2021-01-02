#!/usr/bin/env python3

# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin pdok2json.py

 Dit is een ruw python script om op basis van een rij service-url's
 (wms, wfs, wcs en wmts) de capabilities van elke service op te halen, en
 van elke 'laag' in die service een json object aan te maken met wat gegevens
 van die laag.

 Deze json wordt gebruikt om het bestandje pdok.json aan te maken
 met python3 (LET OP alleen python3 werkt nu ivm encoding probleempjes)
    python3 pdok2json.py > pdok.json
 Dit bestand wordt in de PdokServicePlugin ingeladen om alle lagen te tonen.

 Url's afkomstig van https://www.pdok.nl/datasets

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
from xml.dom.minidom import parse, parseString
import urllib.request, urllib.parse, urllib.error
import re

TIME_OUT = 10

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
    dom = parse(urllib.request.urlopen(wcscapsurl, timeout=TIME_OUT))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/ahn25m/wcs?request=getcapabilities'))
    if len(dom.getElementsByTagName('wcs:Contents'))>0:
        contents = dom.getElementsByTagName('wcs:Contents')[0]
    elif len(dom.getElementsByTagName('Contents'))>0:
        contents = dom.getElementsByTagName('Contents')[0]
    elif len(dom.getElementsByTagName('ows:Contents'))>0:
        contents = dom.getElementsByTagName('ows:Contents')[0]
    url = ''
    for subelement in dom.getElementsByTagName('ows:Operation'):
        if subelement.getAttribute('name')=='GetCoverage':
            url = subelement.getElementsByTagName('ows:Get')[0].getAttribute('xlink:href')
    global firstOne
    comma = ''
    servicetitle = childNodeValue(dom.getElementsByTagName('ows:ServiceIdentification')[0], 'ows:Title')
    for coverage in contents.getElementsByTagName('CoverageSummary'):
        title = childNodeValue(coverage, 'ows:Title')
        layername = childNodeValue(coverage, 'Identifier')
        abstract = childNodeValue(coverage, 'ows:Abstract')
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = str('\n%s{"type":"wcs","title":"%s","abstract":"%s","url":"%s","layers":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            # fix_print_with_import
            print(s.decode('utf-8'), end=' ')
            firstOne=False
        except Exception as e:
            #pass
            # fix_print_with_import
            print("\n\nFout!! In laag: %s" % layername)
            # fix_print_with_import
            print(e)
            return

def handleWFS(wfscapsurl):
    #print(wfscapsurl)
    #dom = parse(urllib.urlopen(wfscapsurl))
    #  ^^ that is not working for some wicked cbs caps with coördinaat in it...
    # hack: read string and find replace coördinaat with coordinaat
    response = urllib.request.urlopen(wfscapsurl, timeout=TIME_OUT)
    #response = urllib.urlopen('problem.xml')
    string = response.read()
    # cbs vierkanten
    #string = re.sub(r"co.{1,2}rdin","coordin", string)
    # rdinfo
    #string = re.sub(r"<WFS_Capabilities","\n<WFS_Capabilities", string)
    #print string
    #return
    dom = parseString(string)
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/ahn25m/wfs?version=1.0.0&request=GetCapabilities'))
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/bagviewer/wfs?request=getcapabilities'))
    global firstOne
    # some service run WFS 1.0.0 while others run 2.0.0
    servicetitle = ''
    if len(dom.getElementsByTagName('Service'))>0:
        servicetitle = childNodeValue(dom.getElementsByTagName('Service')[0], 'Title')
    elif len(dom.getElementsByTagName('ows:ServiceIdentification'))>0:
        servicetitle = childNodeValue(dom.getElementsByTagName('ows:ServiceIdentification')[0], 'ows:Title')
    # servicetitle can have newlines in it sometimes, which create havoc in json
    servicetitle = servicetitle.replace('\r', '')
    servicetitle = servicetitle.replace('\t', ' ')
    servicetitle = servicetitle.replace('\n', ' ')

    url = wfscapsurl
    # mmm beter find the GetFeatures Get
    operations = dom.getElementsByTagName('Operation')
    if len(operations)==0:
        operations = dom.getElementsByTagName('ows:Operation')
    for op in operations:
        if op.hasAttribute('name') and op.getAttribute('name').upper()=='GETFEATURE':
            get = op.getElementsByTagName('Get')
            if len(get)==0:
                get = op.getElementsByTagName('ows:Get')
            url = get[0].getAttribute('xlink:href')
    featuretypes = dom.getElementsByTagName('FeatureType')
    if len(featuretypes)==0:
        # let's try wfs:FeatureType
        featuretypes = dom.getElementsByTagName('wfs:FeatureType')
    for featuretype in featuretypes:
        layername = childNodeValue(featuretype, 'Name')
        if len(layername)==0:
            layername = childNodeValue(featuretype, 'wfs:Name')
        title = childNodeValue(featuretype, 'Title')
        if len(title)==0:
            title = childNodeValue(featuretype, 'wfs:Title')
        # title can have newlines in it sometimes, which create havoc in json
        title = title.replace('\r', '')
        title = title.replace('\t', ' ')
        title = title.replace('\n', ' ')
        abstract = childNodeValue(featuretype, 'Abstract')
        if len(abstract)==0:
            abstract = childNodeValue(featuretype, 'wfs:Abstract')
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
            s = str('\n%s{"type":"wfs","title":"%s","abstract":"%s","url":"%s","layers":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            # fix_print_with_import
            print(s.decode('utf-8'), end=' ')
            firstOne = False
        except Exception as e:
            #pass
            # fix_print_with_import
            print("\n\nFout!! In laag: %s" % layername)
            # fix_print_with_import
            print(e)
            return


def handleWMTS(wmtscapsurl):
    #dom = parse("wmts-getcapabilities_1.0.0.xml")
    dom = parse(urllib.request.urlopen(wmtscapsurl, timeout=TIME_OUT))
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

        tilematrixsets=[]
        for x in layer.getElementsByTagName('TileMatrixSet'):
            tilematrixsets.append(x.childNodes[0].nodeValue)
        tilematrixsets = ",".join(tilematrixsets)

        # wmts does not have some kind of abstract or description :-(
        abstract = ''
        # {"naam":"WMTS Agrarisch Areaal Nederland","url":"http://geodata.nationaalgeoregister.nl/tiles/service/wmts/aan","layers":["aan"],"type":"wmts","pngformaat":"image/png"},
        comma = ''
        try:
            if not firstOne:
                comma = ','
            # some extract have strange chars, we decode to utf8
            s = str('\n%s{"type":"wmts","title":"%s","abstract":"%s","url":"%s","layers":"%s","imgformats":"%s","tilematrixsets":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, imgformats, tilematrixsets, servicetitle)).encode('utf8')
            # the comma behind the print makes print NOT add a \n newline behind it
            # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
            # fix_print_with_import
            print(s.decode('utf-8'), end=' ')
            firstOne = False
        except Exception as e:
            #pass
            # fix_print_with_import
            print("\n\nFout!! In laag: %s" % layername)
            # fix_print_with_import
            print(e)
            return

def handleWMS(wmscapsurl):
    #dom = parse("wms-getcapabilities_1.3.0.xml")
    #dom = parse("wms_cbs.xml")
    #dom = parse("problem.xml")
    #dom = parse(urllib.urlopen('http://geodata.nationaalgeoregister.nl/cbsvierkanten100m/wms?request=GetCapabilities'))
    #dom = parse(urllib.urlopen(wmscapsurl))
    #  ^^ that is not working for some wicked cbs caps with coördinaat in it...
    # hack: read string and find replace coördinaat with coordinaat
    response = urllib.request.urlopen(wmscapsurl, timeout=TIME_OUT)
    string = response.read()
    #string = re.sub(r"co.+rdin","coordin", str(string))
    dom = parseString(string)

    cap = dom.getElementsByTagName('Capability')
    getmap = cap[0].getElementsByTagName('GetMap');
    url = getmap[0].getElementsByTagName('OnlineResource')[0].getAttribute('xlink:href')
    imgformats = childNodeValue(getmap[0], 'Format')
    # formats can have newlines in it sometimes, which create havoc in json
    imgformats = imgformats.replace('\r', '')
    imgformats = imgformats.replace('\t', ' ')
    imgformats = imgformats.replace('\n', ' ')
    servicetitle = childNodeValue(dom.getElementsByTagName('Service')[0], 'Title')
    global firstOne
    root = dom.getElementsByTagName('Layer')[0]
    baseCRS = []
    for subnode in root.childNodes:
            if subnode.nodeType == dom.ELEMENT_NODE and subnode.tagName == 'CRS':
                baseCRS.append(subnode.childNodes[0].nodeValue)
    if (len(baseCRS) == 0):
        baseCRS.append('EPSG:28992')
    for layer in root.getElementsByTagName('Layer'):
        #print(layer)
        # xtra check, if this is again a grouping layer, skip it
        # actually needed for habitatrichtlijn layers
        if len(layer.getElementsByTagName('Layer'))>1:
            #print('PASSING?')
            pass
        else:
            title = childNodeValue(layer, 'Title')
            # title can have newlines in it sometimes, which create havoc in json
            title = title.replace('\r', '')
            title = title.replace('\t', ' ')
            title = title.replace('\n', ' ')
            #print '|'
            #print(title)
            layername = childNodeValue(layer, 'Name')
            abstract = childNodeValue(layer, 'Abstract')
            maxscale = childNodeValue(layer, 'MaxScaleDenominator')
            minscale = childNodeValue(layer, 'MinScaleDenominator')
            #meta = layer.getElementsByTagName('MetadataURL')
            #if meta != None:
            #    print "URL%s"%meta[0].getElementsByTagName('OnlineResource')[0].getAttribute('xlink:href')
            # abstract can have newlines in it, which create havoc in json
            # because we only use abstract in html, we make <br/> of them
            abstract = abstract.replace('\r', '')
            abstract = abstract.replace('\t', ' ')
            abstract = abstract.replace('\n', '<br/>')
            crs = list(baseCRS)
            for subnode in layer.childNodes:
                if subnode.nodeType == dom.ELEMENT_NODE and subnode.tagName == 'CRS':
                    nodevalue = subnode.childNodes[0].nodeValue
                    if nodevalue not in crs:
                        crs.append(nodevalue)
            crs=",".join(crs)
            comma = ''
            handled = False
            handled_styles = []
            for style in layer.getElementsByTagName('Style'):
                styleName = childNodeValue(style, 'Name')
                if styleName in handled_styles:
                    continue
                try:
                    if not firstOne:
                        comma = ','
                    # some extract have strange chars, we decode to utf8
                    s = str('\n%s{"type":"wms","title":"%s","abstract":"%s","url":"%s","layers":"%s","minscale":"%s","maxscale":"%s","servicetitle":"%s","imgformats":"%s", "style":"%s","crs":"%s"}' % (comma, title, abstract, url, layername, minscale, maxscale, servicetitle, imgformats, styleName, crs)).encode('utf8')
                    # the comma behind the print makes print NOT add a \n newline behind it
                    # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
                    # fix_print_with_import
                    print(s.decode('utf-8'), end=' ')
                    firstOne = False
                    handled = True
                    handled_styles.append(styleName)
                except Exception as e:
                    #pass
                    # fix_print_with_import
                    print("\n\nFout!! In laag: %s" % layername)
                    # fix_print_with_import
                    print(e)
                    return
            if not handled:
                # ouch, apparently no styles??? (eg luchtfoto wms's)
                comma = ','
                s = str(
                    '\n%s{"type":"wms","title":"%s","abstract":"%s","url":"%s","layers":"%s","minscale":"%s","maxscale":"%s","servicetitle":"%s","imgformats":"%s", "style":"%s"}' % (
                    comma, title, abstract, url, layername, minscale, maxscale, servicetitle, imgformats, '')).encode('utf8')
                # the comma behind the print makes print NOT add a \n newline behind it
                # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
                # fix_print_with_import
                print(s.decode('utf-8'), end=' ')

wfsversion = "2.0.0"
# services zoals genoemd in https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/
services = [

# alle wmts lagen (behalve luchtfoto) zitten in 1 service
# het heeft dus geen zin om de individuele wmts-url's uit het overzicht te gebruiken omdat die allemaal onderstaande caps teruggeven

# OUD
#('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMTS)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/rgb/wmts?request=GetCapabilities&service=WMTS'),
#('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm Infrarood (WMTS)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/infrarood/wmts?request=GetCapabilities&service=WMTS'),
# per 1 dec 2020
# https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0?&request=GetCapabilities&service=wmts
('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMTS)', 'https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0?&request=GetCapabilities&service=wmts'),
# https://service.pdok.nl/hwh/luchtfotocir/wmts/v1_0?&request=GetCapabilities&service=wmts
('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm Infrarood (WMTS)', 'https://service.pdok.nl/hwh/luchtfotocir/wmts/v1_0?&request=GetCapabilities&service=wmts'),

('wmts', 'PDOK overige services', 'https://geodata.nationaalgeoregister.nl/wmts?VERSION=1.0.0&request=GetCapabilities'),

# LET OP LET OP: de volgende lagen zitten in de wmts capabilities maar moeten eruit:

# kadastralekaart_intern
# en opentopo omhoog geplaatst bij de WMTS'en naast brt (JW) EN de image/jpeg eruit (die heeft PDOK bug!)
# en 2016_ortho25 en 2016_ortho25IR er uit


# 20200618 11494 layers...
# 2019?
# 7570 lagen
# 8645 lagen!!
# WMS en WFS:
# Administratieve Eenheden (INSPIRE geharmoniseerd)
# BAG Terugmeldingen
# CBS Wijken en Buurten 2017
# Geluidskaarten Schiphol
# Geluidskaarten spoorwegen
# Geografische Namen (INSPIRE geharmoniseerd)
# Geomorfologischekaart 1:50.000
# Transport Netwerken - Kabelbanen (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd)

# 20180428
# 9684 lagen (van 8645)
# Nieuwe luchtfotos: 2017
# Beschermde Gebieden INSPIRE (geharmoniseerd)
# BRO Bodemkaart 1:50.000
# BRO Geomorfologischekaart 1:50.000
# BRO Geotechnisch sondeeronderzoek (CPT)
# CBS Postcode4 statistieken
# CBS Postcode4 statistieken
# CBS Postcode6 statistieken
# Hydrografie - Netwerk RWS (INSPIRE geharmoniseerd)
# Hydrografie - Physical Waters (INSPIRE geharmoniseerd)
# Statistical Units Grid
# Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Kabelbanen (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Luchttransport (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Spoorwegen (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd)
# Vervoersnetwerken Waterwegen RWS (INSPIRE geharmoniseerd)
# Vervoersnetwerken - Wegen (INSPIRE geharmoniseerd)
# Vervoersnetwerken Wegen RWS (INSPIRE geharmoniseerd)

# 20181221
#('wms', 'BRO Geotechnisch sondeeronderzoek (WMS)' , 'https://geodata.nationaalgeoregister.nl/brocpt/wms?request=GetCapabilities&service=wms'), #
#('wfs', 'BRO Geotechnisch sondeeronderzoek (WFS)' , 'https://geodata.nationaalgeoregister.nl/brocpt/wfs?request=GetCapabilities&service=wfs'), #
#('wms', 'BRO Bodemkundige boormonsterbeschrijvingen (WMS)' , 'https://geodata.nationaalgeoregister.nl/brobhr/wms?request=GetCapabilities&service=wms'), #
#('wfs', 'BRO Bodemkundige boormonsterbeschrijvingen (WFS)' , 'https://geodata.nationaalgeoregister.nl/brobhr/wfs?request=GetCapabilities&service=wfs'), #


# ALLE URLS NU AFKOMSTIG VAN https://www.pdok.nl/datasets

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/a
('wms', 'AHN1 5, 25 en 100 meter maaiveld raster (WMS)', 'https://geodata.nationaalgeoregister.nl/ahn1/wms?request=GetCapabilities&service=wms'),
#('wfs', 'AHN1 5, 25 en 100 meter maaiveld raster (WFS)', 'https://geodata.nationaalgeoregister.nl/ahn1/wfs?request=GetCapabilities&service=wfs'),
('wcs', 'AHN1 5, 25 en 100 meter maaiveld raster (WCS)', 'https://geodata.nationaalgeoregister.nl/ahn1/wcs?request=GetCapabilities&service=wcs&version=1.1.1'),
('wms', 'AHN2 0,5 en 5 meter maaiveldraster (WMS)', 'https://geodata.nationaalgeoregister.nl/ahn2/wms?request=GetCapabilities&service=wms'),
('wfs', 'AHN2 bladindex ', 'https://geodata.nationaalgeoregister.nl/ahn2/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wcs', 'AHN2 0,5 en 5 meter maaiveldraster (WCS)', 'https://geodata.nationaalgeoregister.nl/ahn2/wcs?request=GetCapabilities&service=wcs&version=1.1.1'),
('wms', 'AHN3 (WMS)', 'https://geodata.nationaalgeoregister.nl/ahn3/wms?request=GetCapabilities&service=wms'),
('wfs', 'AHN3 (WFS)', 'https://geodata.nationaalgeoregister.nl/ahn3/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wcs', 'AHN3 (WCS)', 'https://geodata.nationaalgeoregister.nl/ahn3/wcs?request=GetCapabilities&service=wcs&version=1.1.1'),
('wms', 'Administratieve Eenheden (WMS)','https://geodata.nationaalgeoregister.nl/inspire/au/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Administratieve Eenheden (WFS)','https://geodata.nationaalgeoregister.nl/inspire/au/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Adressen (WMS)', 'https://geodata.nationaalgeoregister.nl/inspireadressen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Adressen (WFS)', 'https://geodata.nationaalgeoregister.nl/inspireadressen/wfs?request=GetCapabilities&version='+wfsversion),
('wms', 'Adressen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/ad/wms?request=GetCapabilities'),
('wfs', 'Adressen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/ad/wfs?request=GetCapabilities&version='+wfsversion),
('wms', 'AAN (WMS)', 'https://geodata.nationaalgeoregister.nl/aan/wms?request=GetCapabilities&service=wms'),
('wfs', 'AAN (WFS)', 'https://geodata.nationaalgeoregister.nl/aan/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Asbest scholenkaart (WMS)', 'https://geodata.nationaalgeoregister.nl/asbestscholenkaart/wms?request=GetCapabilities&service=wms'),
('wfs', 'Asbest scholenkaart (WFS)', 'https://geodata.nationaalgeoregister.nl/asbestscholenkaart/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/b
('wms', 'BAGv1.1 (WMS)', 'https://geodata.nationaalgeoregister.nl/bag/wms/v1_1?request=getCapabilities&service=WMS'),
('wfs', 'BAGv1.1 (WFS)', 'https://geodata.nationaalgeoregister.nl/bag/wfs/v1_1?request=getCapabilities&service=WFS&version='+wfsversion),
('wms', 'BAG Terugmeldingen (WMS)','https://geodata.nationaalgeoregister.nl/terugmeldingen/bag/v2/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'BAG Terugmeldingen (WFS)','https://geodata.nationaalgeoregister.nl/terugmeldingen/bag/v2/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Basisregistratie Gewaspercelen (BRP) (WMS)', 'https://geodata.nationaalgeoregister.nl/brpgewaspercelen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Basisregistratie Gewaspercelen (BRP) (WFS)', 'https://geodata.nationaalgeoregister.nl/brpgewaspercelen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wfs', 'Bekendmakingen (WFS)', 'http://geozet.koop.overheid.nl/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'BGT Terugmeldingen (WMS)', 'https://geodata.nationaalgeoregister.nl/terugmeldingen/bgt/v2/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'BGT Terugmeldingen (WFS)', 'https://geodata.nationaalgeoregister.nl/terugmeldingen/bgt/v2/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'BRK Kadastrale Kaart (WMS)', 'https://geodata.nationaalgeoregister.nl/kadastralekaart/wms/v4_0?service=WMS&version=1.3.0&request=GetCapabilities'),
('wfs', 'BRK Kadastrale Kaart (WFS)', 'https://geodata.nationaalgeoregister.nl/kadastralekaart/wfs/v4_0?service=WFS&version=2.0.0&request=GetCapabilities'), ## NIET NIET &version erbij !!
('wms', 'BRK Kadastrale Percelen (INSPIRE geharmoniseerd) (WMS)', 'https://service.pdok.nl/kadaster/cp/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'BRK Kadastrale Percelen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/cp/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'BRO Geotechnisch sondeeronderzoek (WMS)', 'https://service.pdok.nl/bzk/brocptkenset/wms/v1_0?request=GetCapabilities&service=WMS'),
('wms', 'BRO Bodemkundige boormonsterbeschrijvingen (WMS)', 'https://service.pdok.nl/bzk/brobhrpkenset/wms/v1_0?request=GetCapabilities&service=WMS'),
('wms', 'BRO Grondwatermonitoringput (WMS)', 'https://service.pdok.nl/bzk/brogmwkenset/wms/v2_1?request=getCapabilities'),
('wms', 'BRO Bodemkaart (WMS)', 'https://geodata.nationaalgeoregister.nl/bzk/bro-bodemkaart/wms/v1_0?request=GetCapabilities&service=wms'),
('wms', 'BRO Wandonderzoek v1 (WMS)', 'https://geodata.nationaalgeoregister.nl/bzk/brosfr/wms/v1_0?request=getCapabilities&service=wms'),
('wms', 'BRO Geotechnisch Booronderzoek (WMS)', 'https://geodata.nationaalgeoregister.nl/bzk/brobhrgt/wms/v1_0?request=getCapabilities&service=wms'),
('wms', 'BRO Geomorfologische Kaart (WMS)', 'https://service.pdok.nl/bzk/bro-geomorfologischekaart/wms/v1_0?request=getcapabilities&service=wms'),
('wms', 'BRT TOP10NL (WMS)', 'https://geodata.nationaalgeoregister.nl/top10nlv2/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT Terugmeldingen (WMS)', 'https://geodata.nationaalgeoregister.nl/terugmeldingen/brt/v2/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'BRT Terugmeldingen (WFS)', 'https://geodata.nationaalgeoregister.nl/terugmeldingen/brt/v2/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'BRT TOP25raster (WMS)','https://geodata.nationaalgeoregister.nl/top25raster/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT TOP50raster (WMS)', 'https://geodata.nationaalgeoregister.nl/top50raster/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT TOP100raster (WMS)', 'https://geodata.nationaalgeoregister.nl/top100raster/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT TOP250raster (WMS)', 'https://geodata.nationaalgeoregister.nl/top250raster/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT TOP500raster (WMS)', 'https://geodata.nationaalgeoregister.nl/top500raster/wms?request=GetCapabilities&service=wms'),
('wms', 'BRT TOP1000raster (WMS)', 'https://geodata.nationaalgeoregister.nl/top1000raster/wms?request=GetCapabilities&service=wms'),
('wms', 'CDDA Natura2000 gebieden, de Nationale parken en het Natuur Netwerk Nederlan (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-cdda/wms?request=GetCapabilities&service=WMS'),
('wfs', 'CDDA Natura2000 gebieden, de Nationale parken en het Natuur Netwerk Nederlan (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-cdda/wfs?request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Beschermde Gebieden - Cultuurhistorie (INSPIRE geharmoniseerd) (WMS)', 'https://service.pdok.nl/rce/ps-ch/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'Beschermde Gebieden - Cultuurhistorie (INSPIRE geharmoniseerd) (WFS)', 'https://service.pdok.nl/rce/ps-ch/wfs/v1_0?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Beschermde Gebieden Nationale Parken (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-rvo-np/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Beschermde Gebieden Nationale Parken (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-rvo-np/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Beschermde gebieden Natura2000 (INSPIRE Geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-natura2000/wms?request=getcapabilities'),
('wfs', 'Beschermde gebieden Natura2000 (INSPIRE Geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-natura2000/wfs?request=getcapabilities&version='+wfsversion),
('wms', 'Beschermde Gebieden Provincies (WMS)', 'https://geodata.nationaalgeoregister.nl/provincies/ps/wms/v1?SERVICE=WMS&REQUEST=GetCapabilities'),
('wfs', 'Beschermde Gebieden Provincies (WFS)', 'https://geodata.nationaalgeoregister.nl/provincies/ps/wfs/v1?SERVICE=WFS&REQUEST=GetCapabilities&version='+wfsversion),
('wms', 'Beschermde gebieden Wetlands (INSPIRE Geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-rvo-wl/wms?request=getcapabilities'),
('wfs', 'Beschermde gebieden Wetlands (INSPIRE Geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/ps-rvo-wl/wfs?request=getcapabilities&version='+wfsversion),
('wms', 'Beschermde natuurmonumenten (WMS)', 'https://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/wms?request=GetCapabilities&service=wms'),
('wfs', 'Beschermde natuurmonumenten (WFS)', 'https://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Bestuurlijke grenzen (WMS)', 'https://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Bestuurlijke grenzen (WFS)', 'https://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/c
('wms', 'CBS Aardgas- en elektriciteitslevering 2014 (WMS)', 'https://geodata.nationaalgeoregister.nl/cbsenergieleveringen/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Aardgas- en elektriciteitslevering 2014 (WFS)', 'https://geodata.nationaalgeoregister.nl/cbsenergieleveringen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Bestand Bodemgebruik 2008 (BBG 2008) (WMS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Bestand Bodemgebruik 2008 (BBG 2008) (WFS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Bestand Bodemgebruik 2010 (BBG 2010) (WMS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2010/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Bestand Bodemgebruik 2010 (BBG 2010) (WFS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2010/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Bestand Bodemgebruik 2012 (BBG 2012) (WMS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2012/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Bestand Bodemgebruik 2012 (BBG 2012) (WFS)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2012/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Bevolkingskernen 2008 (WMS) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Bevolkingskernen 2008 (WFS) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Bevolkingskernen 2011 (WMS) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2011/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Bevolkingskernen 2011 (WFS) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2011/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Gebiedsindelingen (WMS)', 'https://geodata.nationaalgeoregister.nl/cbsgebiedsindelingen/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Gebiedsindelingen (WFS)', 'https://geodata.nationaalgeoregister.nl/cbsgebiedsindelingen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Gebiedsindelingen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/su-vector/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Gebiedsindelingen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/su-vector/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Postcode4 statistieken (WMS)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode4/wms?&request=GetCapabilities&service=wms'),
('wfs', 'CBS Postcode4 statistieken (WFS)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode4/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Postcode6 statistieken (WMS)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode6/wms?&request=GetCapabilities&service=wms'),
('wms', 'CBS Provincies (WMS)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Provincies (WFS)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Vierkantstatistieken 100m (WMS) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten100mv2/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Vierkantstatistieken 100m (WFS) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten100mv2/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Vierkantstatistieken 500m (WMS) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten500mv2/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Vierkantstatistieken 500m (WFS) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten500mv2/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2009 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2009 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2010 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2010 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2011 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2011 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2012 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2012 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2013 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2013/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2013 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2013/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2014 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2014/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2014 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2014/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2015 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2015/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2015 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2015/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2016 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2016/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2016 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2016/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2017 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2017/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2017 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2017/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2018 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2018/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2018 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2018/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2019 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2019/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2019 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2019/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Wijken en Buurten 2020 (WMS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2020/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Wijken en Buurten 2020 (WFS) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2020/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'CBS Population Distribution (WMS)', 'https://service.pdok.nl/cbs/pd/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'CBS Population Distribution (WFS)', 'http://service.pdok.nl/cbs/pd/wfs/v1_0?request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'CBS Human Health Statistics Netherlands (WMS)', 'https://service.pdok.nl/cbs/hh/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'CBS Human Health Statistics Netherlands (WFS)', 'https://service.pdok.nl/cbs/hh/wfs/v1_0?request=GetCapabilities&service=WFS&version='+wfsversion),

('wms', 'Cultuurhistorisch GIS (CultGIS) (WMS)', 'https://geodata.nationaalgeoregister.nl/cultgis/wms?request=GetCapabilities&service=wms'),
('wfs', 'Cultuurhistorisch GIS (CultGIS) (WFS)', 'https://geodata.nationaalgeoregister.nl/cultgis/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/d
('wms', 'Digitaal Topografisch Bestand (DTB) (WMS)', 'https://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wms?request=GetCapabilities&service=wms'),
('wfs', 'Digitaal Topografisch Bestand (DTB) (WFS)', 'https://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Drone no-fly zone (WMS)', 'https://geodata.nationaalgeoregister.nl/dronenoflyzones/wms?request=GetCapabilities&service=wms'),
('wfs', 'Drone no-fly zone (WFS)', 'https://geodata.nationaalgeoregister.nl/dronenoflyzones/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/e
('wms', 'Ecotopen (WMS)' , 'https://geodata.nationaalgeoregister.nl/ecotopen/wms?request=GetCapabilities&service=wms') ,
('wfs', 'Ecotopen (WFS)' , 'https://geodata.nationaalgeoregister.nl/ecotopen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion) ,

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/f
('wms', 'Fietsknooppunten (WMS)','https://geodata.nationaalgeoregister.nl/fietsknooppuntennetwerk/wms?request=GetCapabilities&service=wms'),
('wms', 'Fysisch Geografische Regio’s (WMS)','https://geodata.nationaalgeoregister.nl/fysischgeografischeregios/wms?request=GetCapabilities&service=wms'),
('wfs', 'Fysisch Geografische Regio’s (WFS)','https://geodata.nationaalgeoregister.nl/fysischgeografischeregios/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/g
('wms', 'Gebouwen (INSPIRE geharmoniseerd) (WMS)' , 'https://geodata.nationaalgeoregister.nl/inspire/bu/wms?request=GetCapabilities&service=wms') ,
('wfs', 'Gebouwen (INSPIRE geharmoniseerd) (WFS)' , 'https://geodata.nationaalgeoregister.nl/inspire/bu/wfs?request=GetCapabilities&service=wfs&version='+wfsversion) ,
('wms', 'Geluidskaarten Rijkswegen (WMS)' , 'https://geodata.nationaalgeoregister.nl/rwsgeluidskaarten/wms?request=GetCapabilities&service=wms') ,
('wfs', 'Geluidskaarten Rijkswegen (WFS)' , 'https://geodata.nationaalgeoregister.nl/rwsgeluidskaarten/wfs?request=GetCapabilities&service=wfs&version='+wfsversion) ,

('wms', 'Geluidskaarten Schiphol lnight (WMS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartschipholnacht/v2/wms?&request=GetCapabilities&service=WMS') ,
('wfs', 'Geluidskaarten Schiphol lnight (WFS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartschipholnacht/v2/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Geluidskaarten Schiphol lden (WMS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartschipholetmaal/v2/wms?&request=GetCapabilities&service=WMS') ,
('wfs', 'Geluidskaarten Schiphol lden (WFS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartschipholetmaal/v2/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),

('wms', 'Geluidkaart hoofdspoornet 2016 Lden (WMS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartspoorwegenetmaal/v1/wms?&request=GetCapabilities&service=WMS') ,
('wfs', 'Geluidkaart hoofdspoornet 2016 Lden (WFS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartspoorwegenetmaal/v1/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Geluidkaart hoofdspoornet 2016 Lnight (WMS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartspoorwegennacht/v1/wms?&request=GetCapabilities&service=WMS') ,
('wfs', 'Geluidkaart hoofdspoornet 2016 Lnight (WMS)', 'https://geodata.nationaalgeoregister.nl/ienw/geluidskaartspoorwegennacht/v1/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Geografische Namen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/gn/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Geografische Namen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/gn/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
#('wms', 'Geomorfologischekaart 1:50.000 (WMS)', 'https://geodata.nationaalgeoregister.nl/geomorfologischekaart50000/wms?request=GetCapabilities&service=wms'),
#('wfs', 'Geomorfologischekaart 1:50.000 (WFS)', 'https://geodata.nationaalgeoregister.nl/geomorfologischekaart50000/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Gesloten gebieden voor visserij (WMS)', 'https://geodata.nationaalgeoregister.nl/geslotenvisserij/wms?service=WMS&request=GetCapabilities&service=WMS'),
('wfs', 'Gesloten gebieden voor visserij (WFS)', 'https://geodata.nationaalgeoregister.nl/geslotenvisserij/wfs?service=WFS&request=GetCapabilities&service=WFS&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/h
('wms', 'Habitatrichtlijn verspreiding van habitattypen (WMS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Habitatrichtlijn verspreiding van habitattypen (WFS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Habitatrichtlijn verspreiding van soorten (WMS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsoorten/v2/wms?request=GetCapabilities&service=wms'),
('wfs', 'Habitatrichtlijn verspreiding van soorten (WFS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsoorten/v2/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Habitatrichtlijn verspreidingsgebied van habitattypen (WMS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsgebiedtypen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Habitatrichtlijn verspreidingsgebied van habitattypen (WFS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsgebiedtypen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Habitatrichtlijn verspreidingsgebied van soorten (WMS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsgebieden/v2/wms?request=GetCapabilities&service=wms'),
('wfs', 'Habitatrichtlijn verspreidingsgebied van soorten (WFS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsgebieden/v2/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'HHabitatrichtlijn verspreiding van typen (WMS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingtypen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Habitatrichtlijn verspreiding van typen (WFS)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingtypen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Historische Rivierkaarten (WMS)', 'https://geodata.nationaalgeoregister.nl/historischerivierkaarten/wms?request=GetCapabilities&service=wms'),
('wms', 'Hydrografie - Netwerk RWS (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/hy-n/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Hydrografie - Netwerk RWS (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/hy-n/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Hydrografie - Physical Waters (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/hy-p/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Hydrografie - Physical Waters (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/hy-p/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/i
('wms', 'Indicatieve aandachtsgebieden funderingsproblematiek (WMS)', 'https://geodata.nationaalgeoregister.nl/indgebfunderingsproblematiek/wms?request=GetCapabilities&service=wms'),
('wfs', 'Indicatieve aandachtsgebieden funderingsproblematiek (WFS)', 'https://geodata.nationaalgeoregister.nl/indgebfunderingsproblematiek/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Invasieve Exoten (WMS)', 'https://geodata.nationaalgeoregister.nl/rvo/invasieve-exoten/wms/v1_0?request=GetCapabilities&service=wms'),
('wfs', 'Invasieve Exoten (WFS)', 'https://geodata.nationaalgeoregister.nl/indgebfunderingsproblematiek/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/k
('wms' , 'Kaderrichtlijn Mariene Strategie 2018 (WMS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnmarienestrategie2018/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs' , 'Kaderrichtlijn Mariene Strategie 2018 (WFS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnmarienestrategie2018/wfs/v1_0?request=GetCapabilities&service=WFS&version='+wfsversion),
('wms' , 'Kaderrichtlijn Water actueel (WMS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwateractueel/wms/v1_0?service=WMS&request=GetCapabilities'),
('wfs' , 'Kaderrichtlijn Water actueel (WFS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwateractueel/wfs/v1_0?service=WFS&request=GetCapabilities&version='+wfsversion),
('wms' , 'Kaderrichtlijn Water EU2015 (WMS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwater2015/wms/v1_0?service=WMS&request=GetCapabilities'),
('wfs' , 'Kaderrichtlijn Water EU2015 (WFS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwater2015/wfs/v1_0?service=WFS&request=GetCapabilities&version='+wfsversion),
('wms' , 'Kaderrichtlijn Water EU2009 (WMS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwater2009/wms/v1_0?service=WMS&request=GetCapabilities'),
('wfs' , 'Kaderrichtlijn Water EU2009 (WFS)' , 'https://geodata.nationaalgeoregister.nl/rws/kaderrichtlijnwater2009/wfs/v1_0?service=WFS&request=GetCapabilities&version='+wfsversion),

# zit in algememe wmts caps: Kadastrale kaart (WMTS | PDOK Basis) http://geodata.nationaalgeoregister.nl/wmts/kadastralekaart?VERSION=1.0.0&request=GetCapabilities

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/l
('wms', 'Landelijke fietsroutes (WMS)', 'https://geodata.nationaalgeoregister.nl/lfroutes/wms?request=GetCapabilities&service=wms'),
('wms', 'Lange afstandswandelroutes (WMS)', 'https://geodata.nationaalgeoregister.nl/landelijke-wandelroutes/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=Getcapabilities'),
('wms' , 'Liander elektriciteitsnetten (WMS)' , 'https://geodata.nationaalgeoregister.nl/liander/elektriciteitsnetten/v1/wms?service=wms&request=GetCapabilities'),
('wfs' , 'Liander elektriciteitsnetten (WFS)' , 'https://geodata.nationaalgeoregister.nl/liander/elektriciteitsnetten/v1/wfs?&service=wfs&request=GetCapabilities&version='+wfsversion),
# luchtfoto WMTS'en zitten in aparte services !!! niet in de algemene
('wms', 'Luchtfoto Beeldmateriaal / PDOK 25 cm Infrarood (WMS)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/infrarood/wms?&request=GetCapabilities&service=wms'),
('wms', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMS)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/rgb/wms?&request=GetCapabilities&service=wms'),

# overige luchtfoto's ("Gesloten" maar niet toegevoegd...)

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/m
('wms', 'Mossel- en oesterhabitats (WMS)' , 'https://geodata.nationaalgeoregister.nl/mosselenoesterhabitats/wms?request=GetCapabilities&service=wms'),
('wfs', 'Mossel- en oesterhabitats (WFS)' , 'https://geodata.nationaalgeoregister.nl/mosselenoesterhabitats/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Mosselzaad invanginstallaties (WMS)' , 'https://geodata.nationaalgeoregister.nl/mosselzaadinvanginstallaties/wms?request=GetCapabilities&service=wms'),
('wfs', 'Mosselzaad invanginstallaties (WFS)' , 'https://geodata.nationaalgeoregister.nl/mosselzaadinvanginstallaties/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/n
('wms', 'NAPinfo (WMS)' , 'https://geodata.nationaalgeoregister.nl/napinfo/wms?request=GetCapabilities&service=wms'),
('wfs', 'NAPinfo (WFS)' , 'https://geodata.nationaalgeoregister.nl/napinfo/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Nationaal Hydrologisch Instrumentarium (NHI) (WMS)' , 'https://geodata.nationaalgeoregister.nl/nhi/ows?service=wms&request=GetCapabilities&service=wms'),
('wfs', 'Nationaal Hydrologisch Instrumentarium (NHI) (WFS)' , 'https://geodata.nationaalgeoregister.nl/nhi/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wfs','NWB-Vaarwegen (WFS)', 'https://geodata.nationaalgeoregister.nl/nwbvaarwegen/wms?request=GetCapabilities'),
('wms','NWB-Vaarwegen (WMS)', 'https://geodata.nationaalgeoregister.nl/nwbvaarwegen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs','NWB-Wegen (WFS)', 'https://geodata.nationaalgeoregister.nl/nwbwegen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms','NWB-Wegen (WMS)', 'https://geodata.nationaalgeoregister.nl/nwbwegen/wms?SERVICE=WMS&request=GetCapabilities'),
('wms', 'Nationale EnergieAtlas informatielagen Kadaster (WMS)', 'https://geodata.nationaalgeoregister.nl/neainfolagenkadaster/wms?request=GetCapabilities&service=wms'),
('wfs', 'Nationale EnergieAtlas informatielagen Kadaster (WFS)', 'https://geodata.nationaalgeoregister.nl/neainfolagenkadaster/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Nationale Parken (WMS)', 'https://geodata.nationaalgeoregister.nl/nationaleparken/wms?request=GetCapabilities&service=wms'),
('wfs', 'Nationale Parken (WFS)', 'https://geodata.nationaalgeoregister.nl/nationaleparken/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
#('wms', 'Nationale Streekpaden (WMS) ','https://geodata.nationaalgeoregister.nl/streekpaden/wms?request=GetCapabilities'), # OUD ?
('wms', 'Natura 2000 (WMS)', 'https://geodata.nationaalgeoregister.nl/natura2000/wms?request=GetCapabilities&service=wms'),
('wfs', 'Natura 2000 (WFS)', 'https://geodata.nationaalgeoregister.nl/natura2000/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
# zit in algememe wmts caps: Natura 2000 (WMTS) http://geodata.nationaalgeoregister.nl/tiles/service/wmts/natura2000?VERSION=1.0.0&request=GetCapabilities
# geen TMS: Natura 2000 (TMS) http://geodata.nationaalgeoregister.nl/tms/1.0.0/natura2000@EPSG:28992@png8
('wms','Natuurmeting Op Kaart 2014 (WMS)','https://geodata.nationaalgeoregister.nl/nok2014/wms?request=GetCapabilities&service=wms'),
('wfs','Natuurmeting Op Kaart 2014 (WFS)','https://geodata.nationaalgeoregister.nl/nok2014/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
# TIJDELIJK UIT: ('wms','Noordzee Vaarwegmarkeringen (WMS)','https://geodata.nationaalgeoregister.nl/noordzeevaarwegmarkeringenrd/wms?request=GetCapabilities&service=wms'),
('wfs','Noordzee Vaarwegmarkeringen (WFS) ','https://geodata.nationaalgeoregister.nl/noordzeevaarwegmarkeringenrd/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/o
('wms','Overheidsdiensten (WMS)', 'https://geodata.nationaalgeoregister.nl/overheidsdiensten/wms?request=GetCapabilities&service=wms'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/p
('wms', 'Potentieel koude en warmte uit open en gesloten WKO systemen (GJ/ha.jaar) (WMS)', 'https://geodata.nationaalgeoregister.nl/wko/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Potentieel koude en warmte uit open en gesloten WKO systemen (GJ/ha.jaar) (WFS)', 'https://geodata.nationaalgeoregister.nl/wko/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Potentiekaart omgevingswarmte (WMS)', 'https://geodata.nationaalgeoregister.nl/omgevingswarmte/wms?request=GetCapabilities&service=wms'),
('wfs', 'Potentiekaart omgevingswarmte (WFS)', 'https://geodata.nationaalgeoregister.nl/omgevingswarmte/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Potentiekaart reststromen (WMS)', 'https://geodata.nationaalgeoregister.nl/reststromen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Potentiekaart reststromen (WFS)', 'https://geodata.nationaalgeoregister.nl/reststromen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Potentiekaart restwarmte (WMS)', 'https://geodata.nationaalgeoregister.nl/restwarmte/wms?request=GetCapabilities'),
('wfs', 'Potentiekaart restwarmte (WFS)', 'https://geodata.nationaalgeoregister.nl/restwarmte/wfs?request=GetCapabilities&version='+wfsversion),
('wms', 'Projecten Deltaplan Agrarisch Waterbeheer (WMS)', 'https://geodata.nationaalgeoregister.nl/deltaplanagrarischwaterbeheer/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Projecten Deltaplan Agrarisch Waterbeheer (WFS)', 'https://geodata.nationaalgeoregister.nl/deltaplanagrarischwaterbeheer/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Publiekrechtelijke Beperking WKPB (WMS)', 'https://geodata.nationaalgeoregister.nl/publiekrechtelijkebeperking/wms?request=GetCapabilities&service=wms'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/r
('wms', 'RDinfo (WMS)', 'https://geodata.nationaalgeoregister.nl/rdinfo/wms?request=GetCapabilities&service=wms'),
('wfs', 'RDinfo (WFS)', 'https://geodata.nationaalgeoregister.nl/rdinfo/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Richtlijn Overstromingsrisico EU2018 (WMS)', 'https://geodata.nationaalgeoregister.nl/rws/richtlijnoverstromingsrisico2018/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'Richtlijn Overstromingsrisico EU2018 (WFS)', 'https://geodata.nationaalgeoregister.nl/rws/richtlijnoverstromingsrisico2018/wfs/v1_0?request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Richtlijn Stedelijk Afvalwater (WMS)', 'https://geodata.nationaalgeoregister.nl/rws/richtlijnstedelijkafvalwater2015/wms/v1_0?request=GetCapabilities&service=WMS'),
('wfs', 'Richtlijn Stedelijk Afvalwater (WFS)', 'https://geodata.nationaalgeoregister.nl/rws/richtlijnstedelijkafvalwater2015/wfs/v1_0?request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Ruimtelijke plannen (WMS)', 'https://geodata.nationaalgeoregister.nl/plu/wms?request=GetCapabilities&service=wms'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/s
('wms', 'Scheepvaart Verkeersscheidingsstelsel Noordzee (WMS)', 'https://geodata.nationaalgeoregister.nl/rws/verkeersscheidingsstelsel/wms/v2_0?service=WMS&request=getcapabilities'),
('wfs', 'Scheepvaart Verkeersscheidingsstelsel Noordzee (WFS)','https://geodata.nationaalgeoregister.nl/rws/verkeersscheidingsstelsel/wfs/v2_0?service=WFS&request=getcapabilities&version='+wfsversion),
('wms', 'Schelpdierenpercelen (WMS)', 'https://geodata.nationaalgeoregister.nl/schelpdierenpercelen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Schelpdierenpercelen (WFS)','https://geodata.nationaalgeoregister.nl/schelpdierenpercelen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Schelpdierwater (WMS)', 'https://geodata.nationaalgeoregister.nl/schelpdierwater/wms?request=GetCapabilities&service=wms'),
('wfs', 'Schelpdierwater (WFS)', 'https://geodata.nationaalgeoregister.nl/schelpdierwater/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Spoorwegen Prorail (WMS)', 'https://geodata.nationaalgeoregister.nl/spoorwegen/wms?request=GetCapabilities&service=wms'),
('wfs', 'Spoorwegen Prorail (WFS)', 'https://geodata.nationaalgeoregister.nl/spoorwegen/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Statistical Units Grid (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/su-grid/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Statistical Units Grid (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/su-grid/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Statistics Netherlands Land Use 2015 (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/elu/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Statistics Netherlands Land Use 2015 (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/elu/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Stedelijk Water (Riolering) (WMS)','https://geodata.nationaalgeoregister.nl/rioned/gwsw/wms/v1_0?&request=GetCapabilities&service=WMS'),
('wfs', 'Stedelijk Water (Riolering) (WFS)','https://geodata.nationaalgeoregister.nl/rioned/gwsw/wfs/v1_0?&request=GetCapabilities&service=WFS&version='+wfsversion),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/t

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/v
('wms', 'Vaarweg Informatie Nederland (VIN) (WMS) ','https://geodata.nationaalgeoregister.nl/vin/wms?request=GetCapabilities&service=wms'),
('wfs', 'Vaarweg Informatie Nederland (VIN) (WFS) ','https://geodata.nationaalgeoregister.nl/vin/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

('wms', 'Verkeersongevallen - Nederland 2008 - 2017 (WMS)', 'https://geodata.nationaalgeoregister.nl/rws/verkeersongevallen_nld_2017/wms/v1?SERVICE=WMS&request=getcapabilities'),
('wfs', 'Verkeersongevallen - Nederland 2008 - 2017 (WFS)', 'https://geodata.nationaalgeoregister.nl/rws/verkeersongevallen_nld_2017/wfs/v1?SERVICE=WFS&request=getcapabilities&version='+wfsversion),

# ('wms', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/tn/wms?request=GetCapabilities'),
# ('wfs', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-cte/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/tn/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/tn/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Kabelbanen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-c/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Kabelbanen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-c/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Luchttransport (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/tn-a/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Luchttransport (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/tn-a/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Spoorwegen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-ra/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Spoorwegen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-ra/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd) (WMS)', 'http://geodata.nationaalgeoregister.nl/inspire/tn-w/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd) (WFS)', 'http://geodata.nationaalgeoregister.nl/inspire/tn-w/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
# ('wms', 'Vervoersnetwerken - Wegen (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/tn-ro/wms?&request=GetCapabilities&service=wms'),
# ('wfs', 'Vervoersnetwerken - Wegen (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/tn-ro/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Vervoersnetwerken Waterwegen RWS (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-w/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Vervoersnetwerken Waterwegen RWS (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-w/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Vervoersnetwerken Wegen RWS (INSPIRE geharmoniseerd) (WMS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-ro/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Vervoersnetwerken Wegen RWS (INSPIRE geharmoniseerd) (WFS)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-ro/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),

('wms', 'Vogelrichtlijn verspreiding van soorten (WMS)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsoorten/wms?request=GetCapabilities&service=wms'),
('wfs', 'Vogelrichtlijn verspreiding van soorten (WFS)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsoorten/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Vogelrichtlijn verspreidingsgebied soorten (WMS)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsgebiedsoorten/wms?&request=GetCapabilities&service=wms'),
('wfs', 'Vogelrichtlijn verspreidingsgebied soorten (WFS)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsgebiedsoorten/wfs?&request=GetCapabilities&service=wfs&version='+wfsversion),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/w
('wms', 'Waterschappen Administratieve eenheden INSPIRE (WMS)', 'https://geodata.nationaalgeoregister.nl/hwh/eenheden/wms/v1_0?request=getcapabilities&service=wms'),
('wms', 'Waterschappen Hydrografie INSPIRE (WMS)', 'https://service.pdok.nl/hwh/hydrografie/wms/v1_0?request=getcapabilities&service=wms'),
('wms', 'Waterschappen Kunstwerken IMWA (WMS)', 'https://service.pdok.nl/hwh/kunstwrkimwa/wms/v1_0?request=getCapabilities&service=wms'),
('wms', 'Waterschappen Nuts-Overheidsdiensten INSPIRE (WMS)', 'https://geodata.nationaalgeoregister.nl/wsdiensteninspire/wms?request=GetCapabilities&service=wms'),
('wms', 'Waterschappen Oppervlaktewateren IMWA (WMS)', 'https://service.pdok.nl/hwh/oppwaterimwa/wms/v1_0?request=getCapabilities&service=wms'),
('wms', 'Waterschappen Waterbeheergebieden IMWA (WMS)', 'https://service.pdok.nl/hwh/wbehgebimwa/wms/v1_0?request=GetCapabilities&service=WMS'),
('wms', 'Keringen waterschappen IMWA (WMS)', 'https://service.pdok.nl/hwh/keringenimwa/wms/v1_0?request=getCapabilities&service=wms'),
('wms', 'Weggegevens (Weggeg) (WMS)', 'https://geodata.nationaalgeoregister.nl/weggeg/wms?request=GetCapabilities&service=wms'),
('wfs', 'Weggegevens (Weggeg) (WFS)', 'https://geodata.nationaalgeoregister.nl/weggeg/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Wetlands (WMS)', 'https://geodata.nationaalgeoregister.nl/wetlands/wms?request=GetCapabilities&service=wms'),
('wfs', 'Wetlands (WFS)', 'https://geodata.nationaalgeoregister.nl/wetlands/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),
('wms', 'Windsnelheden 100m hoogte (WMS)','https://geodata.nationaalgeoregister.nl/windkaart/wms?request=GetCapabilities&service=wms'),
('wfs', 'Windsnelheden 100m hoogte (WFS)','https://geodata.nationaalgeoregister.nl/windkaart/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/z
('wms', 'Zeegebieden (WMS)', 'https://geodata.nationaalgeoregister.nl/sr/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Zeegebieden (WFS)', 'https://geodata.nationaalgeoregister.nl/inspire/sr/wfs?&request=GetCapabilities&service=WFS&version='+wfsversion),
('wms', 'Zeegraskartering (WMS)', 'https://geodata.nationaalgeoregister.nl/zeegraskartering/wms?request=GetCapabilities&service=wms'),
('wfs', 'Zeegraskartering (WFS)', 'https://geodata.nationaalgeoregister.nl/zeegraskartering/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

]

# testing NOTE: ik heb rare problemen met freedom.nl... NIET via tmobile connectie
NO_services = [

('wms', 'CBS Provincies (WMS)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wms?request=GetCapabilities&service=wms'),
('wfs', 'CBS Provincies (WFS)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wfs?request=GetCapabilities&service=wfs&version='+wfsversion),

#('wms', 'xxxx', 'https'),
#('wfs', 'xxxx', 'https'),
#('wcs', 'xxxx', 'https'),

]


firstOne = True
print('{"services":[', end=' ')

for (stype, title, url) in services:
    #print(f'\n --> {url}')
    if stype == 'wms':
        handleWMS(url)
    elif stype == 'wmts':
        handleWMTS(url)
    elif stype == 'wfs':
        handleWFS(url)
    elif stype == 'wcs':
        handleWCS(url)
    import time
    #time.sleep(4)

print(']}')
