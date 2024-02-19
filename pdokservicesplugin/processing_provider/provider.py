import os.path

from qgis.PyQt import QtGui
from qgis.core import QgsProcessingProvider

from .processing_geocoder import PDOKGeocoder
from .processing_reverse_geocoder import PDOKReverseGeocoder
from .processing_ahn import PDOKWCSTool

from ..lib.constants import PLUGIN_NAME, PLUGIN_ID


class Provider(QgsProcessingProvider):
    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(PDOKGeocoder())
        self.addAlgorithm(PDOKReverseGeocoder())
        self.addAlgorithm(PDOKWCSTool())

    def id(self, *args, **kwargs):
        return PLUGIN_ID

    def name(self, *args, **kwargs):
        return self.tr(PLUGIN_NAME)

    def icon(self):
        provider_path = os.path.dirname(__file__)
        plugin_path = os.path.dirname(provider_path)
        img_path = os.path.join(plugin_path, "resources", "icon_pdok.svg")

        icon = QtGui.QIcon(img_path)
        return icon
