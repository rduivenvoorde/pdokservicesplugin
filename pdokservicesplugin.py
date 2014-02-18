# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin
                                 A QGIS plugin


Services url:

http://pdokviewer.pdok.nl/config/default.xml
and
https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls

from 

http://pdokviewer.pdok.nl/

                              -------------------
        begin                : 2012-10-11
        copyright            : (C) 2012 by Richard Duivenvoorde
        email                : richard@webmapper.net
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
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
import json
import os
import urllib
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from pdokservicesplugindialog import PdokServicesPluginDialog
from xml.dom.minidom import parse
import pdokgeocoder

class PdokServicesPlugin:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # Create the dialog and keep reference
        self.dlg = PdokServicesPluginDialog()
        # initialize plugin directory
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDbFilePath()).path() + "/python/plugins/pdokservicesplugin"
        # initialize locale
        localePath = ""
        if isinstance(QSettings().value("locale/userLocale"), QVariant):
            locale = QSettings().value("locale/userLocale").toString()[0:2]
        else:
            locale = QSettings().value("locale/userLocale")[0:2]

        if QFileInfo(self.plugin_dir).exists():
            localePath = self.plugin_dir + "/i18n/pdokservicesplugin_" + locale + ".qm"

        if QFileInfo(localePath).exists():
            self.translator = QTranslator()
            self.translator.load(localePath)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
        self.currentLayer = None
        self.pointer = None


    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/pdokservicesplugin/icon.png"), \
            u"Pdok Services Plugin", self.iface.mainWindow())
        # connect the action to the run method
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.action)
        self.servicesLoaded = False

        # about
        self.aboutAction = QAction(QIcon(":/plugins/pdokservicesplugin/help.png"), \
                            "About", self.iface.mainWindow())
        self.aboutAction.setWhatsThis("Pdok Services Plugin About")
        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.aboutAction)

        QObject.connect(self.aboutAction, SIGNAL("activated()"), self.about)
        QObject.connect(self.dlg.ui.btnLoadLayer, SIGNAL("clicked()"), self.loadService)

        self.dlg.geocoderSearchBtn.clicked.connect(self.searchAddress)
        self.dlg.geocoderSearch.returnPressed.connect(self.searchAddress)

        self.dlg.geocoderResultSearch.textChanged.connect(self.filterGeocoderResult)

        self.dlg.buttonBox.button(QDialogButtonBox.Close).setAutoDefault(False)


    def about(self):
        infoString = QString("Written by Richard Duivenvoorde\nEmail - richard@duif.net\n")
        infoString = infoString.append("Company - http://www.webmapper.net\n")
        infoString = infoString.append("Source: https://github.com/rduivenvoorde/pdokservicesplugin")
        QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin About", infoString)

    def unload(self):
        self.removePointer()
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&Pdok Services Plugin",self.action)
        self.iface.removeToolBarIcon(self.action)

    def showService(self, selectedIndexes):
        if len(selectedIndexes)==0:
            self.currentLayer = None
            self.dlg.ui.layerInfo.setHtml('')
            return
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[1])
        # itemType holds the data (== column 1)
        self.currentLayer = self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)
        if isinstance(self.currentLayer, QVariant):
            self.currentLayer = self.currentLayer.toMap()
            # QGIS 1.8: QVariants
            currentLayer = {}
            for key in self.currentLayer.keys():
                val = self.currentLayer[key]
                print unicode(val.toString())
                currentLayer[unicode(key)]=unicode(val.toString())
            self.currentLayer = currentLayer
        url = self.currentLayer['url']
        title = self.currentLayer['title']
        servicetitle = self.currentLayer['servicetitle']
        layername = self.currentLayer['layers']
        abstract = self.currentLayer['abstract']
        stype = self.currentLayer['type'].upper()
        minscale =''
        if self.currentLayer.has_key('minscale') and self.currentLayer['minscale'] != None and self.currentLayer['minscale'] != '':
            minscale = "min. schaal 1:"+self.currentLayer['minscale']
        maxscale = ''
        if self.currentLayer.has_key('maxscale') and self.currentLayer['maxscale'] != None and self.currentLayer['maxscale'] != '':
            maxscale = "max. schaal 1:"+self.currentLayer['maxscale']
        self.dlg.ui.layerInfo.setText('')
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.layerInfo.setHtml('<h4>%s</h4><h3>%s</h3><lu><li>%s</li><li>&nbsp;</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li></lu>' % (servicetitle, title, abstract, stype, url, layername, minscale, maxscale))

    def loadService(self):
        if self.currentLayer == None:
            return
        servicetype = self.currentLayer['type']
        url = self.currentLayer['url']
        # some services have an url with query parameters in it, we have to urlencode those:
        location,query = urllib.splitquery(url)
        url = location
        if query != None and query != '':
            url +=('?'+urllib.quote_plus(query))
        title = self.currentLayer['title']
        layers = self.currentLayer['layers']
        # mmm, tricky: we take the first one while we can actually want png/gif or jpeg
        if servicetype=="wms":
            imgformat = self.currentLayer['imgformats'].split(',')[0]
            if QGis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                uri = url
                self.iface.addRasterLayer(
                    uri, # service uri
                    title, # name for layer (as seen in QGIS)
                    "wms", # dataprovider key
                    [layers], # array of layername(s) for provider (id's)
                    [""], # array of stylename(s)
                    imgformat, # image format searchstring
                    "EPSG:28992") # crs code searchstring
            else:
                # qgis > 1.8
                uri = "crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url;
                self.iface.addRasterLayer(uri, title, "wms")
        elif servicetype=="wmts":
            if QGis.QGIS_VERSION_INT < 10900:
                QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+servicetype.upper()+"' \nkan niet worden geladen in deze versie van QGIS.\nMisschien kunt u QGIS 2.0 installeren (die kan het WEL)?\nOf is de laag niet ook beschikbaar als wms of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
                return
            # tilematrixsets and imgformat can be more then one, split on comma and take first one
            tilematrixsets = self.currentLayer['tilematrixsets'].split(',')[0]
            # hack because ...
            if tilematrixsets == '':
                tilematrixsets = 'EPSG:28992'
            imgformat = self.currentLayer['imgformats'].split(',')[0]
            # special case for luchtfoto
            #if layers=="luchtfoto":
            #    # tileMatrixSet=nltilingschema&crs=EPSG:28992&layers=luchtfoto&styles=&format=image/jpeg&url=http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml
            #    # {u'layers': u'luchtfoto', u'imgformats': u'image/jpeg', u'title': u'PDOK-achtergrond luchtfoto', u'url': u'http://geodata1.nationaalgeoregister.nl/luchtfoto/wms', u'abstract': u'', u'tilematrixsets': u'nltilingschema', u'type': u'wmts'}
            #    uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url
            #else:
            #    uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url;
            uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url;
            #print "############ PDOK URI #################"
            #print uri
            self.iface.addRasterLayer(uri, title, "wms")
        elif servicetype=="wfs":
            location,query = urllib.splitquery(url)
            uri = location+"?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME="+layers+"&SRSNAME=EPSG:28992"
            # adding a bbox paramater forces QGIS to NOT cache features but retrieve new features all the time
            # QGIS will update the BBOX to the right value
            uri += "&BBOX=0,300000,300000,600000"
            self.iface.addVectorLayer(uri, title, "WFS")
        elif servicetype=="wcs":
            # cache=AlwaysCache&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            uri = ''
            # cache=AlwaysCache
            # cache=PreferNetwork 
            # cache=AlwaysNetwork
            # cache=AlwaysNetwork&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            uri = "cache=AlwaysCache&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs"
            self.iface.addRasterLayer(uri, title, "wcs")
        else:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+servicetype.upper()+"' \nkan niet worden geladen door de plugin of door QGIS.\nIs het niet beschikbaar als wms, wmts of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
            return

    def filterGeocoderResult(self, string):
        #print "filtering geocoder results: %s" % string
        self.dlg.geocoderResultView.selectRow(0)
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def searchAddress(self):
        self.removePointer()
        #print "search geocoder for: %s" % self.dlg.geocoderSearch.text()
        self.geocoderSourceModel.clear()
        self.geocode(self.dlg.geocoderSearch.text())

    def filterLayers(self, string):
        # remove selection if one row is selected
        self.dlg.servicesView.selectRow(0)
        #self.currentLayer = None
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxyModel.setFilterFixedString(string)

    #def addSourceRow(self, service, layer):
    def addSourceRow(self, serviceLayer):
        # you can attache different "data's" to to an QStandarditem
        # default one is the visible one:
        itemType = QStandardItem("%s" % (serviceLayer["type"].upper()) )
        # userrole is a free form one:
        # only attach the data to the first item
        # service layer = a dict/object with all props of the layer
        itemType.setData( serviceLayer, Qt.UserRole )
        itemLayername = QStandardItem("%s" % (serviceLayer["title"]))
        itemServicetitle = QStandardItem("%s" % (serviceLayer["servicetitle"]))
        itemFilter = QStandardItem("%s %s %s %s" % (serviceLayer["type"], serviceLayer["title"], serviceLayer["servicetitle"], serviceLayer["abstract"]) )
        self.sourceModel.appendRow( [itemServicetitle, itemType, itemLayername, itemFilter] )

    # run method that performs all the real work
    def run(self):
        # last viewed/selected tab
        if QSettings().contains("/pdokservicesplugin/currenttab"):
            if QGis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                self.dlg.tabs.widget(QSettings().value("/pdokservicesplugin/currenttab").toInt()[0])
            else:
                self.dlg.tabs.widget(int(QSettings().value("/pdokservicesplugin/currenttab")))

        if self.servicesLoaded == False:
            pdokjson = os.path.join(os.path.dirname(__file__), ".","pdok.json")
            f = open(pdokjson,'r')
            self.pdok = json.load(f)

            self.proxyModel = QSortFilterProxyModel()
            self.sourceModel = QStandardItemModel()
            self.proxyModel.setSourceModel(self.sourceModel)
            # filter == search on itemFilter column:
            self.proxyModel.setFilterKeyColumn(3)
            self.dlg.servicesView.setModel(self.proxyModel)
            self.dlg.servicesView.setEditTriggers(QAbstractItemView.NoEditTriggers)

            self.geocoderProxyModel = QSortFilterProxyModel()
            self.geocoderSourceModel = QStandardItemModel()

            self.geocoderProxyModel.setSourceModel(self.geocoderSourceModel)
            self.geocoderProxyModel.setFilterKeyColumn(0)
            self.dlg.geocoderResultView.setModel(self.geocoderProxyModel)
            self.dlg.geocoderResultView.setEditTriggers(QAbstractItemView.NoEditTriggers)

            #{"services":[
            #   {"naam":"WMS NHI","url":"http://geodata.nationaalgeoregister.nl/nhi/ows","layers":["dmlinks","dmnodes"],"type":"wms"},
            #   {"naam":"WMS NHI","url":"http://geodata.nationaalgeoregister.nl/nhi/ows","layers":["dmlinks","dmnodes"],"type":"wms"}
            # ]}
            # 
            for service in self.pdok["services"]:
                # service[layer] was an array
                if isinstance(service["layers"], str) or isinstance(service["layers"], unicode):
                    self.addSourceRow(service)

            self.dlg.layerSearch.textChanged.connect(self.filterLayers)
            self.dlg.servicesView.selectionModel().selectionChanged.connect(self.showService)
            self.dlg.servicesView.doubleClicked.connect(self.loadService)

            self.dlg.geocoderResultView.doubleClicked.connect(self.zoomToAddress)

            # hide itemFilter column:
            self.dlg.servicesView.hideColumn(3)
            self.servicesLoaded = True;

        self.sourceModel.setHeaderData(0, Qt.Horizontal, "Service")
        self.sourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.sourceModel.setHeaderData(2, Qt.Horizontal, "Laagnaam")
        self.sourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
        #self.dlg.servicesView.verticalHeader().hide()
        self.dlg.servicesView.resizeColumnsToContents()
        self.dlg.servicesView.horizontalHeader().setStretchLastSection(True)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        if QGis.QGIS_VERSION_INT < 10900:
            # qgis <= 1.8
            QSettings().setValue("/pdokservicesplugin/currenttab", QVariant(self.dlg.tabs.currentIndex()))
        else:
            QSettings().setValue("/pdokservicesplugin/currenttab", self.dlg.tabs.currentIndex())
        self.removePointer()

    def geocode(self, string):
        addresses = pdokgeocoder.search(string)
        if len(addresses) == 0:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ( \
                "Niets gevonden. Probeer een andere spelling of alleen postcode/huisnummer."
                ), QMessageBox.Ok, QMessageBox.Ok)
            return
        for address in addresses:
            #print address
            adrestekst = QStandardItem("%s" % (address["adrestekst"]))
            adrestekst.setData( address, Qt.UserRole )
            straat = QStandardItem("%s" % (address["straat"]))
            adres = QStandardItem("%s" % (address["adres"]))
            postcode = QStandardItem("%s" % (address["postcode"]))
            plaats = QStandardItem("%s" % (address["plaats"]))
            gemeente = QStandardItem("%s" % (address["gemeente"]))
            provincie = QStandardItem("%s" % (address["provincie"]))
            self.geocoderSourceModel.appendRow( [adrestekst, straat, adres, postcode, plaats, gemeente, provincie ] )

        self.geocoderSourceModel.setHeaderData(0, Qt.Horizontal, "Resultaat")
        self.geocoderSourceModel.setHeaderData(1, Qt.Horizontal, "Straat")
        self.geocoderSourceModel.setHeaderData(2, Qt.Horizontal, "Nr")
        self.geocoderSourceModel.setHeaderData(3, Qt.Horizontal, "Postcode")
        self.geocoderSourceModel.setHeaderData(4, Qt.Horizontal, "Plaats")
        self.geocoderSourceModel.setHeaderData(5, Qt.Horizontal, "Gemeente")
        self.geocoderSourceModel.setHeaderData(6, Qt.Horizontal, "Provincie")

        self.geocoderSourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(3).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(4).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(5).setTextAlignment(Qt.AlignLeft)
        self.geocoderSourceModel.horizontalHeaderItem(6).setTextAlignment(Qt.AlignLeft)

        self.dlg.geocoderResultView.resizeColumnsToContents()
        self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)

    def zoomToAddress(self, modelindex):
        # get x,y from data of record
        self.removePointer()
        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.UserRole)
        point = QgsPoint( data['x'], data['y'])
        # just always transform from 28992 to mapcanvas crs
        if hasattr(self.iface.mapCanvas().mapRenderer(), "destinationSrs"):
            # QGIS < 2.0
            crs = self.iface.mapCanvas().mapRenderer().destinationSrs()
        else:
            crs = self.iface.mapCanvas().mapRenderer().destinationCrs()
        crs28992 = QgsCoordinateReferenceSystem()
        crs28992.createFromId(28992)
        crsTransform = QgsCoordinateTransform(crs28992, crs)

        r = 100
        if data['adrestekst'].startswith('adres'):
            r = 75
        elif data['adrestekst'].startswith('straat'):
            r = 150
        elif data['adrestekst'].startswith('postcode'):
            r = 500
        elif data['adrestekst'].startswith('plaats'):
            r = 1000
        elif data['adrestekst'].startswith('gemeente'):
            r = 2000
        elif data['adrestekst'].startswith('provincie'):
            r = 30000

        geom = QgsGeometry.fromPoint(point)
        geom.transform(crsTransform)
        self.setPointer(geom.asPoint())
        self.iface.mapCanvas().setExtent(geom.buffer(r, 1).boundingBox())
        self.iface.mapCanvas().refresh()

    def setPointer(self, point):
        self.removePointer()
        self.pointer = QgsVertexMarker(self.iface.mapCanvas())
        self.pointer.setColor(QColor(255,255,0))
        self.pointer.setIconSize(10)
        self.pointer.setPenWidth(5)
        self.pointer.setCenter(point)

    def removePointer(self):
        if self.pointer is not None:
            self.iface.mapCanvas().scene().removeItem(self.pointer)
