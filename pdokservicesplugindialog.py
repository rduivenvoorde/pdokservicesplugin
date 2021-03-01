# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPluginDialog
                                 A QGIS plugin
 bla
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

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import *
from .ui_pdokservicesplugindialog import Ui_PdokServicesPlugin

class PdokServicesPluginDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
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
        self.tabs = self.ui.tabWidget
        self.ui.buttonBox.rejected.connect(self.reject)