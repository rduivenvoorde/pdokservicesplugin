import os.path

from PyQt5 import QtGui
from qgis.core import QgsProcessingProvider, QgsMessageLog, Qgis

from .processing_geocoder import PDOKGeocoder
from .processing_reverse_geocoder import PDOKReverseGeocoder
from .processing_ahn3 import PDOKWCSTool


class Provider(QgsProcessingProvider):
    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(PDOKGeocoder())
        self.addAlgorithm(PDOKReverseGeocoder())
        self.addAlgorithm(PDOKWCSTool())

    def id(self, *args, **kwargs):
        return "pdokservices"

    def name(self, *args, **kwargs):
        return self.tr("PDOK Services Plugin")

    def icon(self):
        provider_path = os.path.dirname(__file__)
        plugin_path = os.path.dirname(provider_path)
        img_path = os.path.join(plugin_path, "resources", "icon_pdok.svg")

        icon = QtGui.QIcon(img_path)
        return icon
