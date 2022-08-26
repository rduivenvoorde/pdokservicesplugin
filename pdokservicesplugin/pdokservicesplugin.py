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
from qgis.PyQt.QtCore import (
    QSettings,
    QVariant,
    Qt,
    QTimer,
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QLineEdit,
    QAbstractItemView,
    QMessageBox,
    QMenu,
    QToolButton,
    QCompleter,
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
    QgsWkbTypes,
)
from qgis.gui import QgsVertexMarker
import qgis.utils

import textwrap
import json
import os
import urllib.request, urllib.parse, urllib.error
import locale
import re
import logging

from .pdok_layer import LayerManager

from .util import show_error, show_warning, info


log = logging.getLogger(__name__)

# Initialize Qt resources from file resources.py
from . import resources_rc

# Import the code for the dialog
from .pdokservicesplugindialog import PdokServicesPluginDialog

from .processing_provider.provider import Provider

from .lib.http_client import PdokServicesNetworkException

from .locator_filter.pdoklocatieserverfilter import PDOKLocatieserverLocatorFilter

from .lib.locatieserver import (
    suggest_query,
    TypeFilter,
    LsType,
    lookup_object,
    get_lookup_object_url,
    Projection,
)

from .settings_manager import SettingsManager
from .bookmark_manager import BookmarkManager

from .constants import PLUGIN_NAME
from .browser_bookmark_collection import DataItemProvider


class PdokServicesPlugin(object):
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.settings_manager = SettingsManager()
        self.bookmark_manager = BookmarkManager()

        self.layer_manager = LayerManager(iface)

        self.plugin_dir = os.path.dirname(__file__)
        self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())

        self.filter = PDOKLocatieserverLocatorFilter(self.iface)
        self.iface.registerLocatorFilter(self.filter)
        self.pointer = None
        self.geocoder_source_model = None

        self.fq_checkboxes = {
            self.dlg.ui.cbx_gem: LsType.gemeente,
            self.dlg.ui.cbx_wpl: LsType.woonplaats,
            self.dlg.ui.cbx_weg: LsType.weg,
            self.dlg.ui.cbx_pcd: LsType.postcode,
            self.dlg.ui.cbx_adr: LsType.adres,
            self.dlg.ui.cbx_pcl: LsType.perceel,
            self.dlg.ui.cbx_hmp: LsType.hectometerpaal,
        }
        self.fav_actions = []

        self.provider = Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def get_settings_value(self, key, default=""):
        value = self.settings_manager.get_setting(key)
        logging.debug(value)
        if value is None:
            return default
        return value

    def set_settings_value(self, key, value):
        self.settings_manager.store_setting(key, value)

    def initGui(self):
        """Create action that will start plugin configuration

        Function name should be kept as is, since it is required for a QGIS plugin. So does not conform with pep naming convention.
        """
        self.run_icon = QIcon(
            os.path.join(self.plugin_dir, "resources", "icon_add_service.svg")
        )
        self.fav_icon = QIcon(
            os.path.join(self.plugin_dir, "resources", "pdok_icon_bookmark.svg")
        )

        self.del_icon = QIcon(
            os.path.join(self.plugin_dir, "resources", "pdok_icon_delete.svg")
        )

        self.dip = DataItemProvider(self.layer_manager)
        QgsApplication.instance().dataItemProviderRegistry().addProvider(self.dip)

        self.run_action = QAction(self.run_icon, PLUGIN_NAME, self.iface.mainWindow())
        self.run_button = QToolButton()
        self.run_button.setMenu(QMenu())
        self.run_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.run_button.setDefaultAction(self.run_action)

        self.services_loaded = False

        self.run_action.triggered.connect(self.run)
        self.setup_fq_checkboxes()

        # Add toolbar button and menu item
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(PLUGIN_NAME)
        self.toolbar.addWidget(self.run_button)

        self.add_fav_actions_to_toolbar_button()

        self.toolbar_search = QLineEdit()

        def toolbar_search_mouse_event():
            self.toolbar_search.selectAll()
            self.timer_toolbar_search.start()

        self.toolbar_search.mousePressEvent = lambda _: toolbar_search_mouse_event()

        self.toolbar_search.setMaximumWidth(200)
        self.toolbar_search.setAlignment(Qt.AlignLeft)
        self.toolbar_search.setPlaceholderText("Zoek in PDOK Locatieserver")
        self.toolbar.addWidget(self.toolbar_search)
        self.timer_toolbar_search = QTimer()
        self.timer_toolbar_search.setSingleShot(True)
        self.timer_toolbar_search.setInterval(200)
        self.timer_toolbar_search.timeout.connect(self.toolbar_search_get_suggestions)
        self.toolbar_search.textEdited.connect(
            lambda: self.timer_toolbar_search.start()
        )

        eraser_icon = QIcon(
            os.path.join(self.plugin_dir, "resources", "icon_remove_cross.svg")
        )
        self.clean_ls_search_action = QAction(
            eraser_icon, "Cleanup", self.erase_address()
        )

        if not self.show_ls_feature():
            self.toolbar.addAction(self.clean_ls_search_action)

        self.clean_ls_search_action.triggered.connect(self.erase_address)
        self.clean_ls_search_action.setEnabled(False)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.run_action)

        self.about_action = QAction(self.run_icon, "About", self.iface.mainWindow())
        self.about_action.setWhatsThis(f"{PLUGIN_NAME} About")
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.about_action)

        self.about_action.triggered.connect(self.about)

        self.dlg.geocoder_search.returnPressed.connect(
            self.ls_dialog_get_suggestions_and_remove_pointer
        )
        self.timer_geocoder_search = QTimer()
        self.timer_geocoder_search.setSingleShot(True)
        self.timer_geocoder_search.setInterval(200)
        self.timer_geocoder_search.timeout.connect(
            self.ls_dialog_get_suggestions_and_remove_pointer
        )
        self.dlg.geocoder_search.textEdited.connect(
            lambda: self.timer_geocoder_search.start()
        )

        self.dlg.geocoder_search.setPlaceholderText(
            "Zoek in PDOK Locatieserver, bv postcode of postcode huisnummer"
        )

        self.dlg.geocoderResultSearch.textChanged.connect(self.filter_geocoder_result)
        self.dlg.geocoderResultSearch.setPlaceholderText(
            "een of meer zoekwoorden uit resultaat"
        )
        # connect all fq checkboxes with suggest, so upon a change in fq filter we re-search
        for cbx in self.fq_checkboxes.keys():
            cbx.stateChanged.connect(self.ls_dialog_get_suggestions_and_remove_pointer)
        self.run(True)

        # set to hidden when no layer selected
        self.dlg.ui.layer_info.setHidden(True)
        self.dlg.ui.layer_options_groupbox.setHidden(True)

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
            if not self.show_ls_feature():
                self.remove_pointer()
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.run_action)
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self.about_action)
            del self.toolbar

            QgsApplication.instance().dataItemProviderRegistry().removeProvider(
                self.dip
            )
            self.dip = None
            QgsApplication.processingRegistry().removeProvider(self.provider)
        except Exception:
            pass

    def get_dd(self, val, val_string=""):
        md_item_empty = "<dd><em>Niet ingevuld</em></dd>"
        if val:
            if val_string:
                val = val_string
            return f"<dd>{val}</dd>"
        return md_item_empty

    def format_scale_denominator(self, val):
        if val == "" or not val.isnumeric():
            return ""
        scale_formatted = locale.format_string("%d", int(float(val)), grouping=True)
        return f"1:{scale_formatted}"

    def show_layer(self, selectedIndexes):
        if len(selectedIndexes) == 0:
            self.dlg.ui.layer_info.setHtml("")
            self.dlg.ui.comboSelectProj.clear()
            self.dlg.ui.layer_info.setHidden(True)
            self.dlg.ui.layer_options_groupbox.setHidden(True)
            return

        self.dlg.ui.pushButton.clicked.connect(self.toggle_all_fq_checkboxes)
        self.dlg.ui.layer_info.setHidden(False)
        self.dlg.ui.layer_options_groupbox.setHidden(False)

        # needed to scroll To the selected row incase of using the keyboard / arrows
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[0])
        # itemType holds the data (== column 1)
        pdok_layer_config = self.get_selected_pdok_layer_config()
        crs = self.get_crs()

        if "selectedStyle" not in pdok_layer_config:
            selected_style = self.get_selected_style()
            if selected_style is not None:
                pdok_layer_config["selectedStyle"] = selected_style

        def reconnect(signal, newhandler):
            try:
                signal.disconnect()
            except TypeError:
                pass
            signal.connect(newhandler)

        reconnect(
            self.dlg.ui.btnLoadLayer.clicked,
            (
                lambda layer_config, crs: lambda: self.layer_manager.load_layer(
                    layer_config, crs, "default"
                )
            )(pdok_layer_config, crs),
        )
        reconnect(
            self.dlg.ui.btnLoadLayerTop.clicked,
            (
                lambda layer_config, crs: lambda: self.layer_manager.load_layer(
                    layer_config, crs, "top"
                )
            )(pdok_layer_config, crs),
        )
        reconnect(
            self.dlg.ui.btnLoadLayerBottom.clicked,
            (
                lambda layer_config, crs: lambda: self.layer_manager.load_layer(
                    layer_config, crs, "bottom"
                )
            )(pdok_layer_config, crs),
        )
        self.update_layer_panel(pdok_layer_config)

    def update_layer_panel(self, layer):
        url = layer["service_url"]
        title = layer["title"]
        abstract_dd = self.get_dd(layer["abstract"])

        service_title = (
            layer["service_title"]
            if layer["service_title"]
            else "[service title niet ingevuld]"
        )
        layername = layer["name"]
        service_abstract_dd = self.get_dd(layer["service_abstract"])
        stype = layer["service_type"].upper()
        minscale = ""
        if "minscale" in layer:
            minscale = self.format_scale_denominator(layer["minscale"])
        maxscale = ""
        if "maxscale" in layer:
            maxscale = self.format_scale_denominator(layer["maxscale"])
        service_md_id = layer["service_md_id"]
        dataset_md_id = layer["dataset_md_id"]
        self.dlg.ui.layer_info.setText("")
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.btnLoadLayerTop.setEnabled(True)
        self.dlg.ui.btnLoadLayerBottom.setEnabled(True)

        fav = False
        if self.bookmark_manager.pdok_layer_in_bookmarks(layer) != -1:
            fav = True

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
            f'<a title="Bekijk dataset metadata in NGR" href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{dataset_md_id}">{dataset_md_id}</a>',
        )
        fav_string = ""
        fav_title = ""
        if fav:
            fav_string = '<img style="margin:10px" src=":/plugins/pdokservicesplugin/resources/bookmark.png" align="left" />&nbsp;&nbsp;'
            fav_title = "&nbsp;[favoriet]"
        self.dlg.ui.layer_info.setHtml(
            f"""
            <h2>{fav_string}{layername_key} ({stype}) - {title}</h2>
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
            <h3>Service Informatie</h3>
            <dl>
                <dt><b>Service Title</b></dt>
                <dd><a title="Bekijk service capabilities{fav_title}" href="{url}">{service_title}</a></dd>\
                <dt><b>Service Type</b></dt>
                <dd>{stype}</dd>
                <dt><b>Service Abstract</b></dt>
                {service_abstract_dd}
                <dt><b>Service Metadata</b></dt>
                <dd><a title="Bekijk service metadata in NGR"  href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{service_md_id}">{service_md_id}</a></dd>
            </dl>
            """
        )
        self.dlg.ui.comboSelectProj.clear()
        self.dlg.ui.wmsStyleComboBox.clear()

        show_list = {
            self.dlg.ui.comboSelectProj: ["WMS", "WMTS"],
            self.dlg.ui.labelCrs: ["WMS", "WMTS"],
            self.dlg.ui.wmsStyleComboBox: ["WMS"],
            self.dlg.ui.wmsStyleLabel: ["WMS"],
        }

        for ui_el in show_list.keys():
            service_types = show_list[ui_el]
            ui_el.setHidden(not (stype in service_types))

        if stype == "WMS":
            styles = layer["styles"]
            nr_styles = len(styles)
            style_str = "styles" if nr_styles > 1 else "style"
            self.dlg.ui.wmsStyleLabel.setText(
                f"Style ({nr_styles} {style_str} beschikbaar)"
            )
            style_title_names = [
                x["title"] if "title" in x else x["name"] for x in styles
            ]
            self.dlg.ui.wmsStyleComboBox.addItems(style_title_names)
            self.dlg.ui.wmsStyleComboBox.setCurrentIndex(0)
            completer = QCompleter(style_title_names, self.dlg.ui.wmsStyleComboBox)
            completer.setFilterMode(Qt.MatchContains)
            self.dlg.ui.wmsStyleComboBox.setCompleter(completer)
            self.dlg.ui.wmsStyleComboBox.setEnabled(
                nr_styles > 1  # enable if more than one style
            )
            try:
                crs = layer["crs"]
            except KeyError:
                crs = "EPSG:28992"
            crs = crs.split(",")
            self.dlg.ui.comboSelectProj.addItems(crs)
            for i in range(len(crs)):
                if crs[i] == "EPSG:28992":
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

        if stype == "WMTS":
            tilematrixsets = layer["tilematrixsets"].split(",")
            self.dlg.ui.comboSelectProj.addItems(tilematrixsets)
            for i in range(len(tilematrixsets)):
                if tilematrixsets[i].startswith("EPSG:28992"):
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

    def get_selected_style(self):
        indices = self.dlg.servicesView.selectedIndexes()
        layer = indices[1].data(Qt.UserRole) if len(indices) > 2 else None
        if layer is None:
            return
        selected_style_title = self.dlg.ui.wmsStyleComboBox.currentText()
        selected_style = None
        if "styles" in layer:
            selected_style = next(
                (x for x in layer["styles"] if x["title"] == selected_style_title),
                None,
            )
            if selected_style is None:
                # check if selected_style_title is one of the style names, in case the style in the cap doc does not have a title
                # style should have at least a name
                selected_style = next(
                    (x for x in layer["styles"] if x["name"] == selected_style_title),
                    None,
                )
        return selected_style

    def get_crs(self):
        crs = "EPSG:28992"
        if self.dlg.ui.comboSelectProj.currentIndex() != -1:
            crs = self.dlg.ui.comboSelectProj.currentText()
        return crs

    def filter_geocoder_result(self, string):
        self.dlg.geocoderResultView.selectRow(0)
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def toolbar_search_get_suggestions(self):
        def create_model(_suggestions):
            model = QStandardItemModel()
            for s in _suggestions:
                key = s["weergavenaam"]
                it = QStandardItem(key)
                it.setData(s, Qt.UserRole)
                model.appendRow(it)
            return model

        search_text = self.toolbar_search.text()
        if len(search_text) <= 1:
            self.toolbar_search.setCompleter(None)
            return
        results = suggest_query(search_text, self.create_type_filter())
        self.completer = QCompleter()
        self.model = create_model(results)
        self.completer.setModel(self.model)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchContains)
        self.toolbar_search.setCompleter(self.completer)
        self.toolbar_search.show()
        self.completer.complete()
        self.completer.activated.connect(self.on_toolbar_suggest_activated)
        return

    def on_toolbar_suggest_activated(self, suggest_text):
        self.remove_pointer_or_layer()
        items = self.model.findItems(suggest_text)
        if len(items) == 0:  # check should not be necessary
            return
        item = items[0]
        data = item.data(Qt.UserRole)
        lookup_id = data["id"]
        self.lookup_toolbar_search_and_zoom(lookup_id)
        self.dlg.geocoder_search.setText(suggest_text)
        self.fill_ls_dialog_from_toolbar_search()  # run geocode to populate ls dialog

    def ls_dialog_get_suggestions_and_remove_pointer(self):
        self.remove_pointer_or_layer()
        self.geocoder_source_model.clear()
        self.ls_dialog_get_suggestions()

    def ls_dialog_get_suggestions(self):
        try:
            self.dlg.ui.lookupinfo.setHtml("")
            search_text = self.dlg.geocoder_search.text()
            if len(search_text) <= 1:
                return
            results = suggest_query(search_text, self.create_type_filter(), 50)
            if len(results) == 0:
                # ignore, as we are suggesting, maybe more characters will reveal something...
                return
            for result in results:
                adrestekst = QStandardItem(str(result["weergavenaam"]))
                adrestekst.setData(result, Qt.UserRole)
                type = QStandardItem(str(result["type"]))
                adrestekst.setData(result, Qt.UserRole)
                self.geocoder_source_model.appendRow([adrestekst, type])
            self.geocoder_source_model.setHeaderData(0, Qt.Horizontal, "Resultaat")
            self.geocoder_source_model.setHeaderData(1, Qt.Horizontal, "Type")
            self.geocoder_source_model.horizontalHeaderItem(0).setTextAlignment(
                Qt.AlignLeft
            )
            self.dlg.geocoderResultView.resizeColumnsToContents()
            self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)
        except PdokServicesNetworkException as ex:
            title = f"HTTP Request Error"
            message = f"""an error occured while executing HTTP request, error:
                    {str(ex)}
                    """
            show_error(message, title)

    def erase_address(self):
        """
        clean the input and remove the pointer
        """
        self.remove_pointer_or_layer()
        if self.geocoder_source_model is not None:
            self.geocoder_source_model.clear()
        if self.dlg.geocoder_search is not None:
            self.dlg.geocoder_search.clear()
        if self.toolbar_search is not None:
            self.toolbar_search.clear()
            self.toolbar_search.setCompleter(None)

    def filter_layers(self, string):
        # remove selection if one row is selected
        self.dlg.servicesView.selectRow(0)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"
        regexp = QRegExp(string, Qt.CaseInsensitive)
        regexp.setMinimal(True)
        self.proxyModel.setFilterRegExp(regexp)
        self.proxyModel.insertRow

    def add_source_row(self, serviceLayer):
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
        styles_string = ""
        if "styles" in serviceLayer:
            styles_string = " ".join(
                [" ".join(x.values()) for x in serviceLayer["styles"]]
            )

        itemLayername = QStandardItem(str(serviceLayer["title"]))
        itemLayername.setToolTip(
            f'{serviceLayer["service_type"].upper()} - {serviceLayer["service_title"]}'
        )
        # itemFilter is the item used to search filter in. That is why layername is a combi of layername + filter here
        itemFilter = QStandardItem(
            f'{serviceLayer["service_type"]} {layername} {serviceLayer["service_title"]} {serviceLayer["service_abstract"]} {styles_string}'
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

        current_tab = self.settings_manager.get_setting("currenttab")
        if current_tab is not None:
            self.dlg.tabs.widget(int(current_tab))

        if self.services_loaded == False:
            pdokjson = os.path.join(self.plugin_dir, "resources", "layers-pdok.json")
            with open(pdokjson, "r", encoding="utf-8") as f:
                self.layers_pdok = json.load(f)

            self.sourceModel = QStandardItemModel()

            self.styleFilter = QSortFilterProxyModel()
            self.styleFilter.setSourceModel(self.sourceModel)
            self.styleFilter.setFilterKeyColumn(4)

            self.proxyModel = QSortFilterProxyModel()
            self.proxyModel.setSourceModel(self.styleFilter)
            self.proxyModel.setFilterKeyColumn(3)

            self.dlg.servicesView.setModel(self.proxyModel)
            self.dlg.servicesView.setEditTriggers(QAbstractItemView.NoEditTriggers)

            self.geocoderProxyModel = QSortFilterProxyModel()
            self.geocoder_source_model = QStandardItemModel()

            self.geocoderProxyModel.setSourceModel(self.geocoder_source_model)
            self.geocoderProxyModel.setFilterKeyColumn(0)
            self.dlg.geocoderResultView.setModel(self.geocoderProxyModel)
            self.dlg.geocoderResultView.setEditTriggers(
                QAbstractItemView.NoEditTriggers
            )
            for layer in self.layers_pdok:
                if isinstance(layer["name"], str):
                    self.add_source_row(layer)

            self.dlg.layerSearch.textChanged.connect(self.filter_layers)
            self.dlg.servicesView.selectionModel().selectionChanged.connect(
                self.show_layer
            )

            self.dlg.servicesView.doubleClicked.connect(
                lambda: self.layer_manager.load_layer(
                    self.get_selected_pdok_layer_config(),
                    self.get_crs(),
                    "default",
                )
            )  # Using lambda here to prevent sending signal parameters to the loadService() function

            self.dlg.servicesView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.dlg.servicesView.customContextMenuRequested.connect(
                lambda pos: self.make_fav_context_menu(
                    pos, self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)
                )
            )

            # actually I want to load a service when doubleclicked on header
            # but as I cannot get this to work, let's disable clicking it then
            self.dlg.servicesView.verticalHeader().setSectionsClickable(False)
            self.dlg.servicesView.horizontalHeader().setSectionsClickable(False)
            self.dlg.geocoderResultView.selectionModel().selectionChanged.connect(
                self.lookup_dialog_search
            )
            # hide itemFilter column:
            self.dlg.servicesView.hideColumn(3)
            self.services_loaded = True

        self.sourceModel.setHeaderData(2, Qt.Horizontal, "Service")
        self.sourceModel.setHeaderData(1, Qt.Horizontal, "Type")
        self.sourceModel.setHeaderData(0, Qt.Horizontal, "Laagnaam")
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
        self.settings_manager.store_setting("currenttab", self.dlg.tabs.currentIndex())
        self.remove_pointer_or_layer()

    def get_selected_pdok_layer_config(self):
        return self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)

    def setup_fq_checkboxes(self):
        """
        Setup the fq checkboxes in the gui, by looking into the settings for the
        'pdokservicesplugin/checkedfqs' key, which contains a list of type strings
        like ['weg','adres']
        """
        checked_fqs = self.get_settings_value("checkedfqs", [])
        if len(checked_fqs) > 0:  # else there is not saved state... take gui defaults
            for checkbox in self.fq_checkboxes.keys():
                ls_type = self.fq_checkboxes[checkbox]
                checkbox.setChecked(ls_type.name in checked_fqs)

    def toggle_all_fq_checkboxes(self):
        none_checked = all(map(lambda x: not x.isChecked(), self.fq_checkboxes.keys()))
        if none_checked:
            # check_all
            [x.setChecked(True) for x in self.fq_checkboxes.keys()]
        else:
            # uncheck all
            [x.setChecked(False) for x in self.fq_checkboxes.keys()]

    def create_type_filter(self):
        """
        This creates a TypeFilter (Filter Query, see https://github.com/PDOK/locatieserver/wiki/Zoekvoorbeelden-Locatieserver) based on the checkboxes in the dialog. Defaults to []
        """
        filter = TypeFilter([])
        for key in self.fq_checkboxes.keys():
            if key.isChecked():
                filter.add_type(self.fq_checkboxes[key])
        return filter

    def fill_ls_dialog_from_toolbar_search(self):
        self.dlg.geocoder_search.setText(self.toolbar_search.text())
        self.geocoder_source_model.clear()  # otherwise results will be appended in in ls_dialog
        self.ls_dialog_get_suggestions()

    def lookup_toolbar_search_and_zoom(self, lookup_id):
        data = None
        try:
            data = lookup_object(lookup_id, Projection.EPSG_28992)
        except PdokServicesNetworkException as ex:
            title = f"HTTP Request Error"
            message = textwrap.dedent(
                f"""an error occured while executing HTTP request, error:

                {str(ex)}
                """
            )
            show_error(message, title)
        if data is None:
            return
        self.zoom_to_result(data)

    def semver_greater_or_equal_then(self, a, b):
        """check if semver string a is greater or equal then b

        Args:
            a (str): semver string with three components
            b (str): semver string with three components

        Returns:
            bool: indicating semver a is greater or equal to semver b
        """
        regex_pattern = r"^[0-9]+\.[0-9]+\.[0-9]+$"
        if not re.search(regex_pattern, a) or not re.search(regex_pattern, b):
            raise ValueError(
                "input semver_greater_than not conforming to semver string with three components"
            )
        a_list = [int(x) for x in a.split(".")]
        b_list = [int(x) for x in b.split(".")]

        for (a_val, b_val) in zip(a_list, b_list):
            if a_val > b_val:
                return True
        return a_list == b_list

    def show_ls_feature(self):
        """qgis supports "hidden" layers from QGIS version 3.18.0 and higher, see https://gis.stackexchange.com/a/230804. So only show locatie server feature instead of centroid from 3.18.0 and higher.

        Returns:
            bool: boolean indicating whether qgis supports "hidden" layers
        """
        semversion = qgis.utils.Qgis.QGIS_VERSION.split("-")[0]
        if self.semver_greater_or_equal_then(semversion, "3.18.0"):
            return True
        return False

    def zoom_to_result(self, data):
        # just always transform from 28992 to mapcanvas crs
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        crs28992 = QgsCoordinateReferenceSystem.fromEpsgId(28992)
        crsTransform = QgsCoordinateTransform(crs28992, crs, QgsProject.instance())

        adrestekst = "{} - {}".format(data["type"], data["weergavenaam"])
        adrestekst_lower = adrestekst.lower()
        show_ls_feature = self.show_ls_feature()

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

        geom = QgsGeometry.fromWkt(data["wkt_geom"])
        geom.transform(crsTransform)
        geom_type = geom.type()

        geom_type_dict = {
            QgsWkbTypes.PointGeometry: "point",
            QgsWkbTypes.LineGeometry: "linestring",
            QgsWkbTypes.PolygonGeometry: "polygon",
        }
        if geom_type not in geom_type_dict:
            info(
                f"unexpected geomtype return by ls: {geom_type}"
            )  # TODO: better error handling
            return
        if geom_type == QgsWkbTypes.PolygonGeometry:
            # flashGeometries will flash a opaque polygon... let's create a linestring from it so it is less obnoxious
            geom = geom.convertToType(QgsWkbTypes.LineGeometry, destMultipart=True)

        if show_ls_feature:
            self.iface.mapCanvas().flashGeometries(
                [geom],
                startColor=QColor("#ff0000"),
                endColor=QColor("#FFFF00"),
                flashes=10,
            )
        else:
            centroid = QgsGeometry.fromWkt(data["wkt_centroid"])
            centroid.transform(crsTransform)
            center = centroid.asPoint()
            self.set_pointer(center)

        geom_bbox = geom.boundingBox()
        rect = QgsRectangle(geom_bbox)
        rect.scale(1.2)
        self.iface.mapCanvas().zoomToFeatureExtent(rect)
        # for point features it is required to zoom to predefined zoomlevel depending on return type
        if re.match(r"^POINT", data["wkt_geom"]):
            self.iface.mapCanvas().zoomScale(z)
        self.iface.mapCanvas().refresh()

    def fill_lookup_info(self, data):
        lookup_url = get_lookup_object_url(data["id"])
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
            if isinstance(val, str) and re.match(r"^https?://.*$", val):
                val = f'<a href="{val}">{val}</a>'
            if isinstance(val, list):
                val = ", ".join(val)
            result_list = f"{result_list}<li><b>{key}:</b> {val}</li>"
        self.dlg.ui.lookupinfo.setHtml(f"<lu>{result_list}</lu>")

    def remove_pointer_or_layer(self):
        if not self.show_ls_feature():
            self.remove_pointer()

    def lookup_dialog_search(self):
        self.remove_pointer_or_layer()
        if len(self.dlg.geocoderResultView.selectedIndexes()) == 0:
            return
        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.UserRole)
        if (
            not "wkt_centroid" in data
        ):  # this method is called from lsDialog that already has retrieved objects
            lookup_id = data["id"]
            data = None
            try:
                data = lookup_object(lookup_id, Projection.EPSG_28992)
            except PdokServicesNetworkException as ex:
                title = f"HTTP Request Error"
                message = textwrap.dedent(
                    f"""an error occured while executing HTTP request, error:

                    {str(ex)}
                    """
                )
                show_error(message, title)
            if data is None:
                return
        self.fill_lookup_info(data)
        self.zoom_to_result(data)

    def set_pointer(self, point):
        self.remove_pointer()
        self.pointer = QgsVertexMarker(self.iface.mapCanvas())
        self.pointer.setColor(QColor(255, 0, 0))
        self.pointer.setIconSize(10)
        self.pointer.setPenWidth(2)
        self.pointer.setCenter(point)
        self.clean_ls_search_action.setEnabled(True)

    def remove_pointer(self):
        if self.pointer is not None and self.pointer.scene() is not None:
            self.iface.mapCanvas().scene().removeItem(self.pointer)
            self.pointer = None
            self.clean_ls_search_action.setEnabled(False)

    def make_fav_context_menu(self, position, layer):
        menu = QMenu()
        layer = self.dlg.servicesView.selectedIndexes()[1].data(Qt.UserRole)
        log.debug(f"make_fav_context_menu: {layer}")
        if layer:
            fav_index = self.bookmark_manager.pdok_layer_in_bookmarks(layer)
            favs = self.bookmark_manager.get_bookmarks()
            nr_of_favs = len(favs)

            if fav_index != -1:

                up_fav_action = QAction(f"Verplaats favoriet omhoog")
                down_fav_action = QAction(f"Verplaats favoriet omlaag")

                if fav_index == 0:
                    up_fav_action.setEnabled(False)
                if fav_index == (nr_of_favs - 1):
                    down_fav_action.setEnabled(False)

                delete_fav_action = QAction(f"Verwijder deze laag uit favorieten")
                delete_fav_action.setIcon(self.del_icon)

                menu.addAction(up_fav_action)
                menu.addAction(down_fav_action)
                menu.addAction(delete_fav_action)

                action = menu.exec_(self.dlg.servicesView.mapToGlobal(position))
                log.debug(f"make_fav_context_menu: {action}")
                if action == delete_fav_action:
                    # delete layer to favourites with qsettngs
                    # then update favourite context menu
                    self.bookmark_manager.delete_bookmark(layer)
                    self.update_layer_panel(layer)
                    self.add_fav_actions_to_toolbar_button()
                elif action == up_fav_action:
                    self.bookmark_manager.change_bookmark_index(layer, -1)
                    self.add_fav_actions_to_toolbar_button()
                elif action == down_fav_action:
                    self.bookmark_manager.change_bookmark_index(layer, 1)
                    self.add_fav_actions_to_toolbar_button()

            else:
                selected_style = self.get_selected_style()
                if selected_style is not None:
                    layer = {
                        **layer,
                        **{"selectedStyle": selected_style},
                    }

                add_fav_action = QAction(f"Voeg deze laag toe aan favorieten")
                add_fav_action.setIcon(self.fav_icon)
                menu.addAction(add_fav_action)
                action = menu.exec_(self.dlg.servicesView.mapToGlobal(position))
                if action == add_fav_action:
                    # save layer to favourites with qsettngs
                    # then update favourite context menu
                    self.bookmark_manager.save_bookmark(layer)
                    self.update_layer_panel(layer)
                    self.add_fav_actions_to_toolbar_button()

    def add_bookmark_to_map(self, bookmark):
        if not bookmark:
            return
        pdok_layer_config = self.get_layer_in_pdok_layers(bookmark)
        if not pdok_layer_config:
            return
        if "selectedStyle" in bookmark:
            pdok_layer_config["selectedStyle"] = bookmark["selectedStyle"]
        self.layer_manager.load_layer(pdok_layer_config)

    def get_layer_in_pdok_layers(self, lyr):
        """
        returns None if layer not found
        """

        def predicate(x):
            return self.bookmark_manager.bookmarks_equal(lyr, x)

        return next(filter(predicate, self.layers_pdok), None)

    def add_fav_actions_to_toolbar_button(self):
        # first reset existing fav_actions
        for fav_action in self.fav_actions:
            self.run_button.menu().removeAction(fav_action)
        self.fav_actions = []
        fav_layers = self.bookmark_manager.get_bookmarks()

        # add fav_actions
        if len(fav_layers) == 0:
            fav_action = QAction(f"Maak een favoriet aan in het PDOK Services tabblad")
            fav_action.setIcon(self.fav_icon)
            fav_action.setEnabled(False)
            self.run_button.menu().addAction(fav_action)
            self.fav_actions.append(fav_action)
        else:
            for fav_layer in fav_layers:
                if fav_layer:
                    fav_action = QAction()
                    fav_action.setIcon(self.fav_icon)
                    fav_action.triggered.connect(
                        (lambda fav_layer: lambda: self.add_bookmark_to_map(fav_layer))(
                            fav_layer
                        )
                    )  # Double lambda is required in order to freeze argument, otherwise always last favourite is added
                    # see https://stackoverflow.com/a/10452866/1763690

                    fav_action.setToolTip(fav_layer["title"].capitalize())
                    title = fav_layer["title"].capitalize()
                    if "selectedStyle" in fav_layer:
                        style = fav_layer["selectedStyle"]
                        style_title = style["name"]
                        if "title" in style:
                            style_title = style["title"]
                        if style_title:
                            title = f"{title} [{style_title}]"

                    if "service_type" in fav_layer:
                        stype = fav_layer["service_type"].upper()
                        title += f" ({stype})"
                    fav_action.setText(title)
                    self.run_button.menu().addAction(fav_action)
                    self.fav_actions.append(fav_action)
