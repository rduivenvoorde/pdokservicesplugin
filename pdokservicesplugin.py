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
        email                : richard@zuidt.nl
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
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import object
# Import the PyQt and QGIS libraries
from qgis.PyQt.QtCore import QSettings, QVariant, QFileInfo, QObject, Qt
from qgis.PyQt.QtWidgets import QAction, QLineEdit, QAbstractItemView, QMessageBox
from qgis.PyQt.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtCore import QSortFilterProxyModel
from qgis.core import QgsApplication, Qgis, QgsPoint,QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsRectangle
from qgis.gui import QgsVertexMarker

import json
import os
import urllib.request, urllib.parse, urllib.error
# Initialize Qt resources from file resources.py
from . import resources_rc
# Import the code for the dialog
from .pdokservicesplugindialog import PdokServicesPluginDialog
from .pdokservicesplugindialog import PdokServicesPluginDockWidget
from xml.dom.minidom import parse
from . import pdokgeocoder

class PdokServicesPlugin(object):

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # docked or dialog, defaults to dialog
        if isinstance(QSettings().value("locale/userLocale"), QVariant):
            self.docked = QSettings().value("/pdokservicesplugin/docked", QVariant(False)).toBool()
        else:
            self.docked = QSettings().value("/pdokservicesplugin/docked", False)
        # Create the dialog and keep reference
        if "True" == self.docked or "true" == self.docked or  True == self.docked:
            self.dlg = PdokServicesPluginDockWidget()
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dlg)
        else:
            self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())
        # initialize plugin directory
        self.plugin_dir = QFileInfo(QgsApplication.qgisUserDatabaseFilePath()).path() + "/python/plugins/pdokservicesplugin"
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
        self.SETTINGS_SECTION = '/pdokservicesplugin/'
        self.pointer = None
        self.geocoderSourceModel = None

    def getSettingsValue(self, key, default=''):
        if QSettings().contains(self.SETTINGS_SECTION + key):
            key = self.SETTINGS_SECTION + key
            if Qgis.QGIS_VERSION_INT < 10900: # qgis <= 1.8
                return str(QSettings().value(key).toString())
            else:
                return str(QSettings().value(key))
        else:
            return default
    def setSettingsValue(self, key, value):
        key = self.SETTINGS_SECTION + key
        if Qgis.QGIS_VERSION_INT < 10900:
            # qgis <= 1.8
            QSettings().setValue(key, QVariant(value))
        else:
            QSettings().setValue(key, value)


    def initGui(self):
        # Create action that will start plugin configuration
        self.run_action = QAction(QIcon(":/plugins/pdokservicesplugin/icon.png"), \
            u"Pdok Services Plugin", self.iface.mainWindow())

        self.servicesLoaded = False
        # connect the action to the run method
        if "True" == self.docked or "true" == self.docked or  True == self.docked:
            self.run_action.triggered.connect(self.showAndRaise)
            self.dlg.radioDocked.setChecked(True)
            # docked the dialog is immidiately visible, so should run NOW
        else:
            self.run_action.triggered.connect(self.run)
            self.dlg.radioDocked.setChecked(False)

        # Add toolbar button and menu item
        #self.iface.addToolBarIcon(self.action)

        self.toolbar = self.iface.addToolBar("PDOK services plugin")
        self.toolbar.setObjectName("PDOK services plugin")
        self.toolbar.addAction(self.run_action)
        self.toolbarSearch = QLineEdit()
        self.toolbarSearch.setMaximumWidth(200)
        self.toolbarSearch.setAlignment(Qt.AlignLeft)
        self.toolbarSearch.setPlaceholderText("PDOK Geocoder zoek")
        self.toolbar.addWidget(self.toolbarSearch)
        self.toolbarSearch.returnPressed.connect(self.searchAddressFromToolbar)
        # address/point cleanup
        self.clean_action = QAction(QIcon(":/plugins/pdokservicesplugin/eraser.png"), \
            u"Cleanup", self.eraseAddress())
        self.toolbar.addAction(self.clean_action)
        self.clean_action.triggered.connect(self.eraseAddress)

        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.run_action)

        # about
        self.aboutAction = QAction(QIcon(":/plugins/pdokservicesplugin/help.png"), \
                            "About", self.iface.mainWindow())
        self.aboutAction.setWhatsThis("Pdok Services Plugin About")
        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.aboutAction)

        self.aboutAction.triggered.connect(self.about)
        self.dlg.ui.btnLoadLayer.clicked.connect(self.loadService)

        self.dlg.geocoderSearchBtn.clicked.connect(self.searchAddress)
        self.dlg.geocoderSearch.returnPressed.connect(self.searchAddress)
        self.dlg.geocoderSearch.setPlaceholderText("PDOK Geocoder zoek, bv postcode of postcode huisnummer")

        self.dlg.geocoderResultSearch.textChanged.connect(self.filterGeocoderResult)
        self.dlg.geocoderResultSearch.setPlaceholderText("een of meer zoekwoorden uit resultaat")

        self.dlg.radioDocked.toggled.connect(self.set_docked)

        self.dlg.btnCheckPdokJson.clicked.connect(self.checkPdokJson)
        #self.iface.mapCanvas().renderStarting.connect(self.extentsChanged)

        self.run(True)

    # for now hiding the pointer as soon as the extent changes
    #def extentsChanged(self):
    #    self.removePointer()

    def checkPdokJson(self):
        myversion = self.getSettingsValue('pdokversion', '1')
        msgtxt = ''
        msglvl = 0  # QgsMessageBar.INFO
        try:
            response = urllib.request.urlopen('http://www.qgis.nl/pdok.version')
            str_response = response.read().decode('utf-8')
            pdokversion = json.loads(str_response)
            if pdokversion > int(myversion):
                response = urllib.request.urlopen('http://www.qgis.nl/pdok.json')
                str_response = response.read().decode('utf-8')
                pdokjson = json.loads(str_response)
                with open(self.plugin_dir +'/pdok.json', 'w') as outfile:
                    json.dump(pdokjson, outfile)
                msgtxt = "De laatste versie is opgehaald en zal worden gebruikt " + \
                    str(pdokversion) + ' (was ' + myversion +')'
                self.servicesLoaded = False # reset reading of json
                self.run()
                self.setSettingsValue('pdokversion', pdokversion)
            else:
                msgtxt = "Geen nieuwere versie beschikbaar dan " + str(pdokversion)
        except Exception as e:
            #print e
            msgtxt = "Fout bij ophalen van service info. Netwerk probleem?"
            msglvl = 2 # QgsMessageBar.CRITICAL
        # msg
        if hasattr(self.iface, 'messageBar'):
            self.iface.messageBar().pushMessage("PDOK services update", msgtxt, level=msglvl, duration=10)
        else: # 1.8
            QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin", msgtxt)

    def set_docked(self, foo):
        self.setSettingsValue('docked', self.dlg.radioDocked.isChecked())
        #if Qgis.QGIS_VERSION_INT < 10900:
        #    # qgis <= 1.8
        #    QSettings().setValue("/pdokservicesplugin/docked", QVariant(self.dlg.radioDocked.isChecked()))
        #else:
        #    QSettings().setValue("/pdokservicesplugin/docked", self.dlg.radioDocked.isChecked())

    def showAndRaise(self):
        self.dlg.show()
        self.dlg.raise_()
        # also remove the pointer
        self.removePointer()

    def about(self):
        infoString =  "Written by Richard Duivenvoorde\nEmail - richard@duif.net\n"
        infoString += "Company - Zuidt - http://www.zuidt.nl\n"
        infoString += "Source: https://github.com/rduivenvoorde/pdokservicesplugin"
        QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin About", infoString)

    def unload(self):
        self.removePointer()
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&Pdok Services Plugin",self.run_action)
        del self.toolbarSearch

    def showService(self, selectedIndexes):
        if len(selectedIndexes)==0:
            self.currentLayer = None
            self.dlg.ui.layerInfo.setHtml('')
            return
        # needed to scroll To the selected row incase of using the keyboard / arrows
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[0])
        # itemType holds the data (== column 1)
        self.currentLayer = self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)
        if isinstance(self.currentLayer, QVariant):
            self.currentLayer = self.currentLayer.toMap()
            # QGIS 1.8: QVariants
            currentLayer = {}
            for key in list(self.currentLayer.keys()):
                val = self.currentLayer[key]
                currentLayer[str(key)]=str(val.toString())
            self.currentLayer = currentLayer
        url = self.currentLayer['url']
        title = self.currentLayer['title']
        style = ''
        if 'style' in self.currentLayer:
            style = self.currentLayer['style']
            title = title + ' [' + style + ']'
        servicetitle = self.currentLayer['servicetitle']
        layername = self.currentLayer['layers']
        abstract = self.currentLayer['abstract']
        stype = self.currentLayer['type'].upper()
        minscale =''
        if 'minscale' in self.currentLayer and self.currentLayer['minscale'] != None and self.currentLayer['minscale'] != '':
            minscale = "min. schaal 1:"+self.currentLayer['minscale']
        maxscale = ''
        if 'maxscale' in self.currentLayer and self.currentLayer['maxscale'] != None and self.currentLayer['maxscale'] != '':
            maxscale = "max. schaal 1:"+self.currentLayer['maxscale']
        self.dlg.ui.layerInfo.setText('')
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.layerInfo.setHtml('<h4>%s</h4><h3>%s</h3><lu><li>%s</li><li>&nbsp;</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li></lu>' % (servicetitle, title, abstract, stype, url, layername, style, minscale, maxscale))

    def loadService(self):
        if self.currentLayer == None:
            return
        servicetype = self.currentLayer['type']
        url = self.currentLayer['url']
        # some services have an url with query parameters in it, we have to urlencode those:
        location,query = urllib.parse.splitquery(url)
        url = location
        if query != None and query != '':
            url +=('?'+urllib.parse.quote_plus(query))
        title = self.currentLayer['title']
        if 'style' in self.currentLayer:
            style = self.currentLayer['style']
            title = title + ' [' + style + ']'
        else:
            style = '' # == default for this service
        layers = self.currentLayer['layers']
        # mmm, tricky: we take the first one while we can actually want png/gif or jpeg
        if servicetype=="wms":
            imgformat = self.currentLayer['imgformats'].split(',')[0]
            if Qgis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                uri = url
                self.iface.addRasterLayer(
                    uri, # service uri
                    title, # name for layer (as seen in QGIS)
                    "wms", # dataprovider key
                    [layers], # array of layername(s) for provider (id's)
                    [""], # array of stylename(s)  NOTE: ignoring styles here!!!
                    imgformat, # image format searchstring
                    "EPSG:28992") # crs code searchstring
            else:
                # qgis > 1.8
                uri = "crs=EPSG:28992&layers="+layers+"&styles="+style+"&format="+imgformat+"&url="+url;
                self.iface.addRasterLayer(uri, title, "wms")
        elif servicetype=="wmts":
            if Qgis.QGIS_VERSION_INT < 10900:
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
            location,query = urllib.parse.splitquery(url)
            uri = location+"?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME="+layers+"&SRSNAME=EPSG:28992"
            # adding a bbox paramater forces QGIS to NOT cache features but retrieve new features all the time
            # QGIS will update the BBOX to the right value
            uri += "&BBOX=-10000,310000,290000,650000"
            self.iface.addVectorLayer(uri, title, "WFS")
        elif servicetype=="wcs":
            # cache=AlwaysCache&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            uri = ''
            # cache=AlwaysCache
            # cache=PreferNetwork 
            # cache=AlwaysNetwork
            # cache=AlwaysNetwork&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            uri = "cache=AlwaysNetwork&crs=EPSG:28992&format=GeoTIFF&identifier="+layers+"&url="+url
            self.iface.addRasterLayer(uri, title, "wcs")
        else:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+servicetype.upper()+"' \nkan niet worden geladen door de plugin of door QGIS.\nIs het niet beschikbaar als wms, wmts of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
            return

    def filterGeocoderResult(self, string):
        #print "filtering geocoder results: %s" % string
        self.dlg.geocoderResultView.selectRow(0)
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def searchAddressFromToolbar(self):
        self.removePointer()
        self.geocoderSourceModel.clear()
        self.geocode(self.toolbarSearch.text())

    def searchAddress(self):
        self.removePointer()
        #print "search geocoder for: %s" % self.dlg.geocoderSearch.text()
        self.geocoderSourceModel.clear()
        self.geocode(self.dlg.geocoderSearch.text())

    def eraseAddress(self):
        """
        clean the input and remove the pointer
        """
        self.removePointer()
        if self.geocoderSourceModel is not None:
            self.geocoderSourceModel.clear()
        if self.dlg.geocoderSearch is not None:
            self.dlg.geocoderSearch.clear()
        if self.toolbarSearch is not None:
            self.toolbarSearch.clear()

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
        itemType.setToolTip("%s - %s" % (serviceLayer["type"].upper() ,serviceLayer["title"] ))
        # only wms services have styles (sometimes)
        layername = serviceLayer["title"]
        if 'style' in serviceLayer:
            itemLayername = QStandardItem("%s [%s]" % (serviceLayer["title"], serviceLayer["style"]) )
            layername = "%s [%s]" % (serviceLayer["title"], serviceLayer["style"])
        else:
            itemLayername = QStandardItem("%s" % (serviceLayer["title"]))
        itemLayername.setToolTip("%s - %s" % (serviceLayer["type"].upper() ,serviceLayer["servicetitle"] ))
        # itemFilter is the item used to search filter in. That is why layername is a combi of layername + filter here
        itemFilter = QStandardItem("%s %s %s %s" % (serviceLayer["type"], layername, serviceLayer["servicetitle"], serviceLayer["abstract"]) )
        itemServicetitle = QStandardItem("%s" % (serviceLayer["servicetitle"]))
        itemServicetitle.setToolTip("%s - %s" % (serviceLayer["type"].upper() ,serviceLayer["title"] ))
        self.sourceModel.appendRow( [ itemLayername, itemType, itemServicetitle, itemFilter ] )

    # run method that performs all the real work
    def run(self, hiddenDialog=False):
        # last viewed/selected tab
        if QSettings().contains("/pdokservicesplugin/currenttab"):
            if Qgis.QGIS_VERSION_INT < 10900:
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
                if isinstance(service["layers"], str) or isinstance(service["layers"], str):
                    self.addSourceRow(service)

            self.dlg.layerSearch.textChanged.connect(self.filterLayers)
            self.dlg.layerSearch.setPlaceholderText("woord uit laagnaam, type of service ")
            self.dlg.servicesView.selectionModel().selectionChanged.connect(self.showService)
            self.dlg.servicesView.doubleClicked.connect(self.loadService)
            # actually I want to load a service when doubleclicked on header
            # but as I cannot get this to work, let's disable clicking it then
            self.dlg.servicesView.verticalHeader().setSectionsClickable(False)
            self.dlg.servicesView.horizontalHeader().setSectionsClickable(False)

            self.dlg.geocoderResultView.doubleClicked.connect(self.zoomToAddress)

            # hide itemFilter column:
            self.dlg.servicesView.hideColumn(3)
            self.servicesLoaded = True;

        self.sourceModel.setHeaderData(2, Qt.Horizontal, "Service")
        self.sourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.sourceModel.setHeaderData(0, Qt.Horizontal, "Laagnaam [style]")
        self.sourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        #self.dlg.servicesView.verticalHeader().hide()
        #self.dlg.servicesView.resizeColumnsToContents()
        self.dlg.servicesView.setColumnWidth(0, 300)  # set name to 300px (there are some huge layernames)
        self.dlg.servicesView.horizontalHeader().setStretchLastSection(True)
        # show the dialog ?
        if not hiddenDialog:
            self.dlg.show()
        # Run the dialog event loop
        #result = self.dlg.exec_()
        if Qgis.QGIS_VERSION_INT < 10900:
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

        #if len(addresses)==1:
        self.dlg.geocoderResultView.selectRow(0)
        self.zoomToAddress()

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

    def zoomToAddress(self):
        # get x,y from data of record
        self.removePointer()
        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.UserRole)
        # 1.8
        if isinstance(data, QVariant):
            data = data.toMap()
            point = QgsPoint( data[QString(u'x')].toInt()[0], data[QString(u'y')].toInt()[0] )
            adrestekst = uniunicodee(data[QString(u'adrestekst')])
        else:
            point = QgsPoint( data['x'], data['y'])
            adrestekst = data['adrestekst']
        # just always transform from 28992 to mapcanvas crs
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        crs28992 = QgsCoordinateReferenceSystem()
        crs28992.createFromId(28992)
        crsTransform = QgsCoordinateTransform(crs28992, crs)

        z = 1587
        if adrestekst.startswith('adres'):
            z = 1587
        elif adrestekst.startswith('straat'):
            z = 3175
        elif adrestekst.startswith('postcode'):
            z = 6350
        elif adrestekst.startswith('plaats'):
            z = 25398
        elif adrestekst.startswith('gemeente'):
            z = 50797
        elif adrestekst.startswith('provincie'):
            z = 812750

        geom = QgsGeometry.fromPoint(point)
        geom.transform(crsTransform)
        center = geom.asPoint()
        self.setPointer(center)
        # zoom to with center is actually setting a point rectangle and then zoom
        rect = QgsRectangle(center, center)
        self.iface.mapCanvas().setExtent(rect)
        self.iface.mapCanvas().zoomScale(z)
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
