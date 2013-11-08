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
import json
import os
import urllib
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from pdokservicesplugindialog import PdokServicesPluginDialog

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



    def about(self):
        infoString = QString("Written by Richard Duivenvoorde\nEmail - richard@duif.net\n")
        infoString = infoString.append("Company - http://www.webmapper.net\n")
        infoString = infoString.append("Source: https://github.com/rduivenvoorde/pdokservicesplugin")
        QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin About", infoString)

    def unload(self):
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
        print url
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
                    imgformat, # image format string
                    "EPSG:28992") # crs code string
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
        itemType.setData( serviceLayer , Qt.UserRole )
        itemLayername = QStandardItem("%s" % (serviceLayer["title"]))
        itemServicetitle = QStandardItem("%s" % (serviceLayer["servicetitle"]))
        itemFilter = QStandardItem("%s %s %s %s" % (serviceLayer["type"], serviceLayer["title"], serviceLayer["servicetitle"], serviceLayer["abstract"]) )
        self.sourceModel.appendRow( [itemServicetitle, itemType, itemLayername, itemFilter] )

    # run method that performs all the real work
    def run(self):
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


            #{"services":[
            #   {"naam":"WMS NHI","url":"http://geodata.nationaalgeoregister.nl/nhi/ows","layers":["dmlinks","dmnodes"],"type":"wms"},
            #   {"naam":"WMS NHI","url":"http://geodata.nationaalgeoregister.nl/nhi/ows","layers":["dmlinks","dmnodes"],"type":"wms"}
            # ]}
            # 
            for service in self.pdok["services"]:
                # service[layer] was an array
                if isinstance(service["layers"], str) or isinstance(service["layers"], unicode):
                    #layer = service["layers"]
                    #self.addSourceRow(service, layer)
                    self.addSourceRow(service)
                #else:
                #    for layer in service["layers"]:
                #        self.addSourceRow(service, layer)
                        ## you can attache different "data's" to to an QStandarditem
                        ## default one is the visible one:
                        #item = QStandardItem("%s %s" % (service["naam"], layer))
                        ## userrole is a free form one:
                        #item.setData( { "type":service["type"], "title":service["naam"], "layername":layer, "url":service["url"], "abstract":service["abstract"] }, Qt.UserRole)
                        #itemType = QStandardItem("%s" % (service["type"].upper()) )
                        #self.sourceModel.appendRow( [itemType, item] )

            self.dlg.layerSearch.textChanged.connect(self.filterLayers)
            self.dlg.servicesView.selectionModel().selectionChanged.connect(self.showService)
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
        #self.dlg.servicesView.resizeColumnToContents(0)
        #self.dlg.servicesView.resizeColumnToContents(1)
        #self.dlg.servicesView.resizeColumnToContents(2)
        self.dlg.servicesView.resizeColumnsToContents()
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code)
            pass

