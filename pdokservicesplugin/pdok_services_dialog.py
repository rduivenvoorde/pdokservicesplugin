# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtWidgets import (
    QDialog
)
from qgis.PyQt import uic


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pdok_services_dialog.ui'))

class PdokServicesDialog(QDialog, FORM_CLASS):

    def __init__(self, plugin, parent=None):

        super(PdokServicesDialog, self).__init__(parent)
        self.setupUi(self)

        self.plugin = plugin

        # only select one row at a time:
        self.servicesView.setSelectionMode(self.servicesView.SingleSelection)
        self.servicesView.setSelectionBehavior(self.servicesView.SelectRows)
        self.servicesView.setAutoScroll(False)

        # select whole row if an item is clicked
        self.geocoderResultView.setSelectionMode(self.geocoderResultView.SingleSelection)
        self.geocoderResultView.setSelectionBehavior(self.geocoderResultView.SelectRows)

        self.tabs = self.tabWidget # TODO: why changing this name??

        # close button
        self.buttonBox.rejected.connect(self.reject)
