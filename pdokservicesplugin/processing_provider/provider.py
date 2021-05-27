from qgis.core import QgsProcessingProvider
from .processing_geocoder import PDOKGeocoder
from .processing_reverse_geocoder import PDOKReverseGeocoder
from .processing_ahn3 import PDOKWCSTool

from PyQt5 import QtGui


class Provider(QgsProcessingProvider):
    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(PDOKGeocoder())
        self.addAlgorithm(PDOKReverseGeocoder())
        self.addAlgorithm(PDOKWCSTool())

    def id(self, *args, **kwargs):
        """The ID of your plugin, used for identifying the provider.

        This string should be a unique, short, character only string,
        eg "qgis" or "gdal". This string should not be localised.
        """
        return "pdokservices"

    def name(self, *args, **kwargs):
        """The human friendly name of your plugin in Processing.

        This string should be as short as possible (e.g. "Lastools", not
        "Lastools version 1.0.1 64-bit") and localised.
        """
        return self.tr("PDOK Services Plugin")

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = ":/plugins/pdok_services/icon.png"
        icon = QtGui.QIcon(icon_path)
        return icon
