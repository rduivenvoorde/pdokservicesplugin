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
# from __future__ import absolute_import
# from future import standard_library
# standard_library.install_aliases()
# from builtins import str
# from builtins import object
# Import the PyQt and QGIS libraries
from qgis.PyQt.QtCore import QSettings, QVariant, QFileInfo, Qt, QTranslator, QCoreApplication, qVersion
from qgis.PyQt.QtWidgets import QAction, QLineEdit, QAbstractItemView, QMessageBox, QMenu, QToolButton
from qgis.PyQt.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtCore import QSortFilterProxyModel
from qgis.core import QgsApplication, Qgis, QgsProject ,QgsCoordinateReferenceSystem, QgsCoordinateTransform, \
    QgsGeometry, QgsRectangle, QgsMessageLog, QgsRasterLayer, QgsVectorLayer, QgsLayerTreeLayer
from qgis.gui import QgsVertexMarker

import json
import os
import urllib.request, urllib.parse, urllib.error
# Initialize Qt resources from file resources.py
from . import resources_rc
# Import the code for the dialog
from .pdokservicesplugindialog import PdokServicesPluginDialog
from xml.dom.minidom import parse
from .pdokgeocoder import PDOKGeoLocator


class PdokServicesPlugin(object):

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface

        # docked or dialog, defaults to dialog
        # 2018 may: RD: deprecating Docked window, as the content is getting to big anyway
        # if isinstance(QSettings().value("/pdokservicesplugin/docked"), QVariant):
        #     self.docked = QSettings().value("/pdokservicesplugin/docked", QVariant(False))
        # else:
        #     self.docked = QSettings().value("/pdokservicesplugin/docked", False)
        #
        # # Create the dialog and keep reference
        # if "True" == self.docked or "true" == self.docked or True is self.docked:
        #     self.dlg = PdokServicesPluginDockWidget()
        #     self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dlg)
        # else:
        #     self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())

        self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        self.currentLayer = None
        self.SETTINGS_SECTION = '/pdokservicesplugin/'
        self.pointer = None
        self.pdokgeocoder = PDOKGeoLocator(self.iface)
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
        self.runIcon = QIcon(os.path.join(self.plugin_dir, 'icon_add_service.svg'))

        self.run_action = QAction(self.runIcon, "PDOK Services plugin", self.iface.mainWindow())

        self.run_button = QToolButton()
        self.run_button.setMenu(QMenu())
        self.run_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.run_button.setDefaultAction(self.run_action)

        self.servicesLoaded = False
        # connect the action to the run method
        self.run_action.triggered.connect(self.run)
        self.setupfq()

        # Add toolbar button and menu item
        #self.iface.addToolBarIcon(self.action)

        self.toolbar = self.iface.addToolBar("PDOK services plugin")
        self.toolbar.setObjectName("PDOK services plugin")
        #self.toolbar.addAction(self.run_action)
        self.toolbar.addWidget(self.run_button)

        # Set default loading behaviour
        self.default_tree_locations = {
            "wms": 'top',
            "wmts": 'bottom',
            "wfs": 'top',
            "wcs": 'top'
        }

        #self.run_button.menu().addSection('Favorieten')

        self.favourite_1_action = QAction('Favoriet 1', self.iface.mainWindow())
        self.favourite_1_action.setIcon(self.runIcon)
        self.favourite_1_action.triggered.connect(lambda: self.load_favourite(1))
        self.set_favourite_action(self.favourite_1_action, 1)
        self.run_button.menu().addAction(self.favourite_1_action)

        self.favourite_2_action = QAction('Favoriet 2', self.iface.mainWindow())
        self.favourite_2_action.setIcon(self.runIcon)
        self.favourite_2_action.triggered.connect(lambda: self.load_favourite(2))
        self.set_favourite_action(self.favourite_2_action, 2)
        self.run_button.menu().addAction(self.favourite_2_action)

        # TODO :-)
        #self.run_button.menu().addSection('Meest Recent')
        #self.run_button.menu().addSeparator()

        self.toolbarSearch = QLineEdit()
        self.toolbarSearch.setMaximumWidth(200)
        self.toolbarSearch.setAlignment(Qt.AlignLeft)
        self.toolbarSearch.setPlaceholderText("PDOK Locatieserver zoek")
        self.toolbar.addWidget(self.toolbarSearch)
        self.toolbarSearch.returnPressed.connect(self.searchAddressFromToolbar)
        # address/point cleanup
        eraserIcon = QIcon(os.path.join(self.plugin_dir, 'icon_remove_cross.svg'))
        self.clean_action = QAction(eraserIcon, "Cleanup", self.eraseAddress())
        self.toolbar.addAction(self.clean_action)
        self.clean_action.triggered.connect(self.eraseAddress)
        self.clean_action.setEnabled(False)

        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.run_action)

        # about
        self.aboutAction = QAction(self.runIcon, \
                            "About", self.iface.mainWindow())
        self.aboutAction.setWhatsThis("Pdok Services Plugin About")
        self.iface.addPluginToMenu(u"&Pdok Services Plugin", self.aboutAction)

        self.aboutAction.triggered.connect(self.about)
        self.dlg.ui.btnLoadLayer.clicked.connect(lambda: self.loadService('default'))
        self.dlg.ui.btnLoadLayerTop.clicked.connect(lambda: self.loadService('top'))
        self.dlg.ui.btnLoadLayerBottom.clicked.connect(lambda: self.loadService('bottom'))

        self.dlg.geocoderSearch.returnPressed.connect(self.searchAddress)

        self.dlg.geocoderSearch.textEdited.connect(self.searchAddress)
        self.dlg.geocoderSearch.setPlaceholderText("PDOK Locatieserver zoek, bv postcode of postcode huisnummer")

        self.dlg.geocoderResultSearch.textChanged.connect(self.filterGeocoderResult)
        self.dlg.geocoderResultSearch.setPlaceholderText("een of meer zoekwoorden uit resultaat")
        #self.iface.mapCanvas().renderStarting.connect(self.extentsChanged)

        ui = self.dlg.ui
        cbxs = [ui.cbx_gem, ui.cbx_wpl, ui.cbx_weg, ui.cbx_pcd, ui.cbx_adr, ui.cbx_pcl, ui.cbx_hmp]
        # connect all fq checkboxes with suggest, so upon a change in fq filter we re-search
        for cbx in cbxs:
            cbx.stateChanged.connect(self.searchAddress)

        self.run(True)

    # for now hiding the pointer as soon as the extent changes
    #def extentsChanged(self):
    #    self.removePointer()

    # 2021-02 hiding the check JSON: to much hassle
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
                with open(os.path.join(self.plugin_dir, 'pdok.json'), 'w') as outfile:
                    json.dump(pdokjson, outfile)
                msgtxt = "De laatste versie is opgehaald en zal worden gebruikt " + \
                    str(pdokversion) + ' (was ' + myversion +')'
                self.servicesLoaded = False  # reset reading of json
                self.run()
                self.setSettingsValue('pdokversion', pdokversion)
            else:
                msgtxt = "Geen nieuwere versie beschikbaar dan " + str(pdokversion)
        except Exception as e:
            #print e
            msgtxt = "Fout bij ophalen van service info. Netwerk probleem?"
            msglvl = 2  # QgsMessageBar.CRITICAL
        # msg
        if hasattr(self.iface, 'messageBar'):
            self.iface.messageBar().pushMessage("PDOK services update", msgtxt, level=msglvl, duration=10)
        else: # 1.8
            QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin", msgtxt)

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
        self.iface.removePluginMenu("&Pdok Services Plugin", self.run_action)
        self.iface.removePluginMenu("&Pdok Services Plugin", self.aboutAction)
        del self.toolbarSearch
        del self.run_action
        del self.aboutAction

    def showService(self, selectedIndexes):
        if len(selectedIndexes) == 0:
            self.currentLayer = None
            self.dlg.ui.layerInfo.setHtml('')
            self.dlg.ui.comboSelectProj.clear()
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
            title += f' [{style}]'
        servicetitle = self.currentLayer['servicetitle']
        layername = self.currentLayer['layers']
        abstract = self.currentLayer['abstract'] if (not None) else ""
        stype = self.currentLayer['type'].upper()
        minscale =''
        if 'minscale' in self.currentLayer and self.currentLayer['minscale'] != None and self.currentLayer['minscale'] != '':
            minscale = "min. schaal 1:"+self.currentLayer['minscale']
        maxscale = ''
        if 'maxscale' in self.currentLayer and self.currentLayer['maxscale'] != None and self.currentLayer['maxscale'] != '':
            maxscale = "max. schaal 1:"+self.currentLayer['maxscale']
        md_id = self.currentLayer['md_id']
        self.dlg.ui.layerInfo.setText('')
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.btnLoadLayerTop.setEnabled(True)
        self.dlg.ui.btnLoadLayerBottom.setEnabled(True)
        self.dlg.ui.layerInfo.setHtml('<h4>Service: %s</h4><h3>%s</h3><lu><li>%s</li><li>&nbsp;</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>%s</li><li>&nbsp;</li><li>Metadata ID: <a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/%s">%s</a> (link naar het Nationaal Georegister)</li><li>&nbsp;</li></lu>'
                                        % (servicetitle, title, abstract, stype, url, layername, style, minscale, maxscale, md_id, md_id))
        self.dlg.ui.comboSelectProj.clear()
        if stype == "WMS":
            try:
                crs = self.currentLayer['crs']
            except KeyError:
                crs = 'EPSG:28992'
            crs = crs.split(',')
            self.dlg.ui.comboSelectProj.addItems(crs)
            for i in range(len(crs)):
                if crs[i] == 'EPSG:28992':
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)
        if stype=="WMTS":
            tilematrixsets = self.currentLayer['tilematrixsets'].split(',')
            self.dlg.ui.comboSelectProj.addItems(tilematrixsets)
            for i in range(len(tilematrixsets)):
                if tilematrixsets[i].startswith('EPSG:28992'):
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

    def set_favourite_action(self, action, favourite_number):
        if QSettings().contains(f'/pdokservicesplugin/favourite_{favourite_number}'):
            layer = QSettings().value(f'/pdokservicesplugin/favourite_{favourite_number}', None)
            if layer:
                action.setToolTip(layer['title'].capitalize())
                title = layer['title'].capitalize()
                if 'style' in layer:
                    style = layer['style']
                    title += f' [{style}]'
                if 'type' in layer:
                    stype = layer['type'].upper()
                    title += f' ({stype})'
                action.setText(title)
                action.setIcon(self.runIcon)

    def load_favourite(self, favourite_number):
        if QSettings().contains(f'/pdokservicesplugin/favourite_{favourite_number}'):
            layer = QSettings().value(f'/pdokservicesplugin/favourite_{favourite_number}', None)
            if layer and layer in self.pdok['services']:
                self.currentLayer = layer
                self.loadService()
                return
        QMessageBox.warning(self.iface.mainWindow(), "Geen Favoriet aanwezig (of verouderd)...", ( \
            "Maak een Favoriet aan door in de dialoog met services en lagen via het context menu (rechter muisknop) een Favoriet te kiezen..."
            ), QMessageBox.Ok, QMessageBox.Ok)
        self.run()

    def loadService(self, tree_location=None):
        if self.currentLayer == None:
            return
        servicetype = self.currentLayer['type']
        url = self.currentLayer['url']
        # some services have an url with query parameters in it, we have to urlencode those:
        location, query = urllib.parse.splitquery(url)
        url = location
        # RD: 20200820: lijkt of het quoten van de query problemen geeft bij WFS, is/was dit nodig???
        #if query != None and query != '':
        #    url +=('?'+urllib.parse.quote_plus(query))
        title = self.currentLayer['title']
        if 'style' in self.currentLayer:
            style = self.currentLayer['style']
            title += f' [{style}]'
        else:
            style = ''  # == default for this service
        layers = self.currentLayer['layers']
        # mmm, tricky: we take the first one while we can actually want png/gif or jpeg

        if tree_location is None:
            tree_location = self.default_tree_locations[servicetype]
        #print(tree_location)

        if servicetype == "wms":
            imgformat = self.currentLayer['imgformats'].split(',')[0]
            if self.dlg.ui.comboSelectProj.currentIndex() == -1:
                crs = 'EPSG:28992'
            else:
                crs = self.dlg.ui.comboSelectProj.currentText()
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
                    crs) # crs code searchstring
            else:
                # qgis > 1.8
                uri = "crs="+crs+"&layers="+layers+"&styles="+style+"&format="+imgformat+"&url="+url;
                new_layer = QgsRasterLayer(uri, title, "wms")
                self.addLayer(new_layer, tree_location)
        elif servicetype == "wmts":
            if Qgis.QGIS_VERSION_INT < 10900:
                QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+servicetype.upper()+"' \nkan niet worden geladen in deze versie van QGIS.\nMisschien kunt u QGIS 2.0 installeren (die kan het WEL)?\nOf is de laag niet ook beschikbaar als wms of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
                return
            if self.dlg.ui.comboSelectProj.currentIndex() == -1:
                tilematrixset = 'EPSG:28992'
            else:
                tilematrixset = self.dlg.ui.comboSelectProj.currentText()
            imgformat = self.currentLayer['imgformats'].split(',')[0]
            # special case for luchtfoto
            #if layers=="luchtfoto":
            #    # tileMatrixSet=nltilingschema&crs=EPSG:28992&layers=luchtfoto&styles=&format=image/jpeg&url=http://geodata1.nationaalgeoregister.nl/luchtfoto/wmts/1.0.0/WMTSCapabilities.xml
            #    # {u'layers': u'luchtfoto', u'imgformats': u'image/jpeg', u'title': u'PDOK-achtergrond luchtfoto', u'url': u'http://geodata1.nationaalgeoregister.nl/luchtfoto/wms', u'abstract': u'', u'tilematrixsets': u'nltilingschema', u'type': u'wmts'}
            #    uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url
            #else:
            #    uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=&format="+imgformat+"&url="+url;
            #uri = "tileMatrixSet="+tilematrixsets+"&crs=EPSG:28992&layers="+layers+"&styles=default&format="+imgformat+"&url="+url;
            if tilematrixset.startswith('EPSG:'):
                crs=tilematrixset
                i = crs.find(':', 5)
                if i > -1:
                    crs=crs[:i]
            elif tilematrixset.startswith('OGC:1.0'):
                crs='EPSG:3857'
            uri = "tileMatrixSet="+tilematrixset+"&crs="+crs+"&layers="+layers+"&styles=default&format="+imgformat+"&url="+url;
            #print "############ PDOK URI #################"
            #print uri
            new_layer = QgsRasterLayer(uri, title, "wms")
            self.addLayer(new_layer, tree_location)
        elif servicetype == "wfs":
            location, query = urllib.parse.splitquery(url)
            #uri = location+"?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME="+layers+"&SRSNAME=EPSG:28992"
            #uri = location + "?SERVICE=WFS&REQUEST=GetFeature&TYPENAME=" + layers + "&SRSNAME=EPSG:28992"
            # adding a bbox paramater forces QGIS to NOT cache features but retrieve new features all the time
            # QGIS will update the BBOX to the right value
            #uri += "&BBOX=-10000,310000,290000,650000"
            uri = " pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='"+layers+"' url='"+url+"' version='2.0.0' "
            new_layer = QgsVectorLayer(uri, title, "wfs")
            self.addLayer(new_layer, tree_location)
        elif servicetype == "wcs":
            # cache=AlwaysCache&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            uri = ''
            # cache=AlwaysCache
            # cache=PreferNetwork
            # cache=AlwaysNetwork
            # cache=AlwaysNetwork&crs=EPSG:28992&format=GeoTIFF&identifier=ahn25m:ahn25m&url=http://geodata.nationaalgeoregister.nl/ahn25m/wcs
            #uri = "cache=AlwaysNetwork&crs=EPSG:28992&format=image/tiff&version=1.1.1&identifier="+layers+"&url="+url
            # working for ahn1 ahn2 and ahn3: GEOTIFF_FLOAT32
            format = 'GEOTIFF_FLOAT32'
            # working for ahn25m is only image/tiff
            if layers=='ahn25m':
                format = 'image/tiff'
            # we handcrated some wcs layers with 2 different image formats: tiff (RGB) and tiff (float32):
            if 'imgformats' in self.currentLayer:
                format = self.currentLayer['imgformats'].split(',')[0]
            uri = "cache=AlwaysNetwork&crs=EPSG:28992&format="+format+"&identifier=" + layers + "&url=" + url
            #uri = "cache=AlwaysNetwork&crs=EPSG:28992&format="+format+"&version=1.1.2&identifier=" + layers + "&url=" + url
            #uri = "cache=AlwaysNetwork&crs=EPSG:28992&format=image/tiff&version=1.1.2&identifier=" + layers + "&url=" + url
            new_layer = QgsRasterLayer(uri, title, "wcs")
            self.addLayer(new_layer, tree_location)
        else:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+servicetype.upper()+"' \nkan niet worden geladen door de plugin of door QGIS.\nIs het niet beschikbaar als wms, wmts of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
            return

    def addLayer(self, new_layer, tree_location='default'):
        '''Adds a QgsLayer to the project and layer tree.
            tree_location can be 'default', 'top', 'bottom'
        '''
        if tree_location not in ['default', 'top', 'bottom']:
            # raise error ?
            return
        if tree_location == 'default':
            QgsProject.instance().addMapLayer(new_layer, True)
            return
        QgsProject.instance().addMapLayer(new_layer, False)
        new_layer_tree_layer = QgsLayerTreeLayer(new_layer)
        layer_tree = self.iface.layerTreeCanvasBridge().rootGroup()
        if tree_location == 'top':
            layer_tree.insertChildNode(0, new_layer_tree_layer)
        if tree_location == 'bottom':
            layer_tree.insertChildNode(-1, new_layer_tree_layer)

    def filterGeocoderResult(self, string):
        #print "filtering geocoder results: %s" % string
        self.dlg.geocoderResultView.selectRow(0)
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def searchAddressFromToolbar(self):
        self.removePointer()
        self.geocoderSourceModel.clear()
        self.geocode()

    def searchAddress(self):
        self.removePointer()
        #print "search geocoder for: %s" % self.dlg.geocoderSearch.text()
        self.geocoderSourceModel.clear()
        #self.geocode(self.dlg.geocoderSearch.text())
        self.suggest()


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

        # enable possible remote pycharm debugging
        #import pydevd
        #pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)

        # last viewed/selected tab
        if QSettings().contains("/pdokservicesplugin/currenttab"):
            if Qgis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                self.dlg.tabs.widget(QSettings().value("/pdokservicesplugin/currenttab").toInt()[0])
            else:
                self.dlg.tabs.widget(int(QSettings().value("/pdokservicesplugin/currenttab")))

        if self.servicesLoaded == False:
            pdokjson = os.path.join(self.plugin_dir, "pdok.json")
            with open(pdokjson, 'r', encoding='utf-8') as f:
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
                if isinstance(service["layers"], str):
                    self.addSourceRow(service)

            self.dlg.layerSearch.textChanged.connect(self.filterLayers)
            self.dlg.layerSearch.setPlaceholderText("woord uit laagnaam, type of service ")
            self.dlg.servicesView.selectionModel().selectionChanged.connect(self.showService)
            self.dlg.servicesView.doubleClicked.connect(lambda: self.loadService(None)) # Using lambda here to prevent sending signal parameters to the loadService() function

            self.dlg.servicesView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.dlg.servicesView.customContextMenuRequested.connect(self.make_favourite)

            # actually I want to load a service when doubleclicked on header
            # but as I cannot get this to work, let's disable clicking it then
            self.dlg.servicesView.verticalHeader().setSectionsClickable(False)
            self.dlg.servicesView.horizontalHeader().setSectionsClickable(False)

            #self.dlg.geocoderResultView.doubleClicked.connect(self.zoomToAddress)
            self.dlg.geocoderResultView.selectionModel().selectionChanged.connect(self.zoomToAddress)

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

    def make_favourite(self, position):
        menu = QMenu()
        create_fav1_action = menu.addAction("Maak Deze Laag Favoriet 1")
        create_fav2_action = menu.addAction("Maak Deze Laag Favoriet 2")
        action = menu.exec_(self.dlg.servicesView.mapToGlobal(position))
        if action == create_fav1_action:
            QSettings().setValue("/pdokservicesplugin/favourite_1", self.currentLayer)
            self.set_favourite_action(self.favourite_1_action, 1)
        elif action == create_fav2_action:
            QSettings().setValue("/pdokservicesplugin/favourite_2", self.currentLayer)
            self.set_favourite_action(self.favourite_2_action, 2)

    def setupfq(self):
        """
        Setup the fq checkboxes in the gui, by looking into the settings for the
        'pdokservicesplugin/checkedfqs' key, which contains a list of type strings
        like ['weg','adres']
        """
        checked_fqs = self.getSettingsValue('checkedfqs', [])
        #self.info('setup fq: {}'.format(checked_fqs))
        if len(checked_fqs) > 0:  # else there is not saved state... take gui defaults
            self.dlg.ui.cbx_gem.setChecked('gemeente' in checked_fqs)
            self.dlg.ui.cbx_wpl.setChecked('woonplaats' in checked_fqs)
            self.dlg.ui.cbx_weg.setChecked('weg' in checked_fqs)
            self.dlg.ui.cbx_pcd.setChecked('postcode' in checked_fqs)
            self.dlg.ui.cbx_adr.setChecked('adres' in checked_fqs)
            self.dlg.ui.cbx_pcl.setChecked('perceel' in checked_fqs)
            self.dlg.ui.cbx_hmp.setChecked('hectometerpaal' in checked_fqs)

    def createfq(self):
        """
        This creates a fq-string (Filter Query, see https://github.com/PDOK/locatieserver/wiki/Zoekvoorbeelden-Locatieserver)
        Based on the checkboxes in the dialog.
        Defaults to ''
        Example: 'fq=+type:adres+type:gemeente'  (only gemeente AND addresses)
        :return:
        """
        fqlist = []
        if self.dlg.ui.cbx_gem.isChecked():
            fqlist.append('gemeente')
        if self.dlg.ui.cbx_wpl.isChecked():
            fqlist.append('woonplaats')
        if self.dlg.ui.cbx_weg.isChecked():
            fqlist.append('weg')
        if self.dlg.ui.cbx_pcd.isChecked():
            fqlist.append('postcode')
        if self.dlg.ui.cbx_adr.isChecked():
            fqlist.append('adres')
        if self.dlg.ui.cbx_pcl.isChecked():
            fqlist.append('perceel')
        if self.dlg.ui.cbx_hmp.isChecked():
            fqlist.append('hectometerpaal')
        self.setSettingsValue('checkedfqs', fqlist)
        #self.info(self.getSettingsValue('checkedfqs', ['leeg?']))
        fq = ''
        if len(fqlist) > 0:
            fq = '&fq=+type:' + '+type:'.join(fqlist)
        return fq

    def suggest(self):
        self.dlg.ui.lookupinfo.setHtml('')
        search_text = self.dlg.geocoderSearch.text()
        if len(search_text) <= 1:
            # QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ( \
            #     "meer input aub: {}".format(search_text)
            #     ), QMessageBox.Ok, QMessageBox.Ok)
            return
        # QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ( \
        #     "zoeken: {}".format(search_text)
        # ), QMessageBox.Ok, QMessageBox.Ok)
        results = self.pdokgeocoder.suggest(search_text, self.createfq())
        if len(results) == 0:
            # ignore, as we are suggesting, maybe more characters will reveal something...
            return
        for result in results:
            #print address
            adrestekst = QStandardItem("%s" % (result["adrestekst"]))
            adrestekst.setData(result, Qt.UserRole)
            type = QStandardItem("%s" % (result["type"]))
            id = QStandardItem("%s" % (result["id"]))
            score = QStandardItem("%s" % (result["score"]))
            adrestekst.setData(result, Qt.UserRole)
            self.geocoderSourceModel.appendRow([adrestekst, type])
        self.geocoderSourceModel.setHeaderData(0, Qt.Horizontal, "Resultaat")
        self.geocoderSourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.geocoderSourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.dlg.geocoderResultView.resizeColumnsToContents()
        self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)

    def geocode(self):
        self.dlg.geocoderSearch.setText(self.toolbarSearch.text())
        self.suggest()
        if self.dlg.geocoderResultView.model().rowCount()>0:
            self.dlg.geocoderResultView.selectRow(0)
            self.zoomToAddress()
        else:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ( \
                "Niets gevonden.\nProbeer een andere spelling, of alleen postcode/huisnummer?\n\nSelecteer meer (Locatieserver) 'typen' in de PdokServicesPlugin dialoog.\n\nOf gebruik de 'PDOK geocoder'-tab in de PdokServicesPlugin dialoog."
                ), QMessageBox.Ok, QMessageBox.Ok)

    # def geocode(self):
    #     self.dlg.ui.lookupinfo.setHtml('')
    #     search_text = self.toolbarSearch.text()
    #     addresses = self.pdokgeocoder.search(search_text)
    #     if len(addresses) == 0:
    #         QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ( \
    #             "Niets gevonden. Probeer een andere spelling of alleen postcode/huisnummer."
    #             ), QMessageBox.Ok, QMessageBox.Ok)
    #         return
    #     for address in addresses:
    #         #print address
    #         adrestekst = QStandardItem("%s" % (address["adrestekst"]))
    #         adrestekst.setData(address, Qt.UserRole)
    #         straat = QStandardItem("%s" % (address["straat"]))
    #         nummer = QStandardItem("%s" % (address["nummer"]))
    #         postcode = QStandardItem("%s" % (address["postcode"]))
    #         plaats = QStandardItem("%s" % (address["plaats"]))
    #         gemeente = QStandardItem("%s" % (address["gemeente"]))
    #         provincie = QStandardItem("%s" % (address["provincie"]))
    #         self.geocoderSourceModel.appendRow([adrestekst, straat, nummer, postcode, plaats, gemeente, provincie])
    #
    #     self.dlg.geocoderResultView.selectRow(0)
    #     self.zoomToAddress()
    #
    #     self.geocoderSourceModel.setHeaderData(0, Qt.Horizontal, "Resultaat")
    #     self.geocoderSourceModel.setHeaderData(1, Qt.Horizontal, "Straat")
    #     self.geocoderSourceModel.setHeaderData(2, Qt.Horizontal, "Nr")
    #     self.geocoderSourceModel.setHeaderData(3, Qt.Horizontal, "Postcode")
    #     self.geocoderSourceModel.setHeaderData(4, Qt.Horizontal, "Plaats")
    #     self.geocoderSourceModel.setHeaderData(5, Qt.Horizontal, "Gemeente")
    #     self.geocoderSourceModel.setHeaderData(6, Qt.Horizontal, "Provincie")
    #
    #     self.geocoderSourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(3).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(4).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(5).setTextAlignment(Qt.AlignLeft)
    #     self.geocoderSourceModel.horizontalHeaderItem(6).setTextAlignment(Qt.AlignLeft)
    #
    #     self.dlg.geocoderResultView.resizeColumnsToContents()
    #     self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)

    def zoomToAddress(self):
        # get x,y from data of record
        self.removePointer()

        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.UserRole)

        if 'centroide_rd' in data: # free OR lookup service
            geom = QgsGeometry.fromWkt(data['centroide_rd'])
            adrestekst = data['adrestekst']
        else:
            # no centroid yet, probably only object id, retrieve it via lookup service
            id = data['id']
            data = self.pdokgeocoder.lookup(id)
            geom = QgsGeometry.fromWkt(data['centroide_rd'])
            adrestekst = data['adrestekst']
            lookup_data= data['data']
            lis = ''
            for key in lookup_data.keys():
                lis = lis + '<li>{}: {}</li>'.format(key, lookup_data[key])
            self.dlg.ui.lookupinfo.setHtml(
                '<h4>{}</h4><lu>{}</lu>'.format(adrestekst, lis))

        # just always transform from 28992 to mapcanvas crs
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        crs28992 = QgsCoordinateReferenceSystem()
        crs28992.createFromId(28992)
        crsTransform = QgsCoordinateTransform(crs28992, crs, QgsProject.instance())
        z = 1587
        if adrestekst.lower().startswith('adres'):
            z = 794
        elif adrestekst.lower().startswith('perceel'):
            z = 794
        elif adrestekst.lower().startswith('hectometer'):
            z = 1587
        elif adrestekst.lower().startswith('straat'):
            z = 3175
        elif adrestekst.lower().startswith('postcode'):
            z = 6350
        elif adrestekst.lower().startswith('woonplaats'):
            z = 25398
        elif adrestekst.lower().startswith('gemeente'):
            z = 50797
        elif adrestekst.lower().startswith('provincie'):
            z = 812750
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
        self.pointer.setColor(QColor(255, 0, 0))
        self.pointer.setIconSize(10)
        self.pointer.setPenWidth(2)
        self.pointer.setCenter(point)
        self.clean_action.setEnabled(True)

    def removePointer(self):
        if self.pointer is not None and self.pointer.scene() is not None:
            self.iface.mapCanvas().scene().removeItem(self.pointer)
            self.pointer = None
            self.clean_action.setEnabled(False)

    def info(self, msg=""):
        QgsMessageLog.logMessage('{}'.format(msg), 'PDOK-services Plugin', Qgis.Info)
