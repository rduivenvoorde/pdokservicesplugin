# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPluginDialog
                                 A QGIS plugin
 bla
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

from PyQt4 import QtCore, QtGui
from ui_pdokservicesplugindialog import Ui_PdokServicesPlugin
from ui_pdokservicesplugindockwidget import Ui_PDOKservices

# create the dialog for zoom to point
class PdokServicesPluginDockWidget(QtGui.QDockWidget):

    def __init__(self):
        QtGui.QDockWidget.__init__(self)
        # Set up the user interface from Designer.
        self.ui = Ui_PDOKservices()
        self.ui.setupUi(self)
        self.servicesView = self.ui.servicesView
        # only select one row at a time:
        self.servicesView.setSelectionMode(self.servicesView.SingleSelection)
        # select whole row if an item is clicked
        self.servicesView.setSelectionBehavior(self.servicesView.SelectRows)
        self.servicesView.setAutoScroll(False)
        self.layerSearch = self.ui.layerSearch
        self.geocoderSearch = self.ui.geocoderSearch
        self.geocoderResultSearch = self.ui.geocoderResultSearch
        self.geocoderResultView = self.ui.geocoderResultView
        self.geocoderResultView.setSelectionMode(self.geocoderResultView.SingleSelection)
        # select whole row if an item is clicked
        self.geocoderResultView.setSelectionBehavior(self.geocoderResultView.SelectRows)
        self.geocoderSearchBtn = self.ui.geocoderSearchBtn
        self.tabs = self.ui.tabWidget



class PdokServicesPluginDialog(QtGui.QDialog):

    def __init__(self):
        QtGui.QDialog.__init__(self)
        # Set up the user interface from Designer.
        self.ui = Ui_PdokServicesPlugin()
        self.ui.setupUi(self)
        self.servicesView = self.ui.servicesView
        # only select one row at a time:
        self.servicesView.setSelectionMode(self.servicesView.SingleSelection)
        # select whole row if an item is clicked
        self.servicesView.setSelectionBehavior(self.servicesView.SelectRows)
        self.servicesView.setAutoScroll(False)
        self.layerSearch = self.ui.layerSearch
        self.geocoderSearch = self.ui.geocoderSearch
        self.geocoderResultSearch = self.ui.geocoderResultSearch
        self.geocoderResultView = self.ui.geocoderResultView
        self.geocoderResultView.setSelectionMode(self.geocoderResultView.SingleSelection)
        # select whole row if an item is clicked
        self.geocoderResultView.setSelectionBehavior(self.geocoderResultView.SelectRows)
        self.geocoderSearchBtn = self.ui.geocoderSearchBtn
        self.tabs = self.ui.tabWidget
        self.buttonBox = self.ui.buttonBox
        #QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("accepted()"), self.accept)
        #QtCore.QObject.disconnect(self.ui.buttonBox, QtCore.SIGNAL("accepted()"), self.accept)
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("rejected()"), self.reject)
