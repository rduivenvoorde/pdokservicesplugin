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
    QgsVectorTileLayer,
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

log = logging.getLogger(__name__)

# Initialize Qt resources from file resources.py
from . import resources_rc

# Import the code for the dialog
from .pdokservicesplugindialog import PdokServicesPluginDialog

from .processing_provider.provider import Provider

from .lib.http_client import PdokServicesNetworkException

from .locator_filter.pdoklocatieserverfilter import PDOKLocatieserverLocatorFilter

from .lib.constants import PLUGIN_NAME, PLUGIN_ID, DEFAULT_NR_FAVS, SETTINGS_SECTIONS
from .lib.locatieserver import (
    suggest_query,
    TypeFilter,
    LsType,
    lookup_object,
    get_lookup_object_url,
    Projection,
)


# enable possible remote pycharm debugging
#import pydevd
#pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)


class PdokServicesPlugin(object):
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dlg = PdokServicesPluginDialog(parent=self.iface.mainWindow())

        self.filter = PDOKLocatieserverLocatorFilter(self.iface)
        self.iface.registerLocatorFilter(self.filter)

        self.current_layer = None
        self.SETTINGS_SECTION = SETTINGS_SECTIONS
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
        if QSettings().contains(f"{self.SETTINGS_SECTION}{key}"):
            key = f"{self.SETTINGS_SECTION}{key}"
            return str(QSettings().value(key))
        else:
            return default

    def set_settings_value(self, key, value):
        key = f"{self.SETTINGS_SECTION}{key}"
        QSettings().setValue(key, QVariant(value))

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

        # Set default layer loading behaviour
        self.default_tree_locations = {
            "wms": "top",
            "wmts": "bottom",
            "wfs": "top",
            "wcs": "top",
            "api features": "top",
            "api tiles": "bottom",
        }

        # Set default layer loading behaviour
        self.service_type_mapping = {
            "wms": "WMS",
            "wmts": "WMTS",
            "wfs": "WFS",
            "wcs": "WCS",
            "api features": "OGC API - features",
            "api tiles": "OGC API - tiles",
        }

        self.add_fav_actions_to_toolbar_button()

        self.toolbar_search = QLineEdit()

        def toolbar_search_mouse_event():
            self.toolbar_search.selectAll()
            self.timer_toolbar_search.start()

        self.toolbar_search.mousePressEvent = lambda _: toolbar_search_mouse_event()

        self.toolbar_search.setMaximumWidth(300)
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

        self.toolbar.addAction(self.clean_ls_search_action)

        self.clean_ls_search_action.triggered.connect(self.erase_address)
        self.clean_ls_search_action.setEnabled(False)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.run_action)

        self.about_action = QAction(self.run_icon, "About", self.iface.mainWindow())
        self.about_action.setWhatsThis(f"{PLUGIN_NAME} About")
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", self.about_action)

        self.about_action.triggered.connect(self.about)
        self.dlg.ui.btnLoadLayer.clicked.connect(lambda: self.load_layer("default"))
        self.dlg.ui.btnLoadLayerTop.clicked.connect(lambda: self.load_layer("top"))
        self.dlg.ui.btnLoadLayerBottom.clicked.connect(
            lambda: self.load_layer("bottom")
        )

        self.dlg.ui.pushButton.clicked.connect(self.toggle_all_fq_checkboxes)

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

        self.dlg.ui.cb_flashing_geoms.stateChanged.connect(self.change_result_visual)

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
        except Exception:
            pass
        QgsApplication.processingRegistry().removeProvider(self.provider)

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
            self.current_layer = None
            self.dlg.ui.layer_info.setHtml("")
            self.dlg.ui.comboSelectProj.clear()
            self.dlg.ui.layer_info.setHidden(True)
            self.dlg.ui.layer_options_groupbox.setHidden(True)
            return

        self.dlg.ui.layer_info.setHidden(False)
        self.dlg.ui.layer_options_groupbox.setHidden(False)

        # needed to scroll To the selected row incase of using the keyboard / arrows
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[0])
        # itemType holds the data (== column 1)
        self.current_layer = self.dlg.servicesView.selectedIndexes()[1].data(
            Qt.UserRole
        )
        self.update_layer_panel()

    def update_layer_panel(self):
        url = self.current_layer["service_url"]
        title = self.current_layer["title"]
        abstract_dd = self.get_dd(self.current_layer["abstract"])

        service_title = (
            self.current_layer["service_title"]
            if self.current_layer["service_title"]
            else "[service title niet ingevuld]"
        )
        layername = self.current_layer["name"]
        service_abstract_dd = self.get_dd(self.current_layer["service_abstract"])
        stype = self.service_type_mapping(self.current_layer["service_type"]) if self.current_layer["service_type"] in self.service_type_mapping else self.current_layer["service_type"].upper()
        minscale = ""
        if "minscale" in self.current_layer:
            minscale = self.format_scale_denominator(self.current_layer["minscale"])
        maxscale = ""
        if "maxscale" in self.current_layer:
            maxscale = self.format_scale_denominator(self.current_layer["maxscale"])
        service_md_id = self.current_layer["service_md_id"]
        dataset_md_id = self.current_layer["dataset_md_id"]
        self.dlg.ui.layer_info.setText("")
        self.dlg.ui.btnLoadLayer.setEnabled(True)
        self.dlg.ui.btnLoadLayerTop.setEnabled(True)
        self.dlg.ui.btnLoadLayerBottom.setEnabled(True)

        fav = False
        if self.pdok_layer_in_favs(self.current_layer) != -1:
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
            "OGC API - features": "OGC API - features",
            "OGC API - tiles": "OGC API - tiles",
        }
        layername_key = f"{layername_key_mapping[stype]}"
        # Go to endpoint of ogcapi features since no features in ngr
        if stype == "OGC API - features":
            dataset_metadata_dd = self.get_dd(
                stype,
                f'<a title="Bekijk dataset metadata van OAPIF" href="{url}/collections/{layername}">{title} - {layername}</a>',
            )
            service_metadata_dd = self.get_dd(
                stype,
                f'<a title="Bekijk service metadata van OAPIF" href="{url}">{service_title}</a>',
            )
        else:
            dataset_metadata_dd = self.get_dd(
                dataset_md_id,
                f'<a title="Bekijk dataset metadata in NGR" href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{dataset_md_id}">{dataset_md_id}</a>',
            )
            service_metadata_dd = self.get_dd(
                service_md_id,
                f'<a title="Bekijk service metadata in NGR" href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{service_md_id}">{service_md_id}</a>',
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
            self.dlg.ui.comboSelectProj: ["WMS", "WMTS", "OGC API - tiles"],
            self.dlg.ui.labelCrs: ["WMS", "WMTS", "OGC API - tiles"],
            self.dlg.ui.wmsStyleComboBox: ["WMS", "OGC API - tiles"],
            self.dlg.ui.wmsStyleLabel: ["WMS", "OGC API - tiles"],
        }

        for ui_el in show_list.keys():
            service_types = show_list[ui_el]
            ui_el.setHidden(not (stype in service_types))

        if stype == "WMS" or stype == "OAT":
            styles = self.current_layer["styles"]
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

        if stype == "WMS":
            try:
                crs = self.current_layer["crs"]
            except KeyError:
                crs = "EPSG:28992"
            crs = crs.split(",")
            self.dlg.ui.comboSelectProj.addItems(crs)
            for i in range(len(crs)):
                if crs[i] == "EPSG:28992":
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

        if stype == "WMTS":
            tilematrixsets = self.current_layer["tilematrixsets"].split(",")
            self.dlg.ui.comboSelectProj.addItems(tilematrixsets)
            for i in range(len(tilematrixsets)):
                if tilematrixsets[i].startswith("EPSG:28992"):
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)

        if stype == "OGC API - tiles":
            try:
                crs = self.current_layer["crs"]
            except KeyError:
                crs = "EPSG:28992"
            crs = crs.split(",")
            self.dlg.ui.comboSelectProj.addItems(map(self.extract_crs, crs))
            for i in range(len(crs)):
                if crs[i] == "EPSG:28992":
                    self.dlg.ui.comboSelectProj.setCurrentIndex(i)


    def extract_crs(self,crs_string):
        pattern = r'/EPSG/(\d+)/(\d+)'
        match = re.search(pattern, crs_string)
        if match:
            return f"EPSG:{match.group(2)}"
        else:
            return crs_string
        
    def quote_wmts_url(self, url):
        """
        Quoten wmts url is nodig omdat qgis de query param `SERVICE=WMS` erachter plakt als je de wmts url niet quote.
        Dit vermoedelijk omdat de wmts laag wordt toegevoegd mbv de wms provider: `return QgsRasterLayer(uri, title, "wms")`.
        Wat op basis van de documentatie wel de manier is om een wmts laag toe te voegen.
        """
        parse_result = urllib.parse.urlparse(url)
        location = f"{parse_result.scheme}://{parse_result.netloc}/{parse_result.path}"
        query = parse_result.query
        query_escaped_quoted = urllib.parse.quote_plus(query)
        url = f"{location}?{query_escaped_quoted}"
        return url

    def get_selected_style(self):
        selected_style_title = self.dlg.ui.wmsStyleComboBox.currentText()
        selected_style = None
        if "styles" in self.current_layer:
            selected_style = next(
                (
                    x
                    for x in self.current_layer["styles"]
                    if x["title"] == selected_style_title
                ),
                None,
            )
            if selected_style is None:
                # check if selected_style_title is one of the style names, in case the style in the cap doc does not have a title
                # style should have at least a name
                selected_style = next(
                    (
                        x
                        for x in self.current_layer["styles"]
                        if x["name"] == selected_style_title
                    ),
                    None,
                )
        return selected_style

    def get_crs_comboselect(self):
        if self.dlg.ui.comboSelectProj.currentIndex() == -1:
            crs = "EPSG:28992"
        else:
            crs = self.dlg.ui.comboSelectProj.currentText()
        return crs

    def create_new_layer(self):
        servicetype = self.current_layer["service_type"]
        title = self.current_layer["title"]
        layername = self.current_layer["name"]
        url = self.current_layer["service_url"]

        if servicetype == "wms":
            imgformat = self.current_layer["imgformats"].split(",")[0]
            crs = self.get_crs_comboselect()

            selected_style_name = ""
            if "selectedStyle" in self.current_layer:
                selected_style = self.current_layer["selectedStyle"]
            else:
                selected_style = self.get_selected_style()
            if selected_style is not None:
                selected_style_name = selected_style["name"]
                selected_style_title = selected_style["name"]
                if "title" in selected_style:
                    selected_style_title = selected_style["title"]
                title += f" [{selected_style_title}]"

            uri = f"crs={crs}&layers={layername}&styles={selected_style_name}&format={imgformat}&url={url}"
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
            tilematrixset = self.get_crs_comboselect()

            imgformat = self.current_layer["imgformats"].split(",")[0]
            if tilematrixset.startswith("EPSG:"):
                crs = tilematrixset
                i = crs.find(":", 5)
                if i > -1:
                    crs = crs[:i]
            elif tilematrixset.startswith("OGC:1.0"):
                crs = "EPSG:3857"
            else:
                # non PDOK services do not have a strict tilematrixset naming based on crs...
                crs = self.current_layer["crs"]
            uri = f"tileMatrixSet={tilematrixset}&crs={crs}&layers={layername}&styles=default&format={imgformat}&url={url}"
            return QgsRasterLayer(
                uri, title, "wms"
            )  # `wms` is correct, zie ook quote_wmts_url
        elif servicetype == "wfs":
            uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
            return QgsVectorLayer(uri, title, "wfs")
        elif servicetype == "wcs":
            # HACK to get WCS to work:
            # 1) fixed format to "GEOTIFF"
            # 2) remove the '?request=getcapabiliteis....' part from the url, unknown why this is required compared to wms/wfs
            # better approach would be to add the supported format(s) to the layers-pdok.json file and use that - this should be the approach when more
            # WCS services will be published by PDOK (currently it is only the AHN WCS)
            format = "GEOTIFF"
            uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
            return QgsRasterLayer(uri, title, "wcs")
        elif servicetype == "api features":  # OGC API Features
            uri = f" pagingEnabled='true' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}'"
            return QgsVectorLayer(uri, title, 'OAPIF')
        elif servicetype == "api tiles":  # OGC API Tiles

            # CRS met oat werkt nog niet correct in qgis/gdal
            crs = self.get_crs_comboselect()
            crs_mapping = {
                "EPSG:28992": "NetherlandsRDNewQuad",
                "EPSG:3857": "WebMercatorQuad",
                "EPSG:4258": "EuropeanETRS89_GRS80Quad_Draft",
                "EPSG:3035": "EuropeanETRS89_LAEAQuad"
            }
            # Style toevoegen in laag vanuit ui
            selected_style_name = (
                self.current_layer["default"] if "default" in self.current_layer else ""
            )
            selected_style = self.get_selected_style()
            if selected_style is not None:
                selected_style_name = selected_style["name"]
                selected_style_url = selected_style["url"]
                title += f" [{selected_style_name}]"

            url_template = (
                url + "/tiles/" + crs_mapping[crs] + "/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt"
            )
            if crs == "EPSG:28992":
                maxz_coord = 12
            elif crs == "EPSG:4258" or crs == "EPSG:3035":
                maxz_coord = 14
            else:
                maxz_coord = 17
            minz_coord = 1 # Better performance wise, see QGIS issue https://github.com/qgis/QGIS/issues/54312
            type = "xyz"
            uri = f"styleUrl={selected_style_url}&url={url_template}&type={type}&zmax={maxz_coord}&zmin={minz_coord}&http-header:referer="
            return QgsVectorTileLayer(uri, title)
        else:
            self.show_warning(
                f"""Sorry, dit type laag: '{servicetype.upper()}'
                kan niet worden geladen door de plugin of door QGIS.
                Is het niet beschikbaar als wms, wmts, wfs, api features of api tiles (vectortile)?
                """
            )
            return

    def load_layer(self, tree_location=None):
        if self.current_layer == None:
            return
        servicetype = self.current_layer["service_type"]
        if tree_location is None:
            tree_location = self.default_tree_locations[servicetype]
        new_layer = self.create_new_layer()
        if new_layer is None:
            return
        self.add_layer(new_layer, tree_location)

    def add_layer(self, new_layer, tree_location="default"):
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
        # AND save current state to QSettings
        checked_boxes = []
        for key in self.fq_checkboxes.keys():
            if key.isChecked():
                checked_boxes.append(self.fq_checkboxes[key].name)
        log.debug(checked_boxes)
        self.set_settings_value("checkedfqs", checked_boxes)

    def ls_dialog_get_suggestions(self):
        try:
            self.dlg.ui.lookupinfo.setHtml("")
            self.dlg.ui.geocoderResultSearchLabel.setEnabled(False)
            self.dlg.ui.geocoderResultSearch.setEnabled(False)
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
                search_string = QStandardItem(f'{str(result["weergavenaam"])} {str(result["type"])}')
                self.geocoder_source_model.appendRow([adrestekst, type, search_string])
            self.geocoder_source_model.setHeaderData(0, Qt.Horizontal, "Resultaat")
            self.geocoder_source_model.setHeaderData(1, Qt.Horizontal, "Type")
            self.geocoder_source_model.horizontalHeaderItem(0).setTextAlignment(
                Qt.AlignLeft
            )
            self.dlg.geocoderResultView.resizeColumnsToContents()
            self.dlg.geocoderResultView.setColumnHidden(2, True)

            self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)
            self.dlg.ui.geocoderResultSearchLabel.setEnabled(True)
            self.dlg.ui.geocoderResultSearch.setEnabled(True)

        except PdokServicesNetworkException as ex:
            title = f"{PLUGIN_NAME} - HTTP Request Error"
            message = f"""an error occured while executing HTTP request, error:
                    {str(ex)}
                    """
            self.show_error(message, title)

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

    @staticmethod
    def valueToBool(value):
        """
        Apparently QGIS or Qt fiddles with boolean QSettings values, sometimes it is False and sometimes 'false'
        :param value:
        :return:
        """
        return value.lower() == 'true' if isinstance(value, str) else bool(value)

    def run(self, hiddenDialog=False):
        """
        run method that performs all the real work
        """
        # last viewed/selected tab
        if QSettings().contains(f"/{PLUGIN_ID}/currenttab"):
            self.dlg.tabs.widget(int(QSettings().value(f"/{PLUGIN_ID}/currenttab")))

        flashing_geoms = self.valueToBool(QSettings().value(f"/{PLUGIN_ID}/flashing_geoms"))
        self.dlg.ui.cb_flashing_geoms.setChecked(flashing_geoms)
        self.clean_ls_search_action.setEnabled(not flashing_geoms)

        if self.services_loaded == False:
            self.layers_pdok = []
            pdokjson = os.path.join(self.plugin_dir, "resources", "layers-pdok.json")
            with open(pdokjson, "r", encoding="utf-8") as f:
                self.layers_pdok.extend(json.load(f))

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
            self.geocoderProxyModel.setFilterKeyColumn(2)
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
                lambda: self.load_layer(None)
            )  # Using lambda here to prevent sending signal parameters to the loadService() function

            self.dlg.servicesView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.dlg.servicesView.customContextMenuRequested.connect(
                self.make_fav_context_menu
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
        QSettings().setValue(f"/{PLUGIN_ID}/currenttab", self.dlg.tabs.currentIndex())
        self.remove_pointer_or_layer()

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
            title = f"{PLUGIN_NAME} - HTTP Request Error"
            message = textwrap.dedent(
                f"""an error occured while executing HTTP request, error:

                {str(ex)}
                """
            )
            self.show_error(message, title)
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
        if self.semver_greater_or_equal_then(semversion, "3.18.0") and self.valueToBool(QSettings().value(f"/{PLUGIN_ID}/flashing_geoms")):
            # it is possible to use the new shiny flashing geoms
            return True
        # the 'old way' :-)
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
            self.info(
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
                title = f"{PLUGIN_NAME} - HTTP Request Error"
                message = textwrap.dedent(
                    f"""an error occured while executing HTTP request, error:

                    {str(ex)}
                    """
                )
                self.show_error(message, title)
            if data is None:
                return
        self.fill_lookup_info(data)
        self.zoom_to_result(data)

    def set_pointer(self, point):
        self.remove_pointer()
        self.pointer = QgsVertexMarker(self.iface.mapCanvas())
        self.pointer.setColor(QColor(255, 255, 0))
        self.pointer.setIconSize(10)
        self.pointer.setPenWidth(5)
        self.pointer.setCenter(point)
        self.clean_ls_search_action.setEnabled(True)

    def remove_pointer(self):
        if self.pointer is not None and self.pointer.scene() is not None:
            self.iface.mapCanvas().scene().removeItem(self.pointer)
            self.pointer = None
            self.clean_ls_search_action.setEnabled(False)

    def change_result_visual(self, checked: bool):
        if checked:
            # default: user checked show results as 'new style/flashing geoms', save in QSettings
            QSettings().setValue(f"/{PLUGIN_ID}/flashing_geoms", True)
        else:
            # user want the old behaviour, save in QSettings
            QSettings().setValue(f"/{PLUGIN_ID}/flashing_geoms", False)
        self.clean_ls_search_action.setEnabled(not checked)

    def info(self, msg=""):
        QgsMessageLog.logMessage("{}".format(msg), "PDOK-services Plugin", Qgis.Info)

    def show_error(self, message, title="PDOK plugin"):
        message = textwrap.dedent(
            message
        )  # textwrap.dedent nodig want anders leading whitespace issue, zie https://stackoverflow.com/a/1412728/1763690
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
        )  # textwrap.dedent nodig want anders leading whitespace issue, zie https://stackoverflow.com/a/1412728/1763690
        QMessageBox.warning(
            self.iface.mainWindow(),
            title,
            (message),
            QMessageBox.Ok,
            QMessageBox.Ok,
        )

    def save_fav_layer_in_settings(self, fav_layer):
        favs = self.get_favs_from_settings()
        nr_of_favs = len(favs)
        new_fav_i = nr_of_favs + 1
        QSettings().setValue(f"/{PLUGIN_ID}/favourite_{new_fav_i}", fav_layer)

    def get_favs_from_settings(self):
        favs = []
        i = 1
        while True:
            fav = QSettings().value(f"/{PLUGIN_ID}/favourite_{i}", None)
            if fav is None:
                break
            favs.append(fav)
            i += 1
        return favs

    def get_fav_layer_index(self, fav_layer_to_get_index):
        fav_layers = self.get_favs_from_settings()
        # find index of fav layer to delete
        fav_index = -1
        for i in range(0, len(fav_layers)):
            fav_layer = fav_layers[i]
            if self.layer_equals_fav_layer(fav_layer_to_get_index, fav_layer):
                fav_index = i
                break
        return fav_index

    def delete_fav_layer_in_settings(self, fav_layer_to_delete):
        fav_layers = self.get_favs_from_settings()
        nr_of_favs = len(fav_layers)
        # find index of fav layer to delete
        fav_del_index = self.get_fav_layer_index(fav_layer_to_delete)
        # delete fav layer if found
        if fav_del_index != -1:
            del fav_layers[fav_del_index]
            # overwrite remaining favs from start to end and remove last
            # remaining fav
            for i in range(0, len(fav_layers)):
                fav_layer = fav_layers[i]
                QSettings().setValue(f"/{PLUGIN_ID}/favourite_{i+1}", fav_layer)
            settings = QSettings()
            settings.remove(f"/{PLUGIN_ID}/favourite_{nr_of_favs}")

    def move_item_in_list(self, the_list, index, direction):
        if not direction in [1, -1]:
            raise ValueError()
        if index <= 0 and direction == -1:
            return the_list
        if index >= len(the_list) - 1 and direction == 1:
            return the_list
        pos1 = index
        pos2 = index + (direction)
        the_list[pos1], the_list[pos2] = the_list[pos2], the_list[pos1]
        return the_list

    def change_index_fav_layer_in_settings(self, fav_layer_to_change, index_delta):
        fav_layers = self.get_favs_from_settings()
        fav_change_index = -1
        for i in range(0, len(fav_layers)):
            fav_layer = fav_layers[i]
            if self.layer_equals_fav_layer(fav_layer_to_change, fav_layer):
                fav_change_index = i
                break

        if fav_change_index != -1:
            fav_layers = self.move_item_in_list(
                fav_layers, fav_change_index, index_delta
            )
            for i in range(0, len(fav_layers)):
                fav_layer = fav_layers[i]
                QSettings().setValue(f"/{PLUGIN_ID}/favourite_{i+1}", fav_layer)

    def make_fav_context_menu(self, position):
        menu = QMenu()
        if self.current_layer:
            fav_index = self.pdok_layer_in_favs(self.current_layer)
            favs = self.get_favs_from_settings()
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
                if action == delete_fav_action:
                    # delete layer to favourites with qsettngs
                    # then update favourite context menu
                    self.delete_fav_layer_in_settings(self.current_layer)
                    self.update_layer_panel()
                elif action == up_fav_action:
                    self.change_index_fav_layer_in_settings(self.current_layer, -1)
                elif action == down_fav_action:
                    self.change_index_fav_layer_in_settings(self.current_layer, 1)
                self.add_fav_actions_to_toolbar_button()

            else:
                selected_style = self.get_selected_style()
                if selected_style is not None:
                    self.current_layer = {
                        **self.current_layer,
                        **{"selectedStyle": selected_style},
                    }
                add_fav_action = QAction(f"Voeg deze laag toe aan favorieten")
                add_fav_action.setIcon(self.fav_icon)
                menu.addAction(add_fav_action)
                action = menu.exec_(self.dlg.servicesView.mapToGlobal(position))
                if action == add_fav_action:
                    # save layer to favourites with qsettngs
                    # then update favourite context menu
                    self.save_fav_layer_in_settings(self.current_layer)
                    self.update_layer_panel()
                    self.add_fav_actions_to_toolbar_button()

    def load_fav_layer(self, fav_layer, index):
        if fav_layer:
            # migration code required for change: https://github.com/rduivenvoorde/pdokservicesplugin/commit/a5700dace54250b8f18229939907c3cab39f5297
            # which changed the schema of the layer config json file
            migrate_fav = False
            if "md_id" in fav_layer:
                fav_layer["service_md_id"] = fav_layer["md_id"]
                migrate_fav = True
            if "layers" in fav_layer:
                fav_layer["name"] = fav_layer["layers"]
                migrate_fav = True
            layer = self.get_layer_in_pdok_layers(fav_layer)

            if "selectedStyle" in fav_layer:
                layer["selectedStyle"] = fav_layer["selectedStyle"]
            if migrate_fav:
                QSettings().setValue(f"/{PLUGIN_ID}/favourite_{index}", layer)
            if layer:
                self.current_layer = layer
                self.load_layer()
                return
        # layer fav_layer not found, ask user to delete it, do NOT open the dialog (old behaviour)
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            "Geen Favoriet aanwezig (of verouderd)...",
            "Het lijkt erop dat deze Favoriet niet meer bestaat (bij PDOK). Uit uw Favorieten verwijderen?",
            QMessageBox.Yes,
            QMessageBox.No,
        )
        # if YES: clean it up from settings and update the toolbar actions
        if reply == QMessageBox.Yes:
            log.debug("CLEAN UP")
            self.delete_fav_layer_in_settings(fav_layer)
            self.add_fav_actions_to_toolbar_button()

    def get_layer_in_pdok_layers(self, lyr):
        """
        returns None if layer not found
        """

        def predicate(x):
            return self.layer_equals_fav_layer(lyr, x)

        return next(filter(predicate, self.layers_pdok), None)

    def layer_equals_fav_layer(self, lyr, fav_lyr):
        """
        check for layer equality based on equal
        - service_md_id
        - name (layername)
        - style (in case of WMS layer)
        """
        # fix #77: names of keys have been changed, so IF there is an old set, try to fix
        if "service_md_id" not in fav_lyr:
            if "md_id" in fav_lyr:
                # local migration
                fav_lyr["service_md_id"] = fav_lyr["md_id"]
                # thinking I could maybe 'fix' the settings I thought to get the fav_layer_index here, BUT
                # not possible because that function itself calls layer_equals_fav_layer => too much recursion
                # log.debug(f'fav_layer index?: {self.get_fav_layer_index(fav_lyr)}')
            else:
                # unable to 'fix' ...
                return False
        if (
            fav_lyr["service_md_id"] == lyr["service_md_id"]
            and fav_lyr["name"] == lyr["name"]
        ):
            # WMS layer with style
            if "style" in fav_lyr and "style" in lyr:
                if fav_lyr["style"] == lyr["style"]:
                    return True
                else:
                    return False
            # other layer without style (but with matching layername and service_md_id)
            return True
        return False

    def pdok_layer_in_favs(self, lyr):
        def predicate(x):
            return self.layer_equals_fav_layer(lyr, x)

        fav_layers = self.get_favs_from_settings()
        i = next((i for i, v in enumerate(fav_layers) if predicate(v)), -1)
        return i

    def add_fav_actions_to_toolbar_button(self):
        # first reset existing fav_actions
        for fav_action in self.fav_actions:
            self.run_button.menu().removeAction(fav_action)
        self.fav_actions = []
        fav_layers = self.get_favs_from_settings()

        # add fav_actions
        if len(fav_layers) == 0:
            fav_action = QAction(f"Maak een favoriet aan in het PDOK Services tabblad")
            fav_action.setIcon(self.fav_icon)
            fav_action.setEnabled(False)
            self.run_button.menu().addAction(fav_action)
            self.fav_actions.append(fav_action)
        else:
            i = 1
            for fav_layer in fav_layers:
                if fav_layer:
                    fav_action = QAction()
                    fav_action.setIcon(self.fav_icon)
                    fav_action.triggered.connect(
                        (
                            lambda fav_layer, i: lambda: self.load_fav_layer(
                                fav_layer, i
                            )
                        )(fav_layer, i)
                    )  # Double lambda is required in order to freeze argument, otherwise always last favourite is added
                    # see https://stackoverflow.com/a/10452866/1763690

                    fav_action.setToolTip(fav_layer["title"].capitalize())
                    title = fav_layer["title"].capitalize()
                    if "selectedStyle" in fav_layer:
                        style = fav_layer["selectedStyle"]
                        if "name" in style:
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
                    i += 1
