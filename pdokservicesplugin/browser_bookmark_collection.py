import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .browser_mapitem import MapDataItem
from .bookmark_manager import BookmarkManager
from .constants import PLUGIN_NAME_SHORT

import logging

log = logging.getLogger(__name__)


IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")


class DataItemProvider(QgsDataItemProvider):
    def __init__(self, layer_manager, callback):
        QgsDataItemProvider.__init__(self)
        self._layer_manager = layer_manager
        self._callback = callback

    def name(self):
        return "PdokProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def createDataItem(self, path, parentItem):
        root = RootCollection(self._layer_manager, self._callback)
        sip.transferto(root, None)
        return root
    
    # def on_updatefavs(self):
    # # empty handler
    #     print("Just an empty on_press handler from id=%s" % self.id)
    #     pass

    # def updatefavs(self):
    #     self.on_updatefavs()


class RootCollection(QgsDataCollectionItem):
    def __init__(self, layer_manager,callback):
        QgsDataCollectionItem.__init__(
            self, None, f"{PLUGIN_NAME_SHORT} - Favorieten", "/PDOK"
        )

        self._layer_manager = layer_manager
        self._callback = callback
        self.setIcon(QIcon(os.path.join(IMGS_PATH, "pdok_icon_bookmark.svg")))
        self.bookmark_manager = BookmarkManager()

    def createChildren(self):
        children = []

        
        bookmarks = self.bookmark_manager.get_bookmarks()

        index = 0
        nr_bookmarks = len(bookmarks)
        for bookmark in bookmarks:
            title = self._layer_manager.get_bookmark_title(bookmark)
            md_item = MapDataItem(self, self._layer_manager, title, bookmark, index, self._callback, nr_bookmarks)
            sip.transferto(md_item, self)
            children.append(md_item)
            index += 1

        return children

    def delete_all_action(self):
        self.bookmark_manager.delete_all_bookmarks()
        self.depopulate()
        self._callback()

    def actions(self, parent):
        actions = []
        add_action = QAction(QIcon(), "Delete all bookmarks", parent)
        add_action.triggered.connect(self.delete_all_action)
        log.debug(f"{self.bookmark_manager.get_bookmarks()} - bookmarks")
        if len(self.bookmark_manager.get_bookmarks())<1:
            add_action.setEnabled(False)


        actions.append(add_action)

        return actions