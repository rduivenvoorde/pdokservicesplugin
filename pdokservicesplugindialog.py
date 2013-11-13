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
from ui_pdokservicesplugin import Ui_PdokServicesPlugin
# create the dialog for zoom to point
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
        self.tabs = self.ui.tabWidget
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("accepted()"), self.accept)
        QtCore.QObject.connect(self.ui.buttonBox, QtCore.SIGNAL("rejected()"), self.reject)
