import os
from PyQt5 import QtCore, QtGui, QtWidgets
from qgis.PyQt import uic


import logging
log = logging.getLogger(__name__)

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'pdokservicesplugindialog.ui'))


class PdokServicesPluginDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super(PdokServicesPluginDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.ui = self

        self.servicesView = self.ui.servicesView
        # only select one row at a time:
        self.servicesView.setSelectionMode(self.servicesView.SingleSelection)
        # select whole row if an item is clicked
        self.servicesView.setSelectionBehavior(self.servicesView.SelectRows)
        self.servicesView.setAutoScroll(False)
        self.layerSearch = self.ui.layerSearch
        self.geocoder_search = self.ui.geocoderSearch
        self.geocoderResultSearch = self.ui.geocoderResultSearch
        self.geocoderResultView = self.ui.geocoderResultView
        self.geocoderResultView.setSelectionMode(
            self.geocoderResultView.SingleSelection
        )
        # select whole row if an item is clicked
        self.geocoderResultView.setSelectionBehavior(self.geocoderResultView.SelectRows)
        self.tabs = self.ui.tabWidget
        self.buttonBox.rejected.connect(self.reject)
