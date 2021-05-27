# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon

from .locator_filter.pdoklocatieserverfilter import PDOKLocatieserverLocatorFilter



class PdokServicesPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # locator filter
        self.filter = PDOKLocatieserverLocatorFilter(self.iface)
        self.iface.registerLocatorFilter(self.filter)

    def initGui(self):
        add_service_icon = QIcon(os.path.join(self.plugin_dir, 'img', 'icon_add_service.svg'))
        self.add_service_action = QAction(add_service_icon, 'Voeg PDOK-kaartlaag toe', self.iface.mainWindow())
        self.add_service_action.triggered.connect(self.show_add_service_dlg)

        self.toolbar = self.iface.addToolBar("PDOK")
        self.toolbar.addAction(self.add_service_action)


    def unload(self):
        self.add_service_action.triggered.disconnect(self.show_add_service_dlg)
        self.toolbar.removeAction(self.add_service_action)
        del self.add_service_action

        del self.toolbar

        self.iface.deregisterLocatorFilter(self.filter)


    def show_add_service_dlg(self):
        QMessageBox.information(None, 'PDOK Services Plugin', 'Dummy text')
