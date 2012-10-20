# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin
                                 A QGIS plugin


Services url:

http://geodata.nationaalgeoregister.nl/apps/preview/serviceinfo.js.jsp 

from 

http://geodata.nationaalgeoregister.nl/apps/preview/

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
        locale = QSettings().value("locale/userLocale").toString()[0:2]

        if QFileInfo(self.plugin_dir).exists():
            localePath = self.plugin_dir + "/i18n/pdokservicesplugin_" + locale + ".qm"

        if QFileInfo(localePath).exists():
            self.translator = QTranslator()
            self.translator.load(localePath)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


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

    def about(self):
        infoString = QString("Written by Richard Duivenvoorde\nEmail - richard@duif.net\n")
        infoString = infoString.append("Company - http://www.webmapper.net\n")
        infoString = infoString.append("Source: https://github.com/rduivenvoorde/pdokservicesplugin")
        QMessageBox.information(self.iface.mainWindow(), "Pdok Services Plugin About", infoString)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&Pdok Services Plugin",self.action)
        self.iface.removeToolBarIcon(self.action)

    def loadService(self, item):
        #service = self.pdok["services"][i]
        #url = service["url"]
        #name = service["naam"]
        #layers = service["layers"][0]
        #namespace = url.split("/")[3]
        #print self.pdoklayers[i]
        #layer = self.pdoklayers[i]
        layer = item.data(Qt.UserRole).toList()
        url = layer[3].toString()
        namespace = url.split("/")[3]
        title = layer[1].toString()
        name = layer[2].toString()
        if layer[0]=="wms":
            if QGis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                uri = url
                self.iface.addRasterLayer(
                    uri, # service uri
                    title, # name for layer (as seen in QGIS)
                    "wms", # dataprovider key
                    [namespace+':'+name], # array of layername(s) for provider (id's)
                    [""], # array of stylename(s)
                    "image/png", # image format string
                    "EPSG:28992") # crs code string
            else:
                # qgis > 1.8
                uri = "crs=EPSG:28992&layers="+namespace+":"+name+"&styles=&format=image/png&url="+url;
                self.iface.addRasterLayer(uri, title, "wms")
        elif layer[0]=="wmts":
            if QGis.QGIS_VERSION_INT < 10900:
                QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+layer[0].toString()+"' \nkan niet worden geladen in deze versie van QGIS.\nMisschien kunt u de ontwikkelversie van QGIS ernaast installeren (die kan het WEL)?\nOf is de laag niet ook beschikbaar als wms of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
                return
            uri = "tileMatrixSet=EPSG:28992&crs=EPSG:28992&layers="+name+"&styles=&format=image/png&url="+url;
            self.iface.addRasterLayer(uri, title, "wms")
        elif layer[0]=="wfs":
            uri = url+"?SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME="+name+"&SRSNAME=EPSG:28992"
            self.iface.addVectorLayer(uri, title, "WFS")
        else:
            QMessageBox.warning(self.iface.mainWindow(), "PDOK plugin", ("Sorry, dit type layer: '"+layer[0].toString()+"' \nkan niet worden geladen door de plugin of door QGIS.\nIs het niet beschikbaar als wms, wmts of wfs?"), QMessageBox.Ok, QMessageBox.Ok)
            return


    def filterLayers(self, string):
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxyModel.setFilterFixedString(string)

    # run method that performs all the real work
    def run(self):

        if self.servicesLoaded == False:
            #listWidget = QListWidget()
            #f = open('/home/richard/dev/qgis/projects/pdok/json.txt','r')
            pdokjson = os.path.join(os.path.dirname(__file__), ".","pdok.json")
            f = open(pdokjson,'r')
            self.pdok = json.load(f)
            #self.pdoklayers = []
            self.proxyModel = QSortFilterProxyModel()
            self.sourceModel = QStandardItemModel()
            
            self.proxyModel.setSourceModel(self.sourceModel)
            self.dlg.servicesListView.setModel(self.proxyModel)
            i = 0
            for service in self.pdok["services"]:

                #print service["naam"]
                #print "\t"+service["type"]
                #print "\t"+service["url"]
                #print "\t"+str(service["layers"])

                for layer in service["layers"]:
                    #self.pdoklayers.append([ service["type"], service["naam"], layer, service["url"] ])
                    #item = QListWidgetItem("%s  %i %s" % (service["naam"], i+1, layer))
                    #self.dlg.servicesListView.addItem(item)
                    #item = QStandardItem()

                    # you can attache different "data's" to to an QStandarditem
                    # default one is the visible one:
                    item = QStandardItem("%i %s %s" % (i+1, service["naam"], layer))
                    # userrole is a free one:
                    item.setData([ service["type"], service["naam"], layer, service["url"] ], Qt.UserRole)
                    #item = QStandardItem()
                    #item.appendColumn([QStandardItem(service["naam"])])
                    #item.appendColumn([QStandardItem(i+1)])
                    #item.appendColumn([QStandardItem(layer)])
                    self.sourceModel.appendRow( item )
                    i=i+1
            #QObject.connect(self.dlg.servicesListView, SIGNAL("currentRowChanged(int)"), self.loadService)
            QObject.connect(self.dlg.servicesListView, SIGNAL("clicked(QModelIndex)"), self.loadService)
            QObject.connect(self.dlg.layerSearch, SIGNAL("textChanged(QString)"), self.filterLayers)
            self.servicesLoaded = True;

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code)
            pass
