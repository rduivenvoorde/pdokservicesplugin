# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin pdok2json.py

 Dit is een ruw python script om op basis van een rij service-url's
 (wms, wfs, wcs en wmts) de capabilities van elke service op te halen, en 
 van elke 'laag' in die service een json object aan te maken me wat gegevens
 van die laag.

 Deze json wordt gebruikt om het bestandje pdok.json aan te maken
 met python3 (LET OP alleen python3 werkt nu ivm encoding probleempjes)
    python3 pdok2json.py > pdok.json
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
from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str

from xml.dom.minidom import parse, parseString
import urllib.request, urllib.parse, urllib.error
import re

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
    dom = parse(urllib.request.urlopen(wcscapsurl))
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
    #dom = parse(urllib.urlopen(wmscapsurl))
    #  ^^ that is not working for some wicked cbs caps with coördinaat in it...
    # hack: read string and find replace coördinaat with coordinaat
    response = urllib.request.urlopen(wfscapsurl)
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
    featuretypes = dom.getElementsByTagName('FeatureType')
    for featuretype in featuretypes:
        layername = childNodeValue(featuretype, 'Name')
        title = childNodeValue(featuretype, 'Title')
        # title can have newlines in it sometimes, which create havoc in json
        title = title.replace('\r', '')
        title = title.replace('\t', ' ')
        title = title.replace('\n', ' ')
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
            s = str('\n%s{"type":"wfs","title":"%s","abstract":"%s","url":"%s","layers":"%s","servicetitle":"%s"}' % (comma, title, abstract, url, layername, servicetitle)).encode('utf8')
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


def handleWMTS(wmtscapsurl):
    #dom = parse("wmts-getcapabilities_1.0.0.xml")
    dom = parse(urllib.request.urlopen(wmtscapsurl))
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
    response = urllib.request.urlopen(wmscapsurl)
    string = response.read()
    #string = re.sub(r"co.+rdin","coordin", str(string))
    #print(string)

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
            comma = ''
            handled = False
            for style in layer.getElementsByTagName('Style'):
                styleName = childNodeValue(style, 'Name')
                try:
                    if not firstOne:
                        comma = ','
                    # some extract have strange chars, we decode to utf8
                    s = str('\n%s{"type":"wms","title":"%s","abstract":"%s","url":"%s","layers":"%s","minscale":"%s","maxscale":"%s","servicetitle":"%s","imgformats":"%s", "style":"%s"}' % (comma, title, abstract, url, layername, minscale, maxscale, servicetitle, imgformats, styleName)).encode('utf8')
                    # the comma behind the print makes print NOT add a \n newline behind it
                    # from: http://stackoverflow.com/questions/3249524/print-in-one-line-dynamically-python
                    # fix_print_with_import
                    print(s.decode('utf-8'), end=' ')
                    firstOne = False
                    handled = True
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

# services zoals genoemd in https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/
services = [

# alle wmts lagen (behalve luchtfoto) zitten in 1 service
# het heeft dus geen zin om de individuele wmts-url's uit het overzicht te gebruiken omdat die allemaal onderstaande caps teruggeven

('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMTS | Open)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/rgb/wmts?request=GetCapabilities&service=WMTS'),
('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm Infrarood (WMTS | Open)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/infrarood/wmts?request=GetCapabilities&service=WMTS'),

('wmts', 'PDOK overige services', 'https://geodata.nationaalgeoregister.nl/wmts?VERSION=1.0.0&request=GetCapabilities'),

# LET OP LET OP: de volgende lagen zitten in de wmts capabilities maar moeten eruit:

# brkpilot
# brkgeo
# gbkn
# kadastralekaart_intern

# en eruit vanwege niet meer geldig
# kadastralekaartv2
# luchtfoto

# en opentopo omhoog geplaatst bij de WMTS'en naast brt (JW) EN de image/jpeg eruit (die heeft PDOK bug!)
# en 2016_ortho25 en 2016_ortho25IR er uit


# 7570 lagen
# 8645 lagen!!
#
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

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/a
('wms', 'AHN1 (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn1/wms?service=wms&request=getcapabilities'),
('wfs', 'AHN1 (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn1/wfs?version=1.0.0&request=GetCapabilities'),
('wcs', 'AHN1 (WCS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn1/wcs?request=getcapabilities&SERVICE=WCS&VERSION=1.1.1'),
('wms', 'AHN2 (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn2/wms?service=wms&request=getcapabilities'),
('wfs', 'AHN2 (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn2/wfs?version=1.0.0&request=GetCapabilities'),
('wcs', 'AHN2 (WCS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn2/wcs?request=getcapabilities&SERVICE=WCS&VERSION=1.1.1'),
('wms', 'AHN3 (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn3/wms?request=GetCapabilities'),
('wfs', 'AHN3 (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn3/wfs?request=GetCapabilities'),
('wcs', 'AHN3 (WCS | Open)', 'https://geodata.nationaalgeoregister.nl/ahn3/wcs?request=GetCapabilities&SERVICE=WCS&VERSION=1.1.1'),
('wms', 'Administratieve Eenheden (INSPIRE geharmoniseerd) (WMS | Open)','https://geodata.nationaalgeoregister.nl/inspire/au/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Administratieve Eenheden (INSPIRE geharmoniseerd) (WFS | Open)','https://geodata.nationaalgeoregister.nl/inspire/au/wfs?&request=GetCapabilities&service=WFS'),
('wms', 'Adressen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspireadressen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Adressen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspireadressen/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Adressen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/ad/wms?request=GetCapabilities'),
('wfs', 'Adressen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/ad/wfs?request=GetCapabilities'),
('wms', 'AAN (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/aan/wms?request=GetCapabilities'),
('wfs', 'AAN (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/aan/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Asbest scholenkaart (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/asbestscholenkaart/wms?request=GetCapabilities '),
('wfs', 'Asbest scholenkaart (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/asbestscholenkaart/wfs?request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/b
('wfs', 'BAG (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bag/wfs?request=GetCapabilities'),
('wms', 'BAG (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bag/wms?request=GetCapabilities'),
('wms', 'BAG Terugmeldingen (WMS | Open)','https://geodata.nationaalgeoregister.nl/bagterugmeldingen/wms?request=GetCapabilities'),
('wfs', 'BAG Terugmeldingen (WFS | Open)','https://geodata.nationaalgeoregister.nl/bagterugmeldingen/wfs?request=GetCapabilities'),
('wms', 'Basisregistratie Gewaspercelen (BRP) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/brpgewaspercelen/wms?request=GetCapabilities'),
('wfs', 'Basisregistratie Gewaspercelen (BRP) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/brpgewaspercelen/wfs?version=1.0.0&request=GetCapabilities'),
('wfs', 'Bekendmakingen (WFS | Open)', 'http://geozet.koop.overheid.nl/wfs?version=1.0.0&request=GetCapabilities'),
# BGT zijn bijna allemaal WMTS'en...
# web beta, maar beide zijn op dit moment stuk
#('wms', 'Basisregistratie Grootschalige Topografie (BGT) - Beta (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/beta/bgt/wms?request=getcapabilities'),
#('wfs', 'Basisregistratie Grootschalige Topografie (BGT) - Beta (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/beta/bgt/wfs?request=getcapabilities'),
('wms', 'Beschermde Gebieden INSPIRE (geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/ps/wms?&request=GetCapabilities'),
('wfs', 'Beschermde Gebieden INSPIRE (geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/ps/wfs?&request=GetCapabilities'),
('wms', 'Beschermde natuurmonumenten (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/ows?service=wms&request=getcapabilities'),
('wfs', 'Beschermde natuurmonumenten (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/beschermdenatuurmonumenten/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Bestuurlijke grenzen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wms?&Request=getcapabilities'),
('wfs', 'Bestuurlijke grenzen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bestuurlijkegrenzen/wfs?version=1.0.0&request=GetCapabilities'),
#zit in algemene WMTS Caps ('wmts', 'BRP Gewaspercelen (WMTS | Open) ', 'http://geodata.nationaalgeoregister.nl/wmts/brtachtergrondkaart?VERSION=1.0.0&request=GetCapabilities') ,
#zit in algemene WMTS Caps ('wmts', 'BRT achtergrondkaart (WMTS | Open) ', 'http://geodata.nationaalgeoregister.nl/wmts/brtachtergrondkaart?VERSION=1.0.0&request=GetCapabilities') ,
('wms', 'BGT Terugmeldingen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bgtterugmeldingen/wms?request=GetCapabilities'),
('wfs', 'BGT Terugmeldingen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bgtterugmeldingen/wfs?request=GetCapabilities'),
('wms', 'BRO Bodemkaart 1:50.000 (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bodemkaart50000/wms?request=getCapabilities'),
('wfs', 'BRO Bodemkaart 1:50.000 (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bodemkaart50000/wfs?request=getCapabilities'),
('wms', 'BRO Geomorfologischekaart 1:50.000 (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/geomorfologischekaart50000/wms?request=GetCapabilities'),
('wfs', 'BRO Geomorfologischekaart 1:50.000 (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/geomorfologischekaart50000/wfs?request=GetCapabilities'),
('wms', 'BRO Geotechnisch sondeeronderzoek (CPT) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/brogeotechnischsondeeronderzoek/wms?request=GetCapabilities'),
('wfs', 'BRO Geotechnisch sondeeronderzoek (CPT) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/brogeotechnischsondeeronderzoek/wfs?request=GetCapabilities'),
('wms', 'BRT Terugmeldingen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/brtterugmeldingen/wms?request=GetCapabilities'),
('wfs', 'BRT Terugmeldingen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/brtterugmeldingen/wms?request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/c
('wms', 'CBS Aardgas- en elektriciteitslevering (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/cbsenergieleveringen/wms?request=GetCapabilities'),
('wfs', 'CBS Aardgas- en elektriciteitslevering (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/cbsenergieleveringen/wfs?request=GetCapabilities'),
('wms', 'CBS Bestand Bodemgebruik 2008 (BBG 2008) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wms?request=getcapabilities') ,
('wfs', 'CBS Bestand Bodemgebruik 2008 (BBG 2008) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2008/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Bestand Bodemgebruik 2010 (BBG 2010) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2010/wms?service=wms&request=getcapabilities') ,
('wfs', 'CBS Bestand Bodemgebruik 2010 (BBG 2010) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2010/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Bestand Bodemgebruik 2012 (BBG 2012) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2012/wms?service=wms&request=getcapabilities') ,
('wfs', 'CBS Bestand Bodemgebruik 2012 (BBG 2012) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/bestandbodemgebruik2012/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Bevolkingskernen 2008 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wms?request=getcapabilities') ,
('wfs', 'CBS Bevolkingskernen 2008 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2008/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Bevolkingskernen 2011 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2011/wms?request=getcapabilities') ,
('wfs', 'CBS Bevolkingskernen 2011 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/bevolkingskernen2011/wfs?version=1.0.0&request=GetCapabilities') ,
('wms', 'CBS Gebiedsindelingen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/cbsgebiedsindelingen/wms?request=GetCapabilities'),
('wfs', 'CBS Gebiedsindelingen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/cbsgebiedsindelingen/wfs?request=GetCapabilities'),
('wms', 'CBS Gebiedsindelingen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/su-vector/wms?&request=GetCapabilities'),
('wfs', 'CBS Gebiedsindelingen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/su-vector/wfs?&request=GetCapabilities'),
('wms', 'CBS Postcode4 statistieken (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode4/wms?&request=GetCapabilities'),
('wfs', 'CBS Postcode4 statistieken (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode4/wfs?&request=GetCapabilities'),
('wms', 'CBS Postcode6 statistieken (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/cbspostcode6/wms?&request=GetCapabilities'),
# geen pc6 WFS ?
('wms', 'CBS Provincies (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wms?request=GetCapabilities'),
('wfs', 'CBS Provincies (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/cbsprovincies/wfs?request=GetCapabilities'),
('wms', 'CBS Vierkantstatistieken 100m (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten100mv2/wms?request=GetCapabilities'),
('wfs', 'CBS Vierkantstatistieken 100m (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten100mv2/wfs?request=GetCapabilities'),
('wms', 'CBS Vierkantstatistieken 500m (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten500mv2/wms?request=GetCapabilities'),
('wfs', 'CBS Vierkantstatistieken 500m (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/cbsvierkanten500mv2/wfs?request=GetCapabilities'),
('wms', 'CBS Wijken en Buurten 2009 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2009 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2009/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2010 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2010 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2010/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2011 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2011 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2011/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2012 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2012 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2012/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2013 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2013/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2013 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2013/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2014 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2014/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2014 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2014/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2015 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2015/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2015 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2015/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2016 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2016/wms?request=getcapabilities'),
('wfs', 'CBS Wijken en Buurten 2016 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2016/wfs?version=1.0.0&request=getcapabilities'),
('wms', 'CBS Wijken en Buurten 2017 (WMS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2017/wms?request=GetCapabilities'),
('wfs', 'CBS Wijken en Buurten 2017 (WFS | Open) ', 'https://geodata.nationaalgeoregister.nl/wijkenbuurten2017/wfs?request=GetCapabilities'),
('wms', 'Cultuurhistorisch GIS (CultGIS) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/cultgis/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Cultuurhistorisch GIS (CultGIS) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/cultgis/wfs?version=1.0.0&request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/d
('wms', 'Digitaal Topografisch Bestand (DTB) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Digitaal Topografisch Bestand (DTB) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/digitaaltopografischbestand/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Drone no-fly zone (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/dronenoflyzones/wms?request=GetCapabilities'),
('wfs', 'Drone no-fly zone (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/dronenoflyzones/wfs?request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/e
('wms', 'Ecotopen (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/ecotopen/wms?request=GetCapabilities') ,
('wfs', 'Ecotopen (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/ecotopen/wfs?request=GetCapabilities') ,

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/f
('wms', 'Fietsknooppunten (WMS | Open)','https://geodata.nationaalgeoregister.nl/fietsknooppuntennetwerk/wms?request=GetCapabilities'),
('wms', 'Fysisch Geografische Regio’s (WMS | Open)','https://geodata.nationaalgeoregister.nl/fysischgeografischeregios/wms?request=GetCapabilities'),
('wfs', 'Fysisch Geografische Regio’s (WFS | Open)','https://geodata.nationaalgeoregister.nl/fysischgeografischeregios/wfs?request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/g
('wms', 'Gebouwen (INSPIRE geharmoniseerd) (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/inspire/bu/wms?request=GetCapabilities') ,
('wfs', 'Gebouwen (INSPIRE geharmoniseerd) (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/inspire/bu/wfs?request=GetCapabilities') ,
('wms', 'Geluidskaarten Rijkswegen (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/rwsgeluidskaarten/wms?request=GetCapabilities') ,
('wfs', 'Geluidskaarten Rijkswegen (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/rwsgeluidskaarten/wfs?request=GetCapabilities') ,
('wms', 'Geluidskaarten Schiphol WMS (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/geluidskaartenschiphol/wms?request=GetCapabilities') ,
('wfs', 'Geluidskaarten Schiphol WFS (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/geluidskaartenschiphol/wfs?request=GetCapabilities'),
('wms', 'Geluidskaarten spoorwegen WMS (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/geluidskaartenspoorwegen/wms?request=GetCapabilities') ,
('wfs', 'Geluidskaarten spoorwegen WFS (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/geluidskaartenspoorwegen/wfs?request=GetCapabilities'),
('wms', 'Geografische Namen (INSPIRE geharmoniseerd) (WMS | Open)', 'http://geodata.nationaalgeoregister.nl/inspire/gn/wms?&request=GetCapabilities'),
('wfs', 'Geografische Namen (INSPIRE geharmoniseerd) (WFS | Open)', 'http://geodata.nationaalgeoregister.nl/inspire/gn/wfs?&request=GetCapabilities'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/h
('wms', 'Habitatrichtlijn verspreiding van habitattypen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wms?request=getcapabilities'),
('wfs', 'Habitatrichtlijn verspreiding van habitattypen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wfs?request=getcapabilities'),
('wms', 'Habitatrichtlijn verspreiding van soorten (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsoorten/wms?request=GetCapabilities'),
('wfs', 'Habitatrichtlijn verspreiding van soorten (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidingsoorten/wfs?request=GetCapabilities'),
('wms', 'Historische Rivierkaarten (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/historischerivierkaarten/wms?request=GetCapabilities'),
('wms', 'Hydrografie - Netwerk RWS (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/hy-n/wms?&request=GetCapabilities'),
('wfs', 'Hydrografie - Netwerk RWS (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/hy-n/wfs?&request=GetCapabilities'),
('wms', 'Hydrografie - Physical Waters (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/hy-p/wms?&request=GetCapabilities&service=WMS'),
('wfs', 'Hydrografie - Physical Waters (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/hy-p/wfs?&request=GetCapabilities&service=WFS'),

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/i
('wms', 'Indicatieve aandachtsgebieden funderingsproblematiek (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/indgebfunderingsproblematiek/wms?&request=GetCapabilities') ,
('wfs', 'Indicatieve aandachtsgebieden funderingsproblematiek (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/indgebfunderingsproblematiek/wfs?&request=GetCapabilities') ,

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/k
('wms' , 'Kadastrale Kaart v3 (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/kadastralekaartv3/wms?request=GetCapabilities') ,
('wfs' , 'Kadastrale Kaart v3 (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/kadastralekaartv3/wfs?request=GetCapabilities'),
('wms' , 'Kadastrale Percelen (INSPIRE geharmoniseerd) (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/inspire/cp/wms?request=GetCapabilities') ,
('wfs' , 'Kadastrale Percelen (INSPIRE geharmoniseerd) (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/inspire/cp/wfs?request=GetCapabilities'),
('wms' , 'Kweldervegetatie (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/kweldervegetatie/wms?request=GetCapabilities') ,
('wfs' , 'Kweldervegetatie (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/kweldervegetatie/wfs?request=GetCapabilities') ,

# zit in algememe wmts caps: Kadastrale kaart (WMTS | PDOK Basis) http://geodata.nationaalgeoregister.nl/wmts/kadastralekaart?VERSION=1.0.0&request=GetCapabilities

# https//www.pdok.nl/nl/producten/pdok-services/overzicht-urls/l
('wms', 'Landelijke fietsroutes (WMS | Open) ','https://geodata.nationaalgeoregister.nl/lfroutes/wms?request=GetCapabilities'),
('wms', 'Lange afstandswandelroutes (WMS | Open) ','https://geodata.nationaalgeoregister.nl/lawroutes/wms?request=GetCapabilities'),
# luchtfoto WMTS'en zitten in aparte services !!! niet in de algemene
('wms', 'Luchtfoto Beeldmateriaal / PDOK 25 cm Infrarood (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/infrarood/wms?&request=GetCapabilities'),
('wms', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/rgb/wms?&request=GetCapabilities'),

# overige luchtfoto's ("Gesloten" maar niet toegevoegd...)

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/m
('wms', 'Mossel- en oesterhabitats (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/mosselenoesterhabitats/wms?request=GetCapabilities') ,
('wfs', 'Mossel- en oesterhabitats (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/mosselenoesterhabitats/wfs?request=GetCapabilities') ,
('wms', 'Mosselzaad invanginstallaties (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/mosselzaadinvanginstallaties/wms?request=GetCapabilities') ,
('wfs', 'Mosselzaad invanginstallaties (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/mosselzaadinvanginstallaties/wfs?request=GetCapabilities') ,

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/n
('wms', 'NAPinfo (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/napinfo/wms?request=GetCapabilities'),
('wfs', 'Napinfo (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/napinfo/wfs?request=GetCapabilities'),
('wms', 'Nationaal Hydrologisch Instrumentarium (NHI) (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/nhi/ows?service=wms&request=GetCapabilities'),
('wfs', 'Nationaal Hydrologisch Instrumentarium (NHI) (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/nhi/wfs?request=GetCapabilities'),
('wms', 'Nationale EnergieAtlas informatielagen Kadaster (WMS | Open)' , 'https://geodata.nationaalgeoregister.nl/neainfolagenkadaster/wms?request=GetCapabilities'),
('wfs', 'Nationale EnergieAtlas informatielagen Kadaster (WFS | Open)' , 'https://geodata.nationaalgeoregister.nl/neainfolagenkadaster/wfs?request=GetCapabilities'),
('wms', 'Nationale Parken (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nationaleparken/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Nationale Parken (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nationaleparken/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Nationale Streekpaden (WMS | Open) ','https://geodata.nationaalgeoregister.nl/streekpaden/wms?request=GetCapabilities'),
('wms', 'Natura 2000 (WMS | Open) ','https://geodata.nationaalgeoregister.nl/natura2000/wms?&request=getcapabilities'),
('wfs', 'Natura 2000 (WFS | Open) ','https://geodata.nationaalgeoregister.nl/natura2000/wfs?version=1.0.0&request=GetCapabilities'),
# zit in algememe wmts caps: Natura 2000 (WMTS | Open) http://geodata.nationaalgeoregister.nl/tiles/service/wmts/natura2000?VERSION=1.0.0&request=GetCapabilities
# geen TMS: Natura 2000 (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/natura2000@EPSG:28992@png8
('wms','Natuurmeting Op Kaart 2010 (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nok2010/wms?service=wms&request=getcapabilities'),
('wfs','Natuurmeting Op Kaart 2011 (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nok2011/wfs?version=1.0.0&request=GetCapabilities'),
# zit in algememe wmts caps: Natuurmeting Op Kaart 2011 (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/nok2011?VERSION=1.0.0&request=GetCapabilities
('wms', 'Natuurmeting Op Kaart 2011 (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nok2011/wms?service=wms&request=getcapabilities'),
# geen TMS: Natuurmeting Op Kaart 2011 (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/nok2011@EPSG:28992@png8
('wms', 'Natuurmeting Op Kaart 2012 (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nok2012/wms?request=GetCapabilities'),
('wfs','Natuurmeting Op Kaart 2012 (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nok2012/wfs?version=1.0.0&request=GetCapabilities'),
('wms','Natuurmeting Op Kaart 2013 (WMS | Open)','https://geodata.nationaalgeoregister.nl/nok2013/wms?request=GetCapabilities'),
('wfs','Natuurmeting Op Kaart 2013 (WFS | Open)','https://geodata.nationaalgeoregister.nl/nok2013/wfs?version=1.0.0&request=GetCapabilities'),
('wms','Natuurmeting Op Kaart 2014 (WMS | Open)','https://geodata.nationaalgeoregister.nl/nok2014/wms?request=GetCapabilities'),
('wfs','Natuurmeting Op Kaart 2014 (WFS | Open)','https://geodata.nationaalgeoregister.nl/nok2014/wfs?version=1.0.0&request=GetCapabilities'),
('wms','Noordzee Vaarwegmarkeringen (WMS | Open)','https://geodata.nationaalgeoregister.nl/noordzeevaarwegmarkeringenrd/wms?service=wms&version=1.0.0&request=getcapabilities'),
('wfs','Noordzee Vaarwegmarkeringen (WFS | Open) ','https://geodata.nationaalgeoregister.nl/noordzeevaarwegmarkeringenrd/wfs?version=1.0.0&request=GetCapabilities'),
('wms','Nulmeting op Kaart 2007 (NOK2007) (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nok2007/wms?service=wms&request=getcapabilities'),
#('wms','Noordzee Wingebieden (WMS | Open)' , 'http://geodata.nationaalgeoregister.nl/noordzeewingebieden/wms?service=wms&version=1.0.0&request=GetCapabilities'),
#('wfs','Noordzee Wingebieden (WFS | Open) ','http://geodata.nationaalgeoregister.nl/noordzeewingebieden/wfs?version=1.0.0&request=GetCapabilities'),
# NWB Spoorwegen eruit wordt Spoorwegen prorail?
#('wfs','NWB-Spoorwegen (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nwbspoorwegen/wfs?version=1.0.0&request=GetCapabilities'),
#('wms','NWB-Spoorwegen (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nwbspoorwegen/wms?SERVICE=WMS&request=GetCapabilities'),
#
('wfs','NWB-Vaarwegen (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nwbvaarwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms','NWB-Vaarwegen (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nwbvaarwegen/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs','NWB-Wegen (WFS | Open) ','https://geodata.nationaalgeoregister.nl/nwbwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms','NWB-Wegen (WMS | Open) ','https://geodata.nationaalgeoregister.nl/nwbwegen/wms?SERVICE=WMS&request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/o
('wms','Oppervlaktewaterlichamen (WMS | Open)','https://geodata.nationaalgeoregister.nl/rwsoppervlaktewaterlichamen/wms?request=GetCapabilities'),
('wfs','Oppervlaktewaterlichamen (WFS | Open)','https://geodata.nationaalgeoregister.nl/rwsoppervlaktewaterlichamen/wfs?request=GetCapabilities'),
('wms','Overheidsdiensten (WMS | Open)','https://geodata.nationaalgeoregister.nl/overheidsdiensten/wms?request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/p
('wms', 'Potentiekaart omgevingswarmte (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/omgevingswarmte/wms?request=GetCapabilities'),
('wfs', 'Potentiekaart omgevingswarmte (WFS | Open))', 'https://geodata.nationaalgeoregister.nl/omgevingswarmte/wfs?request=GetCapabilities'),
('wms', 'Potentiekaart reststromen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/reststromen/wms?request=GetCapabilities'),
('wfs', 'Potentiekaart reststromen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/reststromen/wfs?request=GetCapabilities'),
('wms', 'Potentiekaart restwarmte (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/restwarmte/wms?request=GetCapabilities'),
('wfs', 'Potentiekaart restwarmte (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/restwarmte/wfs?request=GetCapabilities'),
('wms', 'Publiekrechtelijke Beperking (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/publiekrechtelijkebeperking/wms?request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/r
('wms', 'RDinfo (WMS | Open) ','https://geodata.nationaalgeoregister.nl/rdinfo/wms?service=wms&request=getcapabilities'),
('wfs', 'RDinfo (WFS | Open) ','https://geodata.nationaalgeoregister.nl/rdinfo/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Ruimtelijke plannen (WMS | Open) ','https://geodata.nationaalgeoregister.nl/plu/wms?service=wms&request=getcapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/s
('wms', 'Schelpdierenpercelen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/schelpdierenpercelen/wms?request=GetCapabilities'),
('wfs', 'Schelpdierenpercelen (WFS | Open)','https://geodata.nationaalgeoregister.nl/schelpdierenpercelen/wfs?request=GetCapabilities'),
('wms', 'Schelpdierwater (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/schelpdierwater/wms?request=getcapabilities'),
('wfs', 'Schelpdierwater (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/schelpdierwater/wfs?request=getcapabilities'),
('wms', 'Spoorwegen (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/spoorwegen/wms?request=GetCapabilities'),
('wfs', 'Spoorwegen (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/spoorwegen/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Statistical Units Grid (WMS | Open)','https://geodata.nationaalgeoregister.nl/inspire/su-grid/wms?&request=GetCapabilities'),
('wfs', 'Statistical Units Grid (WFS | Open)','https://geodata.nationaalgeoregister.nl/inspire/su-grid/wfs?&request=GetCapabilities'),
('wms', 'Stort- en loswallen (WMS | Open)','https://geodata.nationaalgeoregister.nl/stortenloswallen/wms?request=GetCapabilities'),
('wfs', 'Stort- en loswallen (WFS | Open)','https://geodata.nationaalgeoregister.nl/stortenloswallen/wfs?request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/t
('wms','TOP1000raster (WMS | Open)','https://geodata.nationaalgeoregister.nl/top1000raster/wms?request=GetCapabilities'),
('wms','TOP100raster (WMS | Open)','https://geodata.nationaalgeoregister.nl/top100raster/wms?request=GetCapabilities'),
# zit in algememe wmts caps: TOP10NL (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top10nl?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP10NL (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top10nl@EPSG:28992@png8
('wms','TOP10NL (WMS | Open) ','https://geodata.nationaalgeoregister.nl/top10nlv2/wms?request=GetCapabilities'),
# zit in algememe wmts caps: TOP250raster (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top250raster?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP250raster (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top250raster@EPSG:28992@png8
('wms', 'TOP250raster (WMS | Open) ','https://geodata.nationaalgeoregister.nl/top250raster/wms?&Request=getcapabilities'),
#zit in algemene wmts caps: Top25raster (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top25raster?VERSION=1.0.0&request=GetCapabilities
('wms','TOP25raster (WMS | Open)','https://geodata.nationaalgeoregister.nl/top25raster/wms?request=GetCapabilities'),
# zit in algememe wmts caps: TOP50raster (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top50raster?VERSION=1.0.0&request=GetCapabilities
('wms', 'TOP500raster (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/top500raster/wms?request=GetCapabilities'),
# geen TMS: TOP50raster (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top50raster@EPSG:28992@png8
('wms', 'TOP50raster (WMS | Open) ','https://geodata.nationaalgeoregister.nl/top50raster/wms?&Request=getcapabilities'),
# zit in algememe wmts caps: TOP50vector (WMTS | Open) http://geodata.nationaalgeoregister.nl/wmts/top50vector?VERSION=1.0.0&request=GetCapabilities
# geen TMS: TOP50vector (TMS | Open) http://geodata.nationaalgeoregister.nl/tms/1.0.0/top50vector@EPSG:28992@png8
#('wms', 'TOP50vector (WMS | Open) ','https://geodata.nationaalgeoregister.nl/top50vector/wms?&Request=getcapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/v
('wms', 'Vaarweg Informatie Nederland (VIN) (WMS | Open) ','https://geodata.nationaalgeoregister.nl/vin/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Vaarweg Informatie Nederland (VIN) (WFS | Open) ','https://geodata.nationaalgeoregister.nl/vin/wfs?version=1.0.0&request=GetCapabilities '),
('wms', 'Verkeersscheidingsstelsel (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/verkeersscheidingsstelsel/wms?request=getcapabilities'),
('wfs', 'Verkeersscheidingsstelsel (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/verkeersscheidingsstelsel/wfs?request=getcapabilities'),
('wms', 'Verspreidingsgebied habitattypen (WMS | Open)','https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wms?request=GetCapabilities'),
('wfs', 'Verspreidingsgebied habitattypen (WFS | Open)','https://geodata.nationaalgeoregister.nl/habitatrichtlijnverspreidinghabitattypen/wfs?request=GetCapabilities'),


('wms', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/tn/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Gemeenschappelijke elementen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/tn/wfs?&request=GetCapabilities'),

('wms', 'Vervoersnetwerken - Kabelbanen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-c/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Kabelbanen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-c/wfs?&request=GetCapabilities'),
('wms', 'Vervoersnetwerken - Luchttransport (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/tn-a/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Luchttransport (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/tn-a/wfs?&request=GetCapabilities'),
# foutmelding door newlines in formats
#('wms', 'Vervoersnetwerken - Spoorwegen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-ra/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Spoorwegen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-ra/wfs?&request=GetCapabilities'),
('wms', 'Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-w/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Waterwegen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/inspire/tn-w/wfs?&request=GetCapabilities'),
('wms', 'Vervoersnetwerken - Wegen (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/tn-ro/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken - Wegen (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/tn-ro/wfs?&request=GetCapabilities'),
('wms', 'Vervoersnetwerken Waterwegen RWS (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-w/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken Waterwegen RWS (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-w/wfs?&request=GetCapabilities'),
('wms', 'Vervoersnetwerken Wegen RWS (INSPIRE geharmoniseerd) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-ro/wms?&request=GetCapabilities'),
('wfs', 'Vervoersnetwerken Wegen RWS (INSPIRE geharmoniseerd) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/nl/rws/tn-ro/wfs?&request=GetCapabilities'),
('wms', 'Vogelrichtlijn verspreiding van soorten (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsoorten/wms?request=GetCapabilities'),
('wfs', 'Vogelrichtlijn verspreiding van soorten (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/vogelrichtlijnverspreidingsoorten/wfs?request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/w
('wms', 'Waterschappen Administratieve eenheden INSPIRE (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wsaeenhedeninspire/wms?request=GetCapabilities'),
('wms', 'Waterschappen Hydrografie INSPIRE (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wshydrografieinspire/wms?request=GetCapabilities'),
('wms', 'Waterschappen Kunstwerken IMWA (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wskunstwerkenimwa/wms?request=GetCapabilities'),
('wms', 'Waterschappen Nuts-Overheidsdiensten INSPIRE (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wsdiensteninspire/wms?request=GetCapabilities'),
('wms', 'Waterschappen Oppervlaktewateren IMWA (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wsaoppervlaktewaterenimwa/wms?request=GetCapabilities'),
('wms', 'Waterschappen Waterbeheergebieden IMWA (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wswaterbeheergebiedenimwa/wms?request=GetCapabilities'),
('wms', 'Weggegevens (Weggeg) (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/weggeg/wms?SERVICE=WMS&request=GetCapabilities'),
('wfs', 'Weggegevens (Weggeg) (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/weggeg/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Wetlands (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/wetlands/ows?service=wms&request=getcapabilities'),
('wfs', 'Wetlands (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/wetlands/wfs?version=1.0.0&request=GetCapabilities'),
('wms', 'Windsnelheden 100m hoogte (WMS | Open)','https://geodata.nationaalgeoregister.nl/windkaart/wms?request=GetCapabilities'),
('wfs', 'Windsnelheden 100m hoogte (WFS | Open)','https://geodata.nationaalgeoregister.nl/windkaart/wfs?request=GetCapabilities'),

# https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls/z
('wms', 'Zeegraskartering (WMS | Open)', 'https://geodata.nationaalgeoregister.nl/zeegraskartering/wms?request=GetCapabilities'),
('wfs', 'Zeegraskartering (WFS | Open)', 'https://geodata.nationaalgeoregister.nl/zeegraskartering/wfs?request=GetCapabilities'),
]

# testing
_services = [

('wmts', 'Luchtfoto Beeldmateriaal / PDOK 25 cm RGB (WMTS | Open)', 'https://geodata.nationaalgeoregister.nl/luchtfoto/rgb/wmts?request=GetCapabilities&service=WMTS'),

]


firstOne = True
# fix_print_with_import
print('{"services":[', end=' ')

for (stype, title, url) in services:
    #print '\n --> %s'%url
    if stype == 'wms':
        handleWMS(url)
    elif stype == 'wmts':
        handleWMTS(url)
    elif stype == 'wfs':
        handleWFS(url)
    elif stype == 'wcs':
        handleWCS(url)

# fix_print_with_import
print(']}')
