# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin
                                 A QGIS plugin

                              -------------------
        begin                : 2012-10-11
        copyright            : (C) 2012 by Richard Duivenvoorde
        email                : richard@zuidt.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from copy import deepcopy
from optparse import check_choice
import re
from numpy import isin
from pytz import NonExistentTimeError
from qgis.PyQt.QtCore import (
    QSettings,
    QVariant,
    QFileInfo,
    Qt,
    QTranslator,
    QCoreApplication,
    qVersion,
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QLineEdit,
    QAbstractItemView,
    QMessageBox,
    QMenu,
    QToolButton,
)
from qgis.PyQt.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtCore import QSortFilterProxyModel, QRegExp
from qgis.core import (
    QgsApplication,
    Qgis,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsRectangle,
    QgsMessageLog,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsLayerTreeLayer,
)
from qgis.gui import QgsVertexMarker
import textwrap
import json
import os
import urllib.request, urllib.parse, urllib.error
import locale

# Initialize Qt resources from file resources.py
from . import resources_rc

# Import the code for the dialog
from .pdokservicesplugindialog import PdokServicesPluginDialog

from .processing_provider.provider import Provider

from .lib.http_client import PdokServicesNetworkException

from .locator_filter.pdoklocatieserverfilter import PDOKLocatieserverLocatorFilter

from .lib.constants import PLUGIN_NAME, PLUGIN_ID
from .lib.locatieserver import (
    suggest_query,
    TypeFilter,
    LsType,
    lookup_object,
    get_lookup_object_url,
    Projection,
)


class PdokServicesPlugin(object):
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        # services dialog
        self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())

        # locator filter
        self.filter = PDOKLocatieserverLocatorFilter(self.iface)
        self.iface.registerLocatorFilter(self.filter)

        # initialize plugin directory
        self.currentLayer = None
        self.SETTINGS_SECTION = f"/{PLUGIN_ID}/"
        self.pointer = None
        self.geocoderSourceModel = None

        self.checkbox_dict = {
            self.dlg.ui.cbx_gem: LsType.gemeente,
            self.dlg.ui.cbx_wpl: LsType.woonplaats,
            self.dlg.ui.cbx_weg: LsType.weg,
            self.dlg.ui.cbx_pcd: LsType.postcode,
            self.dlg.ui.cbx_adr: LsType.adres,
            self.dlg.ui.cbx_pcl: LsType.perceel,
            self.dlg.ui.cbx_hmp: LsType.hectometerpaal,
        }

    def getSettingsValue(self, key, default=""):
        if QSettings().contains(f"{self.SETTINGS_SECTION}{key}"):
            key = f"{self.SETTINGS_SECTION}{key}"
            if Qgis.QGIS_VERSION_INT < 10900:  # qgis <= 1.8
                return str(QSettings().value(key).toString())
            else:
                return str(QSettings().value(key))
        else:
            return default

    def setSettingsValue(self, key, value):
        key = f"{self.SETTINGS_SECTION}{key}"
        if Qgis.QGIS_VERSION_INT < 10900:
            # qgis <= 1.8
            QSettings().setValue(key, QVariant(value))
        else:
            QSettings().setValue(key, value)

    def initGui(self):
        # Create action that will start plugin configuration
        self.runIcon = QIcon(
            os.path.join(self.plugin_dir, "resources", "icon_add_service.svg")
        )

        self.run_action = QAction(self.runIcon, PLUGIN_NAME, self.iface.mainWindow())

        self.run_button = QToolButton()
        self.run_button.setMenu(QMenu())
        self.run_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.run_button.setDefaultAction(self.run_action)

        self.servicesLoaded = False
        # connect the action to the run method
        self.run_action.triggered.connect(self.run)
        self.setupfq()

        # Add toolbar button and menu item
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(PLUGIN_NAME)
        self.toolbar.addWidget(self.run_button)

        # Set default loading behaviour
        self.default_tree_locations = {
            "wms": "top",
            "wmts": "bottom",
            "wfs": "top",
            "wcs": "top",
        }

        self.favourite_1_action = QAction("Favoriet 1", self.iface.mainWindow())
        self.favourite_1_action.setIcon(self.runIcon)
        self.favourite_1_action.triggered.connect(lambda: self.load_favourite(1))
        self.set_favourite_action(self.favourite_1_action, 1)
        self.run_button.menu().addAction(self.favourite_1_action)

        self.favourite_2_action = QAction("Favoriet 2", self.iface.mainWindow())
        self.favourite_2_action.setIcon(self.runIcon)
        self.favourite_2_action.triggered.connect(lambda: self.load_favourite(2))
        self.set_favourite_action(self.favourite_2_action, 2)
        self.run_button.menu().addAction(self.favourite_2_action)

        # TODO :-)
        # self.run_button.menu().addSection('Meest Recent')
        # self.run_button.menu().addSeparator()

        self.toolbarSearch = QLineEdit()
        self.toolbarSearch.setMaximumWidth(200)
        self.toolbarSearch.setAlignment(Qt.AlignLeft)
        self.toolbarSearch.setPlaceholderText("PDOK Locatieserver zoek")
        self.toolbar.addWidget(self.toolbarSearch)
        self.toolbarSearch.returnPressed.connect(self.searchAddressFromToolbar)
        # address/point cleanup
        eraserIcon = QIcon(
            os.path.join(self.plugin_dir, "resources", "icon_remove_cross.svg")
        )
        self.clean_action = QAction(eraserIcon, "Cleanup", self.eraseAddress())
        self.toolbar.addAction(self.clean_action)
        self.clean_action.triggered.connect(self.eraseAddress)
        self.clean_action.setEnabled(False)

        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.run_action)

        # about
        self.aboutAction = QAction(self.runIcon, "About", self.iface.mainWindow())
        self.aboutAction.setWhatsThis(f"{PLUGIN_NAME} About")
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.aboutAction)

        self.aboutAction.triggered.connect(self.about)
        self.dlg.ui.btnLoadLayer.clicked.connect(lambda: self.loadService("default"))
        self.dlg.ui.btnLoadLayerTop.clicked.connect(lambda: self.loadService("top"))
        self.dlg.ui.btnLoadLayerBottom.clicked.connect(
            lambda: self.loadService("bottom")
        )

        self.dlg.ui.pushButton.clicked.connect(self.toggleAll)

        self.dlg.geocoderSearch.returnPressed.connect(self.searchAddress)

        self.dlg.geocoderSearch.textEdited.connect(self.searchAddress)
        self.dlg.geocoderSearch.setPlaceholderText(
            "PDOK Locatieserver zoek, bv postcode of postcode huisnummer"
        )

        self.dlg.geocoderResultSearch.textChanged.connect(self.filterGeocoderResult)
        self.dlg.geocoderResultSearch.setPlaceholderText(
            "een of meer zoekwoorden uit resultaat"
        )
        # connect all fq checkboxes with suggest, so upon a change in fq filter we re-search
        for cbx in self.checkbox_dict.keys():
            cbx.stateChanged.connect(self.searchAddress)
        self.run(True)
        self.provider = Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def showAndRaise(self):
        self.dlg.show()
        self.dlg.raise_()
        # also remove the pointer
        self.removePointer()

    def about(self):
        infoString = textwrap.dedent(
            """
            Written by Richard Duivenvoorde
            Email - richard@duif.net
            Company - Zuidt - https://www.zuidt.nl
            Source: https://github.com/rduivenvoorde/pdokservicesplugin
            """
        )
        QMessageBox.information(
            self.iface.mainWindow(), f"{PLUGIN_NAME} - About", infoString
        )

    def unload(self):
        try:  # using try except here because plugin could be unloaded during development: gracefully fail
            self.removePointer()
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.run_action)
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.aboutAction)
            del self.toolbar
        except Exception as e:
            pass

    def get_dd(self, val, val_string=""):
        md_item_empty = "<dd><em>Niet ingevuld</em></dd>"
        if val:
            if val_string:
                val = val_string
            return f"<dd>{val}</dd>"
        return md_item_empty

    def showService(self, selectedIndexes):
        if len(selectedIndexes) == 0:
            self.currentLayer = None
            self.dlg.ui.layerInfo.setHtml("")
            self.dlg.ui.comboSelectProj.clear()
            return
        # needed to scroll To the selected row incase of using the keyboard / arrows
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[0])
        # itemType holds the data (== column 1)
        self.currentLayer = self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)
        if isinstance(self.currentLayer, QVariant):
            self.currentLayer = self.currentLayer.toMap()
            # QGIS 1.8: QVariants
            currentLayer = {}
            for key in list(self.currentLayer.keys()):
                val = self.currentLayer[key]
                currentLayer[str(key)] = str(val.toString())
            self.currentLayer = currentLayer
        url = self.currentLayer["service_url"]
        title = self.currentLayer["title"]
        abstract_dd = self.get_dd(self.currentLayer["abstract"])
        style = ""
        if "style" in self.currentLayer:
            style = self.currentLayer["style"]
            title += f" [{style}]"
        service_title = (
            self.currentLayer["service_title"]
            if self.currentLayer["service_title"]
            else "[service title niet ingevuld]"
        )
        layername = self.currentLayer["name"]
        service_abstract_dd = self.get_dd(self.currentLayer["service_abstract"])
        stype = self.currentLayer["service_type"].upper()
        minscale = ""
        if "minscale" in self.currentLayer and self.currentLayer["minscale"] != "":
            locale.setlocale(locale.LC_ALL, 'nl_NL') # enforce dutch locale, to ensure 1000 seperators is "."
            minscale_formatted = locale.format_string("%d", int(float(self.currentLayer["minscale"])), grouping=True)
            minscale = f'1:{minscale_formatted}'

        maxscale = ""
        if "maxscale" in self.currentLayer and self.currentLayer["maxscale"] != "":
            locale.setlocale(locale.LC_ALL, 'nl_NL') # enforce dutch locale, to ensure 1000 seperators is "."
            maxscale_formatted = locale.format_string("%d", int(float(self.currentLayer["maxscale"])), grouping=True)
            maxscale = f'1:{maxscale_formatted}'

        service_md_id = self.currentLayer["service_md_id"]
        dataset_md_id = self.currentLayer["dataset_md_id"]
        self.dlg.ui.layerInfo.setText("")
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.btnLoadLayerTop.setEnabled(True)
        self.dlg.ui.btnLoadLayerBottom.setEnabled(True)

        maxscale_string = ""
        if maxscale:
            maxscale_string = f"""
            <dt><b>Maxscale</b></dt>
            <dd>{maxscale}</a></dd>
            """
        minscale_string = ""
        if minscale:
            minscale_string = f"""
            <dt><b>Minscale</b></dt>
            <dd>{minscale}</a></dd>
            """

        layername_key_mapping = {
            "WCS": "Coverage",
            "WMS": "Layer",
            "WMTS": "Layer",
            "WFS": "Featuretype",
        }
        layername_key = f"{layername_key_mapping[stype]}"
        dataset_metadata_dd = self.get_dd(
            dataset_md_id,
            f'<a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{dataset_md_id}">{dataset_md_id}</a>',
        )

        self.dlg.ui.layerInfo.setHtml(
            f"""
            <h2><a href="{url}">{service_title} - {stype}</a></h2>
            <dl>
                <dt><b>Service Abstract</b></dt>
                {service_abstract_dd}
                <!--<dt><b>Service Url</b></dt>
                <dd>{url}</dd>-->
                <dt><b>Service Metadata</b></dt>
                <dd><a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{service_md_id}">{service_md_id}</a></dd>
            </dl>
            <h3>{layername_key}: {title}</h3>
            <dl>
                <dt><b>Name</b></dt>
                <dd>{layername}</a></dd>
                <dt><b>Abstract</b></dt>
                {abstract_dd}
                <dt><b>Dataset Metadata</b></dt>
                {dataset_metadata_dd}
                {minscale_string}
                {maxscale_string}
            </dl>
            """
        )
        self.dlg.ui.comboSelectProj.clear()
        if stype == "WMS":
            try:
                crs = self.currentLayer["crs"]
            except KeyError:
                crs = "EPSG:28992"
            crs = crs.split(",")
            self.dlg.ui.comboSelectProj.addItems(crs)
            for i in range(len(crs)):
                if crs[i] == "EPSG:28992":
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)
        if stype == "WMTS":
            tilematrixsets = self.currentLayer["tilematrixsets"].split(",")
            self.dlg.ui.comboSelectProj.addItems(tilematrixsets)
            for i in range(len(tilematrixsets)):
                if tilematrixsets[i].startswith("EPSG:28992"):
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

    def set_favourite_action(self, action, favourite_number):
        if QSettings().contains(f"/{PLUGIN_ID}/favourite_{favourite_number}"):
            layer = QSettings().value(
                f"/{PLUGIN_ID}/favourite_{favourite_number}", None
            )

            if layer:
                action.setToolTip(layer["title"].capitalize())
                title = layer["title"].capitalize()
                if "style" in layer:
                    style = layer["style"]
                    title += f" [{style}]"
                if "service_type" in layer:
                    stype = layer["service_type"].upper()
                    title += f" ({stype})"
                action.setText(title)
                action.setIcon(self.runIcon)

    def show_error(self, message, title="PDOK plugin"):
        message = textwrap.dedent(
            message
        )  # see https://stackoverflow.com/a/1412728/1763690 anders leading whitespace issue
        QMessageBox.critical(
            self.iface.mainWindow(),
            title,
            (message),
            QMessageBox.Ok,
            QMessageBox.Ok,
        )

    def show_warning(self, message, title="PDOK plugin"):
        message = textwrap.dedent(
            message
        )  # see https://stackoverflow.com/a/1412728/1763690 anders leading whitespace issue
        QMessageBox.warning(
            self.iface.mainWindow(),
            title,
            (message),
            QMessageBox.Ok,
            QMessageBox.Ok,
        )

    def get_layer_in_pdok_layers(self, lyr):
        """check for layer equality based on equal
        - service_md_id
        - name (layername)
        - style (in case of WMS layer)
        returns None if layer not found
        """

        def predicate(x):
            if x["service_md_id"] == lyr["service_md_id"] and x["name"] == lyr["name"]:
                # WMS layer with style
                if "style" in x and "style" in lyr:
                    if x["style"] == lyr["style"]:
                        return True
                    else:
                        return False
                # other layer without style (but with matching layername and service_md_id)
                return True
            return False

        return next(filter(predicate, self.layers_pdok), None)

    def load_favourite(self, favourite_number):
        if QSettings().contains(f"/{PLUGIN_ID}/favourite_{favourite_number}"):
            saved_layer = QSettings().value(
                f"/{PLUGIN_ID}/favourite_{favourite_number}", None
            )
            # migration code required for change: https://github.com/rduivenvoorde/pdokservicesplugin/commit/a5700dace54250b8f18229939907c3cab39f5297
            # which changed the schema of the layer config json file
            migrate_fav = False
            if "md_id" in saved_layer:
                saved_layer["service_md_id"] = saved_layer["md_id"]
                migrate_fav = True
            if "layers" in saved_layer:
                saved_layer["name"] = saved_layer["layers"]
                migrate_fav = True
            layer = self.get_layer_in_pdok_layers(saved_layer)
            if migrate_fav:
                QSettings().setValue(
                    f"/{PLUGIN_ID}/favourite_{favourite_number}", layer
                )
            if layer:
                self.currentLayer = layer
                self.loadService()
                return
        self.show_warning(
            "Maak een Favoriet aan door in de dialoog met services en lagen via het context menu (rechter muisknop) een Favoriet te kiezen...",
            "Geen Favoriet aanwezig (of verouderd)...",
        )
        self.run()

    def quote_wmts_url(self, url):
        """
        Quoten wmts url is nodig omdat qgis de query param `SERVICE=WMS` erachter plakt als je de wmts url niet quote.
        Dit vermoedelijk omdat de wmts laag wordt toegevoegd mbv de wms provider: `return QgsRasterLayer(uri, title, "wms")`.
        """
        parse_result = urllib.parse.urlparse(url)
        location = f"{parse_result.scheme}://{parse_result.netloc}/{parse_result.path}"
        query = parse_result.query
        query_escaped_quoted = urllib.parse.quote_plus(query)
        url = f"{location}?{query_escaped_quoted}"
        return url

    def create_new_layer(self):
        servicetype = self.currentLayer["service_type"]
        title = self.currentLayer["title"]
        layername = self.currentLayer["name"]
        url = self.currentLayer["service_url"]

        if servicetype == "wms":
            imgformat = self.currentLayer["imgformats"].split(",")[0]
            if self.dlg.ui.comboSelectProj.currentIndex() == -1:
                crs = "EPSG:28992"
            else:
                crs = self.dlg.ui.comboSelectProj.currentText()
            if Qgis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                uri = url
                self.iface.addRasterLayer(
                    uri,
                    title,
                    "wms",
                    [layername],
                    [""],
                    imgformat,
                    crs,
                )
            else:
                # qgis > 1.8
                style = ""
                if "style" in self.currentLayer:
                    style = self.currentLayer["style"]
                    title += f" [{style}]"
                uri = f"crs={crs}&layers={layername}&styles={style}&format={imgformat}&url={url}"
                return QgsRasterLayer(uri, title, "wms")
        elif servicetype == "wmts":
            if Qgis.QGIS_VERSION_INT < 10900:
                self.show_warning(
                    f"""Sorry, dit type layer: '{servicetype.upper()}'
                    kan niet worden geladen in deze versie van QGIS.
                    Misschien kunt u QGIS 2.0 installeren (die kan het WEL)?
                    Of is de laag niet ook beschikbaar als wms of wfs?"""
                )
                return None
            url = self.quote_wmts_url(url)
            if self.dlg.ui.comboSelectProj.currentIndex() == -1:
                tilematrixset = "EPSG:28992"
            else:
                tilematrixset = self.dlg.ui.comboSelectProj.currentText()
            imgformat = self.currentLayer["imgformats"].split(",")[0]
            if tilematrixset.startswith("EPSG:"):
                crs = tilematrixset
                i = crs.find(":", 5)
                if i > -1:
                    crs = crs[:i]
            elif tilematrixset.startswith("OGC:1.0"):
                crs = "EPSG:3857"
            uri = f"tileMatrixSet={tilematrixset}&crs={crs}&layers={layername}&styles=default&format={imgformat}&url={url}"
            return QgsRasterLayer(
                uri, title, "wms"
            )  # `wms` is correct, zie ook quote_wmts_url
        elif servicetype == "wfs":
            uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
            return QgsVectorLayer(uri, title, "wfs")
        elif servicetype == "wcs":
            format = "GEOTIFF_FLOAT32"
            # we handcrafted some wcs layers with 2 different image formats: tiff (RGB) and tiff (float32):
            if "imgformats" in self.currentLayer:
                format = self.currentLayer["imgformats"].split(",")[0]
            uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url}"
            return QgsRasterLayer(uri, title, "wcs")
        else:
            self.show_warning(
                f"""Sorry, dit type layer: '{servicetype.upper()}'
                kan niet worden geladen door de plugin of door QGIS.
                Is het niet beschikbaar als wms, wmts of wfs?
                """
            )
            return

    def loadService(self, tree_location=None):
        if self.currentLayer == None:
            return
        servicetype = self.currentLayer["service_type"]
        if tree_location is None:
            tree_location = self.default_tree_locations[servicetype]
        new_layer = self.create_new_layer()
        if new_layer is None:
            return
        self.addLayer(new_layer, tree_location)

    def addLayer(self, new_layer, tree_location="default"):
        """Adds a QgsLayer to the project and layer tree.
        tree_location can be 'default', 'top', 'bottom'
        """
        if tree_location not in ["default", "top", "bottom"]:
            # TODO: proper error handling
            return
        if tree_location == "default":
            QgsProject.instance().addMapLayer(new_layer, True)
            return
        QgsProject.instance().addMapLayer(new_layer, False)
        new_layer_tree_layer = QgsLayerTreeLayer(new_layer)
        layer_tree = self.iface.layerTreeCanvasBridge().rootGroup()
        if tree_location == "top":
            layer_tree.insertChildNode(0, new_layer_tree_layer)
        if tree_location == "bottom":
            layer_tree.insertChildNode(-1, new_layer_tree_layer)

    def filterGeocoderResult(self, string):
        self.dlg.geocoderResultView.selectRow(0)
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def searchAddressFromToolbar(self):
        self.removePointer()
        self.geocoderSourceModel.clear()
        try:
            self.geocode()
        except PdokServicesNetworkException as ex:
            title = f"{PLUGIN_NAME} - HTTP Request Error"
            message = f"""
            an error occured while executing HTTP request, error:

            {str(ex)}
            """
            self.show_error(message, title)

    def searchAddress(self):
        self.removePointer()
        self.geocoderSourceModel.clear()
        try:
            self.suggest()
        except PdokServicesNetworkException as ex:
            title = f"{PLUGIN_NAME} - HTTP Request Error"
            message = f"""an error occured while executing HTTP request, error:
                    {str(ex)}
                    """
            self.show_error(message, title)

    def eraseAddress(self):
        """
        clean the input and remove the pointer
        """
        self.removePointer()
        if self.geocoderSourceModel is not None:
            self.geocoderSourceModel.clear()
        if self.dlg.geocoderSearch is not None:
            self.dlg.geocoderSearch.clear()
        if self.toolbarSearch is not None:
            self.toolbarSearch.clear()

    def filterLayers(self, string):
        # remove selection if one row is selected
        self.dlg.servicesView.selectRow(0)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"
        self.info(f"zoektekst: {string}")
        regexp = QRegExp(string, Qt.CaseInsensitive)
        regexp.setMinimal(True)
        self.proxyModel.setFilterRegExp(regexp)

    def addSourceRow(self, serviceLayer):
        # you can attache different "data's" to to an QStandarditem
        # default one is the visible one:
        itemType = QStandardItem(str(serviceLayer["service_type"].upper()))
        # userrole is a free form one:
        # only attach the data to the first item
        # service layer = a dict/object with all props of the layer
        itemType.setData(serviceLayer, Qt.UserRole)
        itemType.setToolTip(
            f'{serviceLayer["service_type"].upper()} - {serviceLayer["title"]}'
        )
        # only wms services have styles (sometimes)
        layername = serviceLayer["title"]
        if "style" in serviceLayer:
            itemLayername = QStandardItem(
                f'{serviceLayer["title"]} [{serviceLayer["style"]}]'
            )
            layername = f'{serviceLayer["title"]} [{serviceLayer["style"]}]'
        else:
            itemLayername = QStandardItem(str(serviceLayer["title"]))
        itemLayername.setToolTip(
            f'{serviceLayer["service_type"].upper()} - {serviceLayer["service_title"]}'
        )
        # itemFilter is the item used to search filter in. That is why layername is a combi of layername + filter here
        itemFilter = QStandardItem(
            f'{serviceLayer["service_type"]} {layername} {serviceLayer["service_title"]} {serviceLayer["service_abstract"]}'
        )
        itemServicetitle = QStandardItem(str(serviceLayer["service_title"]))
        itemServicetitle.setToolTip(
            f'{serviceLayer["service_type"].upper()} - {serviceLayer["title"]}'
        )
        self.sourceModel.appendRow(
            [itemLayername, itemType, itemServicetitle, itemFilter]
        )

    def run(self, hiddenDialog=False):
        """
        run method that performs all the real work
        """
        # enable possible remote pycharm debugging
        # import pydevd
        # pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)

        # last viewed/selected tab
        if QSettings().contains(f"/{PLUGIN_ID}/currenttab"):
            if Qgis.QGIS_VERSION_INT < 10900:
                # qgis <= 1.8
                self.dlg.tabs.widget(
                    QSettings().value(f"/{PLUGIN_ID}/currenttab").toInt()[0]
                )
            else:
                self.dlg.tabs.widget(int(QSettings().value(f"/{PLUGIN_ID}/currenttab")))

        if self.servicesLoaded == False:
            pdokjson = os.path.join(self.plugin_dir, "resources", "layers-pdok.json")
            with open(pdokjson, "r", encoding="utf-8") as f:
                self.layers_pdok = json.load(f)
            self.proxyModel = QSortFilterProxyModel()
            self.sourceModel = QStandardItemModel()
            self.proxyModel.setSourceModel(self.sourceModel)
            self.proxyModel.setFilterKeyColumn(3)
            self.dlg.servicesView.setModel(self.proxyModel)
            self.dlg.servicesView.setEditTriggers(QAbstractItemView.NoEditTriggers)

            self.geocoderProxyModel = QSortFilterProxyModel()
            self.geocoderSourceModel = QStandardItemModel()

            self.geocoderProxyModel.setSourceModel(self.geocoderSourceModel)
            self.geocoderProxyModel.setFilterKeyColumn(0)
            self.dlg.geocoderResultView.setModel(self.geocoderProxyModel)
            self.dlg.geocoderResultView.setEditTriggers(
                QAbstractItemView.NoEditTriggers
            )
            for layer in self.layers_pdok:
                if isinstance(layer["name"], str):
                    self.addSourceRow(layer)

            self.dlg.layerSearch.textChanged.connect(self.filterLayers)
            self.dlg.servicesView.selectionModel().selectionChanged.connect(
                self.showService
            )
            self.dlg.servicesView.doubleClicked.connect(
                lambda: self.loadService(None)
            )  # Using lambda here to prevent sending signal parameters to the loadService() function

            self.dlg.servicesView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.dlg.servicesView.customContextMenuRequested.connect(
                self.make_favourite
            )

            # actually I want to load a service when doubleclicked on header
            # but as I cannot get this to work, let's disable clicking it then
            self.dlg.servicesView.verticalHeader().setSectionsClickable(False)
            self.dlg.servicesView.horizontalHeader().setSectionsClickable(False)
            self.dlg.geocoderResultView.selectionModel().selectionChanged.connect(
                self.zoomToAddress
            )
            # hide itemFilter column:
            self.dlg.servicesView.hideColumn(3)
            self.servicesLoaded = True

        self.sourceModel.setHeaderData(2, Qt.Horizontal, "Service")
        self.sourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.sourceModel.setHeaderData(0, Qt.Horizontal, "Laagnaam [style]")
        self.sourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft)
        self.sourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.dlg.servicesView.setColumnWidth(
            0, 300
        )  # set name to 300px (there are some huge layernames)
        self.dlg.servicesView.horizontalHeader().setStretchLastSection(True)
        # show the dialog ?
        if not hiddenDialog:
            self.dlg.show()
        # Run the dialog event loop
        # result = self.dlg.exec_()
        if Qgis.QGIS_VERSION_INT < 10900:
            # qgis <= 1.8
            QSettings().setValue(
                f"/{PLUGIN_ID}/currenttab", QVariant(self.dlg.tabs.currentIndex())
            )
        else:
            QSettings().setValue(
                f"/{PLUGIN_ID}/currenttab", self.dlg.tabs.currentIndex()
            )
        self.removePointer()

    def make_favourite(self, position):
        menu = QMenu()
        create_fav1_action = menu.addAction("Maak Deze Laag Favoriet 1")
        create_fav2_action = menu.addAction("Maak Deze Laag Favoriet 2")
        action = menu.exec_(self.dlg.servicesView.mapToGlobal(position))
        if action == create_fav1_action:
            QSettings().setValue(f"/{PLUGIN_ID}/favourite_1", self.currentLayer)
            self.set_favourite_action(self.favourite_1_action, 1)
        elif action == create_fav2_action:
            QSettings().setValue(f"/{PLUGIN_ID}/favourite_2", self.currentLayer)
            self.set_favourite_action(self.favourite_2_action, 2)

    def setupfq(self):
        """
        Setup the fq checkboxes in the gui, by looking into the settings for the
        'pdokservicesplugin/checkedfqs' key, which contains a list of type strings
        like ['weg','adres']
        """
        checked_fqs = self.getSettingsValue("checkedfqs", [])
        if len(checked_fqs) > 0:  # else there is not saved state... take gui defaults
            for checkbox in self.checkbox_dict.keys():
                ls_type = self.checkbox_dict[checkbox]
                checkbox.setChecked(ls_type.name in checked_fqs)

    def toggleAll(self):
        none_checked = all(map(lambda x: not x.isChecked(), self.checkbox_dict.keys()))
        if none_checked:
            # check_all
            [x.setChecked(True) for x in self.checkbox_dict.keys()]
        else:
            # uncheck all
            [x.setChecked(False) for x in self.checkbox_dict.keys()]

    def create_type_filter(self):
        """
        This creates a TypeFilter (Filter Query, see https://github.com/PDOK/locatieserver/wiki/Zoekvoorbeelden-Locatieserver) based on the checkboxes in the dialog. Defaults to []
        """
        # TODO: share checkbox dict as class field for other methods doing stuff with the checkboxes

        filter = TypeFilter([])
        for key in self.checkbox_dict.keys():
            if key.isChecked():
                filter.add_type(self.checkbox_dict[key])
        return filter

    def suggest(self):
        self.dlg.ui.lookupinfo.setHtml("")
        search_text = self.dlg.geocoderSearch.text()
        if len(search_text) <= 1:
            return
        results = suggest_query(search_text, self.create_type_filter())
        if len(results) == 0:
            # ignore, as we are suggesting, maybe more characters will reveal something...
            return
        for result in results:
            adrestekst = QStandardItem(str(result["weergavenaam"]))
            adrestekst.setData(result, Qt.UserRole)
            type = QStandardItem(str(result["type"]))
            id = QStandardItem(str(result["id"]))
            score = QStandardItem(str(result["score"]))
            adrestekst.setData(result, Qt.UserRole)
            self.geocoderSourceModel.appendRow([adrestekst, type])
        self.geocoderSourceModel.setHeaderData(0, Qt.Horizontal, "Resultaat")
        self.geocoderSourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.geocoderSourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft)
        self.dlg.geocoderResultView.resizeColumnsToContents()
        self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)

    def geocode(self):
        self.dlg.geocoderSearch.setText(self.toolbarSearch.text())
        self.suggest()
        if self.dlg.geocoderResultView.model().rowCount() > 0:
            self.dlg.geocoderResultView.selectRow(0)
            self.zoomToAddress()
        else:
            self.show_warning(
                f"""
                Niets gevonden.

                Probeer een andere spelling, of alleen postcode/huisnummer?

                Selecteer meer (Locatieserver) 'types' in de  dialoog.

                Of gebruik de 'PDOK geocoder'-tab in de {PLUGIN_NAME} dialoog.
                """
            )

    def zoomToAddress(self):
        self.removePointer()
        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.UserRole)
        if "wkt_centroid" in data:  # free OR lookup service
            centroid = QgsGeometry.fromWkt(data["wkt_centroid"])
            adrestekst = data["weergavenaam"]
        else:
            # no centroid yet, probably only object id, retrieve it via lookup service
            id = data["id"]
            data = None
            try:
                data = lookup_object(id, Projection.EPSG_28992)
                lookup_url = get_lookup_object_url(id)
            except PdokServicesNetworkException as ex:
                title = f"{PLUGIN_NAME} - HTTP Request Error"
                message = textwrap.dedent(
                    f"""an error occured while executing HTTP request, error:

                    {str(ex)}
                    """
                )
                self.show_error(message, title)
            if data is None:
                return
            adrestekst = "{} - {}".format(data["type"], data["weergavenaam"])
            data["lookup_url"] = lookup_url
            # generate lookupinfo list
            data_sorted = {}

            # lambda function to ensure values starting with _ are place last
            # see https://stackoverflow.com/a/18875168/1763690
            for key in sorted(data.keys(), key=lambda d: d.lower().replace("_", "{")):
                data_sorted[key] = data[key]

            result_list = ""
            for key in data_sorted.keys():
                if key in ["wkt_centroid", "wkt_geom"]:  # skip geom fields
                    continue
                val = data_sorted[key]
                if isinstance(val, str) and re.match(r"^https?:\/\/.*$", val):
                    val = f'<a href="{val}">{val}</a>'
                if isinstance(val, list):
                    val = ", ".join(val)
                result_list = f"{result_list}<li><b>{key}:</b> {val}</li>"

            self.dlg.ui.lookupinfo.setHtml(f"<lu>{result_list}</lu>")

            # just always transform from 28992 to mapcanvas crs
            crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            crs28992 = QgsCoordinateReferenceSystem.fromEpsgId(28992)
            crsTransform = QgsCoordinateTransform(crs28992, crs, QgsProject.instance())
            adrestekst_lower = adrestekst.lower()

            zoom_dict = {
                "adres": 794,
                "perceel": 794,
                "hectometer": 1587,
                "weg": 3175,
                "postcode": 6350,
                "woonplaats": 25398,
                "gemeente": 50797,
                "provincie": 812750,
            }
            z = 1587
            for z_type in zoom_dict.keys():
                if adrestekst_lower.startswith(
                    z_type
                ):  # maybe find better way to infer return type?
                    z = zoom_dict[z_type]

            centroid = QgsGeometry.fromWkt(data["wkt_centroid"])
            centroid.transform(crsTransform)
            center = centroid.asPoint()
            self.setPointer(center)

            geom = QgsGeometry.fromWkt(data["wkt_geom"])
            geom.transform(crsTransform)
            geom_bbox = geom.boundingBox()
            rect = QgsRectangle(geom_bbox)
            self.iface.mapCanvas().zoomToFeatureExtent(rect)

            # zoom to a point feature is actually setting a point rectangle and then zoom
            if re.match(r"^POINT", data["wkt_geom"]):
                self.iface.mapCanvas().zoomScale(z)

            self.iface.mapCanvas().refresh()

    def setPointer(self, point):
        self.removePointer()
        self.pointer = QgsVertexMarker(self.iface.mapCanvas())
        self.pointer.setColor(QColor(255, 0, 0))
        self.pointer.setIconSize(10)
        self.pointer.setPenWidth(2)
        self.pointer.setCenter(point)
        self.clean_action.setEnabled(True)

    def removePointer(self):
        if self.pointer is not None and self.pointer.scene() is not None:
            self.iface.mapCanvas().scene().removeItem(self.pointer)
            self.pointer = None
            self.clean_action.setEnabled(False)

    def info(self, msg=""):
        QgsMessageLog.logMessage("{}".format(msg), "PDOK-services Plugin", Qgis.Info)
