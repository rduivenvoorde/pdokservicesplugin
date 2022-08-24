import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .browser_mapitem import MapDataItem
from .bookmark_manager import BookmarkManager
from pdokservicesplugin import bookmark_manager

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")


class DataItemProvider(QgsDataItemProvider):
    def __init__(self):
        QgsDataItemProvider.__init__(self)

    def name(self):
        return "PdokProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def createDataItem(self, path, parentItem):
        root = RootCollection()
        sip.transferto(root, None)
        return root


class RootCollection(QgsDataCollectionItem):
    def __init__(self):
        QgsDataCollectionItem.__init__(self, None, "PDOK", "/PDOK")

        self.setIcon(QIcon(os.path.join(IMGS_PATH, "icon_pdok.svg")))

    def createChildren(self):
        children = []

        bookmark_manager = BookmarkManager()
        bookmarks = bookmark_manager.get_bookmarks()

        for bookmark in bookmarks:
            key = f'{bookmark["service_md_id"]}/{bookmark["name"]}'
            md_item = MapDataItem(self, key, bookmark)
            sip.transferto(md_item, self)
            children.append(md_item)

        return children

    def actions(self, parent):
        actions = []

        add_action = QAction(QIcon(), "Add a new map...", parent)
        add_action.triggered.connect(self._open_add_dialog)
        actions.append(add_action)

        configure_action = QAction(QIcon(), "Account...", parent)
        configure_action.triggered.connect(self._open_configure_dialog)
        actions.append(configure_action)

        return actions

    def _open_add_dialog(self):
        add_dialog = AddConnectionDialog()
        add_dialog.exec_()
        self.refreshConnections()

    def _open_configure_dialog(self):
        configure_dialog = ConfigureDialog()
        configure_dialog.exec_()
        self.refreshConnections()
