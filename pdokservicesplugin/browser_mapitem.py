import os


from qgis.core import *
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton
from qgis.gui import QgsMessageViewer
from qgis.utils import iface
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

import logging

log = logging.getLogger(__name__)

from .settings_manager import SettingsManager

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")


class MapDataItem(QgsDataItem):
    def __init__(self, parent, layer_manager, title, pdok_layer_config):
        QgsDataItem.__init__(
            self, QgsDataItem.Custom, parent, title, "/Pdok/layers/" + title
        )

        icon_path = os.path.join(IMGS_PATH, "pdok.svg")
        self.setIcon(QIcon(icon_path))

        self.populate()  # set to treat Item as not-folder-like

        self._parent = parent
        self._layer_manager = layer_manager
        self._title = title
        self._pdok_layer_config = pdok_layer_config

    def handleDoubleClick(self):
        self._add_layer_to_canvas()
        return True

    def actions(self, parent):
        actions = []
        add_raster_action = QAction(QIcon(), "Add layer", parent)
        add_raster_action.triggered.connect(lambda: self._add_layer_to_canvas())
        actions.append(add_raster_action)
        return actions

    def _add_layer_to_canvas(self):
        logging.debug("_add_layer_to_canvas")
        self._layer_manager.load_layer(self._pdok_layer_config)

    def _delete(self):
        # smanager = SettingsManager()
        # custommaps = smanager.get_setting("custommaps")
        # del custommaps[self._name]
        # smanager.store_setting("custommaps", custommaps)
        self.refreshConnections()

    def _remove(self):
        # smanager = SettingsManager()
        # selectedmaps = smanager.get_setting("selectedmaps")
        # selectedmaps.remove(self._name)
        # smanager.store_setting("selectedmaps", selectedmaps)
        self.refreshConnections()
