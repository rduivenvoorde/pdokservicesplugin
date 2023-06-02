import os
from pdokservicesplugin.bookmark_manager import BookmarkManager

from qgis.core import Qgis
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
    def __init__(self, parent, layer_manager, title, pdok_layer_config, index, callback):
        QgsDataItem.__init__(
            self, QgsDataItem.Custom, parent, title, "/Pdok/layers/" + title
        )
        
        self._callback = callback
        icon_path = os.path.join(IMGS_PATH, "pdok.svg")
        self.setIcon(QIcon(icon_path))

        self.populate()  # set to treat Item as not-folder-like
        self._index = index
        self._parent = parent
        self._layer_manager = layer_manager
        self._title = title
        self._pdok_layer_config = pdok_layer_config
        self.setSortKey("_index")
        self.bookmark_manager = BookmarkManager()
        log.error("init MapDataItem")
        logging.error("init mapdataitem")

    def handleDoubleClick(self):
        self._add_layer_to_canvas()
        return True

    def actions(self, parent):
        actions = []
        
        add_bookmark_to_map_action = QAction(QIcon(), "Add bookmark to map", parent)
        add_bookmark_to_map_action.triggered.connect(lambda: self._add_layer_to_canvas())
        actions.append(add_bookmark_to_map_action)

        delete_bookmark_action = QAction(QIcon(), "Delete bookmark", parent)
        delete_bookmark_action.triggered.connect(lambda: self._delete())
        actions.append(delete_bookmark_action)


        move_up_action = QAction(QIcon(), "Move bookmark up", parent)
        move_up_action.triggered.connect(lambda: self._move_up())
        actions.append(move_up_action)

        move_down_action = QAction(QIcon(), "Move bookmark down", parent)
        move_down_action.triggered.connect(lambda: self._move_down())
        actions.append(move_down_action)

        return actions

    def _add_layer_to_canvas(self):
        logging.debug("_add_layer_to_canvas")
        # TODO: check if bookmark is present in layer config
        self._layer_manager.load_layer(self._pdok_layer_config)

    def _move_up(self):
        # QgsMessageLog.logMessage("Your plugin code has been executed correctly", "PdokServicesPlugin", level=Qgis.Info)
        self.bookmark_manager.change_bookmark_index(self._pdok_layer_config, -1)
        self.parent().depopulate() # depopulates also repopulates it seems...
        self._callback()
    
    def _move_down(self):
        # QgsMessageLog.logMessage("Your plugin code has been executed correctly", "PdokServicesPlugin", level=Qgis.Info)
        self.bookmark_manager.change_bookmark_index(self._pdok_layer_config, 1)
        self.parent().depopulate() # depopulates also repopulates it seems...
        self._callback()

    def _delete(self):
        # smanager = SettingsManager()
        # custommaps = smanager.get_setting("custommaps")
        # del custommaps[self._name]
        # smanager.store_setting("custommaps", custommaps)
        log.exception("help")
        self.bookmark_manager.delete_bookmark(self._pdok_layer_config)
        self.parent().refreshConnections()
        self._callback()
        # self.refreshConnections()

    def _remove(self):
        # smanager = SettingsManager()
        # selectedmaps = smanager.get_setting("selectedmaps")
        # selectedmaps.remove(self._name)
        # smanager.store_setting("selectedmaps", selectedmaps)
        self.refreshConnections()
