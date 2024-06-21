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
from qgis.PyQt.QtGui import (
    QIcon,
    QStandardItemModel,
    QStandardItem,
    QColor,
    QImage,
)
from qgis.PyQt.QtCore import QSortFilterProxyModel
# note: needed for Qt6!
from qgis.PyQt.QtCore import QRegularExpression

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
from . import LOGGER_NAME

log = logging.getLogger(LOGGER_NAME)

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
            self.dlg.cbx_gem: LsType.gemeente,
            self.dlg.cbx_wpl: LsType.woonplaats,
            self.dlg.cbx_weg: LsType.weg,
            self.dlg.cbx_pcd: LsType.postcode,
            self.dlg.cbx_adr: LsType.adres,
            self.dlg.cbx_pcl: LsType.perceel,
            self.dlg.cbx_hmp: LsType.hectometerpaal,
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
        self.run_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
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
            "api features": "OGC API - Features",
            "api tiles": "OGC API - Tiles",
        }

        self.add_fav_actions_to_toolbar_button()

        self.toolbar_search = QLineEdit()

        def toolbar_search_mouse_event():
            self.toolbar_search.selectAll()
            self.timer_toolbar_search.start()

        self.toolbar_search.mousePressEvent = lambda _: toolbar_search_mouse_event()

        self.toolbar_search.setMaximumWidth(300)
        self.toolbar_search.setAlignment(Qt.AlignmentFlag.AlignLeft)
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
        self.dlg.btnLoadLayer.clicked.connect(lambda: self.load_layer("default"))
        self.dlg.btnLoadLayerTop.clicked.connect(lambda: self.load_layer("top"))
        self.dlg.btnLoadLayerBottom.clicked.connect(
            lambda: self.load_layer("bottom")
        )

        self.dlg.pushButton.clicked.connect(self.toggle_all_fq_checkboxes)

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

        self.dlg.cb_flashing_geoms.toggled.connect(self.change_result_visual)

        # set to hidden when no layer selected
        self.dlg.layer_info.setHidden(True)
        self.dlg.layer_options_groupbox.setHidden(True)

        # we want to use html (plus ogg and pdok logo's) in the info webview of the dialog
        # so because we want it to be used in both Qt5 and Qt6, we cannot use resource files
        # so a way to handle this, is to use base64 encoded image strings in the img-html tags
        # to create the base64 string of the ogg.gif:
        # base64 -w0 ogg.gif
        # and then <img src="data:image/GIF;base64, base64string"/>
        # base64 -w0 pdok.png
        # and then <img src="data:image/PNG;base64, base64string"/>
        html = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
        <html><head><meta name="qrichtext" content="1" />
        <style type="text/css">
        body { font-family:'Helvetica Neue','Helvetica','Arial','sans-serif'; font-size:15px; font-weight:304; color:#444444;  }
        p { margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; line-height:162.5%; }
        h2 { margin-top:16px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; line-height:162.5%; }
        h3 { margin-top:14px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; line-height:162.5%; }
        h3 > span { font-size:large; font-weight:600; }
        h2 > span { font-size:x-large; font-weight:600; }
        a > span { font-size:large; font-weight:304; }
        </style>
        </head><body><p style="margin-top:0px;">Deze plugin wordt gemaakt door Richard Duivenvoorde (<a href="http://www.zuidt.nl"><span>Zuidt</span></a>). <br />De code van deze plugin is te vinden op <a href="https://github.com/rduivenvoorde/pdokservicesplugin"><span>Github</span></a>. Bugs kunt u daar melden.</p>
        <h2><span>PDOK</span></h2>
        <p><img src="data:image/PNG;base64, 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[" style="float: left;" /><a href="http://www.pdok.nl"><span>PDOK</span></a> stelt webservices beschikbaar van landsdekkende geo-informatie afkomstig van overheden. Deze data komen rechtstreeks bij de bron vandaan, d.w.z. dat overheidsorganisaties bronhouder van deze data zijn. Daardoor zijn de data actueel en betrouwbaar. Bovendien zijn ze door elke afnemer (overheid, bedrijf, particulier) kosteloos te gebruiken.</p>
        <p>De lijst van services en lagen in deze plugin worden met behulp van het 'pdokservicesspider' script gegeneerd (te vinden op <a href="https://github.com/rduivenvoorde/pdokservicesplugin"><span>Github</span></a><span >). Dit script genereert deze lijst op basis van de </span><a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/csw?service=CSW&amp;request=GetCapabilities&amp;version=2.0.2"><span>CSW service</span></a> van het <a href="https://www.nationaalgeoregister.nl/"><span>Nationaal Georegister</span></a>.</p>
        <h2><span>OpenGeoGroep</span></h2>
        <h3><span>Anders denken, Anders doen..</span></h3>
        <p><img src="data:image/GIF;base64, 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[" style="float: left;" />De <a href="http://www.opengeogroep.nl"><span>OpenGeoGroep</span></a> is een commerciele ICT-dienstverlener die diensten en oplossingen biedt voor geo-informatie vraagstukken. Al onze diensten zijn leveranciersonafhankelijk. De OpenGeoGroep onderscheidt zich door het aanbieden van diensten en innovatieve oplossingen gebaseerd op professionele Open Source Software en op basis van Open Standaarden.
        </p>
        </body>
        </html>
        """
        self.dlg.webView.setHtml(html)

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
            self.dlg.layer_info.setHtml("")
            self.dlg.comboSelectProj.clear()
            self.dlg.layer_info.setHidden(True)
            self.dlg.layer_options_groupbox.setHidden(True)
            return

        self.dlg.layer_info.setHidden(False)
        self.dlg.layer_options_groupbox.setHidden(False)

        # needed to scroll To the selected row incase of using the keyboard / arrows
        self.dlg.servicesView.scrollTo(self.dlg.servicesView.selectedIndexes()[0])
        # itemType holds the data (== column 1)
        self.current_layer = self.dlg.servicesView.selectedIndexes()[1].data(
            Qt.ItemDataRole.UserRole
        )
        self.update_layer_panel()

    def update_layer_panel(self):
        url = self.current_layer["service_url"]
        title = self.current_layer["title"]
        abstract_dd = self.get_dd(self.current_layer["abstract"])
        service_abstract_dd = self.get_dd(self.current_layer["service_abstract"])

        service_title = (
            self.current_layer["service_title"]
            if self.current_layer["service_title"]
            else "[service title niet ingevuld]"
        )
        layername = self.current_layer["name"]
        stype = (
            self.service_type_mapping[self.current_layer["service_type"]]
            if self.current_layer["service_type"] in self.service_type_mapping
            else self.current_layer["service_type"].upper()
        )
        minscale = ""
        if "minscale" in self.current_layer:
            minscale = self.format_scale_denominator(self.current_layer["minscale"])
        maxscale = ""
        if "maxscale" in self.current_layer:
            maxscale = self.format_scale_denominator(self.current_layer["maxscale"])
        service_md_id = self.current_layer["service_md_id"]
        dataset_md_id = self.current_layer["dataset_md_id"]
        self.dlg.layer_info.setText("")
        self.dlg.btnLoadLayer.setEnabled(True)
        self.dlg.btnLoadLayerTop.setEnabled(True)
        self.dlg.btnLoadLayerBottom.setEnabled(True)

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
            "OGC API - Features": "OGC API - Features",
            "OGC API - Tiles": "Vector Tiles",
        }
        layername_key = f"{layername_key_mapping[stype]}"
        if dataset_md_id and dataset_md_id.startswith('http'):
            dataset_metadata_dd = self.get_dd(
                dataset_md_id,
                f'<a title="Info" href="{dataset_md_id}">{dataset_md_id}</a>',
            )
        else:
            dataset_metadata_dd = self.get_dd(
                dataset_md_id,
                f'<a title="Bekijk dataset metadata in NGR" href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{dataset_md_id}">{dataset_md_id}</a>',
            )
        if service_md_id and service_md_id.startswith('http'):
            service_metadata_dd = self.get_dd(
                service_md_id,
                f'<a title="Info" href="{service_md_id}">{service_md_id}</a>',
            )

        else:
            service_metadata_dd = self.get_dd(
                service_md_id,
                f'<a title="Bekijk service metadata in NGR" href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/{service_md_id}">{service_md_id}</a>',
            )
        fav_string = ""
        fav_title = ""
        if fav:
            # earlier we used bookmark.png from the resources, we now do this by using the images as base64 encoded string
            fav_string = '<img style="margin:10px" src="data:image/PNG;base64, iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAABaUlEQVQ4T62UQU7CQBSG35sEQ7vRbYFEuAGcQI6gSy1GvEE9gXoCuQE12rjVG8AJ5AZ2AbLUVdtInOcbSGsLTaeCk3Qz7++X/39vZhD+eWEZ3swznllHdTs80em1wKlX7SOIoQIRyMuGHblFUC2Q3fkAeLiCkM8uW1sD0+5iiM5locOsuwRZ6DIDnD9Uu1KIff61zfH4w+P8eMRDwgnXJgLlp3UWjWMdfgzhINgzXlnQ1E2wuE6++RV2cOpV2ggVBu6+CBadZeS85v8VHw8r6eEu0PTkM0PZBrp+jDaOzfuj4RDiXZnISHRV64WDtHYDOPPMGxZclwGy5rZuB0qfrByHpksIF2WASHBf6wX9QuDUM0YIeFQGSEDjhh12dZFpHaacqL085xw5kzJ79Z6qTSnF2y+QXoQgxzqNfLU35/q3RDedQAjZiutKkzOU5WMKQtLAOo9GedFXdx4dVePnLHPfte9hmV6mNT+oioxxBG338AAAAABJRU5ErkJggg==[" align="left" />&nbsp;&nbsp;'
            fav_title = "&nbsp;[favoriet]"

        show_dev_urls = stype == "OGC API - Tiles"
        dev_urls_html = (
            f"""
        <h3>Ontwikkelaars informatie</h3>
        <dl>
            <dt><b>URLs voor Tiles</b></dt>
            <dd>
                {self.get_tiles_urls(url, self.current_layer["tiles"][0])}
            </dd>
            <dt><b>URLs voor Styles</b></dt>
            <dd>
                {self.get_styles_urls(self.current_layer["styles"])}
            </dd>
        </dl>
        """
            if show_dev_urls
            else ""
        )

        self.dlg.layer_info.setHtml(
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
                {service_metadata_dd}
            </dl>
            {dev_urls_html}
            """
        )
        self.dlg.comboSelectProj.clear()
        self.dlg.wmsStyleComboBox.clear()

        show_list = {
            self.dlg.comboSelectProj: ["WMS", "WMTS", "OGC API - Tiles"],
            self.dlg.labelCrs: ["WMS", "WMTS", "OGC API - Tiles"],
            self.dlg.wmsStyleComboBox: ["WMS", "OGC API - Tiles"],
            self.dlg.wmsStyleLabel: ["WMS", "OGC API - Tiles"],
        }

        for ui_el in show_list.keys():
            service_types = show_list[ui_el]
            ui_el.setHidden(not (stype in service_types))

        if stype == "WMS" or stype == "OGC API - Tiles":
            styles = self.current_layer["styles"]
            nr_styles = len(styles)
            style_str = "styles" if nr_styles > 1 else "style"
            self.dlg.wmsStyleLabel.setText(
                f"Style ({nr_styles} {style_str} beschikbaar)"
            )
            style_title_names = [
                x["title"] if "title" in x else x["name"] for x in styles
            ]
            self.dlg.wmsStyleComboBox.addItems(style_title_names)
            self.dlg.wmsStyleComboBox.setCurrentIndex(0)
            self.dlg.wmsStyleComboBox.setEnabled(
                nr_styles > 1  # enable if more than one style
            )

        if stype == "WMS":
            crs = self.current_layer.get("crs", "EPSG:28992")
            crs = crs.split(",")
            self.dlg.comboSelectProj.addItems(crs)
            for i, c in enumerate(crs):
                if c == "EPSG:28992":
                    self.dlg.comboSelectProj.setCurrentIndex(i)

        elif stype == "WMTS":
            tilematrixsets = self.current_layer["tilematrixsets"].split(",")
            self.dlg.comboSelectProj.addItems(tilematrixsets)
            for i, tilematrixset in enumerate(tilematrixsets):
                if tilematrixset.startswith("EPSG:28992"):
                    self.dlg.comboSelectProj.setCurrentIndex(i)

        elif stype == "OGC API - Tiles":
            tiles = self.current_layer["tiles"][0]
            crs_list = [
                self.extract_crs(tileset["tileset_crs"])
                for tileset in tiles["tilesets"]
            ]
            self.dlg.comboSelectProj.addItems(crs_list)
            for i, crs in enumerate(crs_list):
                if crs.endswith("3857"):
                    self.dlg.comboSelectProj.setCurrentIndex(i)
                    self.dlg.comboSelectProj.model().item(i).setEnabled(True)
                else:
                    # We disable all options that do not support correct projection of vector tiles
                    self.dlg.comboSelectProj.model().item(i).setEnabled(False)
                    self.dlg.comboSelectProj.setToolTip(
                        f"""
                        OGC API - Tiles wordt momenteel alleen correct weergegeven in webmercator CRS (EPSG:3857). 
                        Het gebruik van andere CRS zorgt momenteel voor foutieve projecties. 
                        Zie: https://github.com/qgis/QGIS/issues/54673
                        """
                    )

    def extract_crs(self, crs_string):
        pattern = r"/EPSG/(\d+)/(\d+)"
        match = re.search(pattern, crs_string)
        if match:
            return f"EPSG:{match.group(2)}"
        return crs_string

    def get_tiles_urls(self, url, tiles):
        url_tuple_list = [
            (
                self.build_tileset_url(url, tileset["tileset_id"], False),
                self.extract_crs(tileset["tileset_crs"]),
                tileset["tileset_max_zoomlevel"],
            )
            for tileset in tiles["tilesets"]
        ]
        html_tiles = "<ul>"
        for url, crs, max_zoomlevel in url_tuple_list:
            html_tiles += (
                f"<li>{url}<br>CRS: {crs}<br>Max Zoom Level: {max_zoomlevel}</li>"
            )
        return html_tiles + "</ul>"

    def get_styles_urls(self, styles):
        html_styles = "<ul>"
        for style in styles:
            html_styles += f"<li>{style['url']}</li>"
        return html_styles + "</ul>"

    def build_tileset_url(self, url, tileset_id, for_request):
        url_template = url + "/tiles/" + tileset_id
        if for_request:
            return url_template + "/%7Bz%7D/%7By%7D/%7Bx%7D?f%3Dmvt"
        return url_template + "/{z}/{y}/{x}?f=mvt"

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
        selected_style_title = self.dlg.wmsStyleComboBox.currentText()
        selected_style = None
        if "styles" in self.current_layer:
            selected_style = next(
                (
                    x
                    for x in self.current_layer["styles"]
                    if "title" in x and x["title"] == selected_style_title
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
        if self.dlg.comboSelectProj.currentIndex() == -1:
            return "EPSG:28992"
        return self.dlg.comboSelectProj.currentText()

    def create_new_layer(self):
        servicetype = self.current_layer["service_type"]
        title = self.current_layer["title"]
        layername = self.current_layer["name"]
        url = self.current_layer["service_url"]

        if servicetype == "wms":
            return self.create_wms_layer(layername, title, url)
        elif servicetype == "wmts":
            return self.create_wmts_layer(layername, title, url, servicetype)
        elif servicetype == "wfs":
            return self.create_wfs_layer(layername, title, url)
        elif servicetype == "wcs":
            return self.create_wcs_layer(layername, title, url)
        elif servicetype == "api features":
            return self.create_oaf_layer(layername, title, url)
        elif servicetype == "api tiles":
            return self.create_oat_layer(title, url)
        else:
            self.show_warning(
                f"""Sorry, dit type laag: '{servicetype.upper()}'
                kan niet worden geladen door de plugin of door QGIS.
                Is het niet beschikbaar als wms, wmts, wfs, api features of api tiles (vectortile)?
                """
            )
            return

    def create_wms_layer(self, layername, title, url):
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

    def create_wmts_layer(self, layername, title, url, servicetype):
        if Qgis.QGIS_VERSION_INT < 10900:
            self.show_warning(
                f"""Sorry, dit type layer: '{servicetype.upper()}'
                kan niet worden geladen in deze versie van QGIS.
                Misschien kunt u QGIS 2.0 installeren (die kan het WEL)?
                Of is de laag niet ook beschikbaar als wms of wfs?"""
            )
            return None
        url = self.quote_wmts_url(url)
        imgformat = self.current_layer["imgformats"].split(",")[0]
        # some fiddling with tilematrixset names and crs's (which sometimes are the same, but other times are not)
        tilematrixset = self.get_crs_comboselect()
        # IF there is a selectedCrs in the current_layer, this was a favourite (with selected crs)
        if "selectedCrs" in self.current_layer:
            # this means this was a WMTS layer from a favourite with one selected Crs (actually a MatrixSet!)
            tilematrixset = self.current_layer["selectedCrs"]
        uri = f"tileMatrixSet={tilematrixset}&layers={layername}&styles=default&format={imgformat}&url={url}"
        return QgsRasterLayer(
            uri, title, "wms"
        )  # LET OP: `wms` is correct, zie ook quote_wmts_url

    def create_wfs_layer(self, layername, title, url):
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
        return QgsVectorLayer(uri, title, "wfs")

    def create_wcs_layer(self, layername, title, url):
        # HACK to get WCS to work:
        # 1) fixed format to "GEOTIFF"
        # 2) remove the '?request=getcapabiliteis....' part from the url, unknown why this is required compared to wms/wfs
        # better approach would be to add the supported format(s) to the layers-pdok.json file and use that - this should be the approach when more
        # WCS services will be published by PDOK (currently it is only the AHN WCS)
        format = "GEOTIFF"
        uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
        return QgsRasterLayer(uri, title, "wcs")

    def create_oaf_layer(self, layername, title, url):
        uri = f" pagingEnabled='true' restrictToRequestBBOX='1' preferCoordinatesForWfsT11='false' typename='{layername}' url='{url}'"
        return QgsVectorLayer(uri, title, "OAPIF")

    def create_oat_layer(self, title, url):
        # CRS does not work as expected in qgis/gdal. We can set a crs (non-webmercator), but it is rendered incorrectly.
        crs = self.get_crs_comboselect()
        used_tileset = [
            tileset
            for tileset in self.current_layer["tiles"][0]["tilesets"]
            if tileset["tileset_crs"].endswith(crs.split(":")[1])
        ][0]

        # Style toevoegen in laag vanuit ui
        selected_style = self.get_selected_style()
        selected_style_url = ""

        if selected_style is not None:
            selected_style_url = selected_style["url"]
            title += f" [{selected_style['name']}]"

        url_template = self.build_tileset_url(url, used_tileset["tileset_id"], True)
        maxz_coord = used_tileset["tileset_max_zoomlevel"]

        # Although the vector tiles are only rendered for a specific zoom-level @PDOK (see maxz_coord),
        # we need to set the minimum z value to 0, which gives better performance, see https://github.com/qgis/QGIS/issues/54312
        minz_coord = 0

        type = "xyz"
        uri = f"styleUrl={selected_style_url}&url={url_template}&type={type}&zmax={maxz_coord}&zmin={minz_coord}&http-header:referer="
        tile_layer = QgsVectorTileLayer(uri, title)

        # Set the VT layer CRS and load the styleUrl
        tile_layer.setCrs(srs=QgsCoordinateReferenceSystem(crs))
        tile_layer.loadDefaultStyle()
        return tile_layer

    def load_layer(self, tree_location=None):
        if self.current_layer is None:
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
        self.geocoderProxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.geocoderProxyModel.setFilterFixedString(string)

    def toolbar_search_get_suggestions(self):
        def create_model(_suggestions):
            model = QStandardItemModel()
            for s in _suggestions:
                key = s["weergavenaam"]
                it = QStandardItem(key)
                it.setData(s, Qt.ItemDataRole.UserRole)
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
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
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
        data = item.data(Qt.ItemDataRole.UserRole)
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
            self.dlg.lookupinfo.setHtml("")
            self.dlg.geocoderResultSearchLabel.setEnabled(False)
            self.dlg.geocoderResultSearch.setEnabled(False)
            search_text = self.dlg.geocoder_search.text()
            if len(search_text) <= 1:
                return
            results = suggest_query(search_text, self.create_type_filter(), 50)
            if len(results) == 0:
                # ignore, as we are suggesting, maybe more characters will reveal something...
                return
            for result in results:
                adrestekst = QStandardItem(str(result["weergavenaam"]))
                adrestekst.setData(result, Qt.ItemDataRole.UserRole)
                type = QStandardItem(str(result["type"]))
                adrestekst.setData(result, Qt.ItemDataRole.UserRole)
                search_string = QStandardItem(
                    f'{str(result["weergavenaam"])} {str(result["type"])}'
                )
                self.geocoder_source_model.appendRow([adrestekst, type, search_string])
            self.geocoder_source_model.setHeaderData(0, Qt.Orientation.Horizontal, "Resultaat")
            self.geocoder_source_model.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
            self.geocoder_source_model.horizontalHeaderItem(0).setTextAlignment(
                Qt.AlignmentFlag.AlignLeft
            )
            self.dlg.geocoderResultView.resizeColumnsToContents()
            self.dlg.geocoderResultView.setColumnHidden(2, True)

            self.dlg.geocoderResultView.horizontalHeader().setStretchLastSection(True)
            self.dlg.geocoderResultSearchLabel.setEnabled(True)
            self.dlg.geocoderResultSearch.setEnabled(True)

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
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        strlist = string.strip().split(" ")
        string = ""
        for s in strlist:
            string += f"{s}.*"
        regexp = QRegularExpression(string, QRegularExpression.PatternOption.CaseInsensitiveOption | QRegularExpression.PatternOption.InvertedGreedinessOption)
        self.proxyModel.setFilterRegularExpression(regexp)
        self.proxyModel.insertRow

    def add_source_row(self, serviceLayer):
        # you can attache different "data's" to to an QStandarditem
        # default one is the visible one:
        stype = (
            self.service_type_mapping[serviceLayer["service_type"]]
            if serviceLayer["service_type"] in self.service_type_mapping
            else serviceLayer["service_type"].upper()
        )
        itemType = QStandardItem(str(stype))
        # userrole is a free form one:
        # only attach the data to the first item
        # service layer = a dict/object with all props of the layer
        itemType.setData(serviceLayer, Qt.ItemDataRole.UserRole)
        itemType.setToolTip(f'{stype} - {serviceLayer["title"]}')
        # only wms services have styles (sometimes)
        layername = serviceLayer["title"]
        styles_string = ""
        if "styles" in serviceLayer:
            styles_string = " ".join(
                [" ".join(x.values()) for x in serviceLayer["styles"]]
            )

        itemLayername = QStandardItem(str(serviceLayer["title"]))
        itemLayername.setToolTip(f'{stype} - {serviceLayer["service_title"]}')
        # itemFilter is the item used to search filter in. That is why layername is a combi of layername + filter here
        itemFilter = QStandardItem(
            f'{serviceLayer["service_type"]} {layername} {serviceLayer["service_title"]} {serviceLayer["service_abstract"]} {styles_string}'
        )
        itemServicetitle = QStandardItem(str(serviceLayer["service_title"]))
        itemServicetitle.setToolTip(f'{stype} - {serviceLayer["title"]}')
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
        return value.lower() == "true" if isinstance(value, str) else bool(value)

    def run(self, hiddenDialog=False):
        """
        run method that performs all the real work
        """
        # last viewed/selected tab
        if QSettings().contains(f"/{PLUGIN_ID}/currenttab"):
            self.dlg.tabs.widget(int(QSettings().value(f"/{PLUGIN_ID}/currenttab")))

        flashing_geoms = self.valueToBool(
            QSettings().value(f"/{PLUGIN_ID}/flashing_geoms", defaultValue=True)
        )
        #log.debug(f"{flashing_geoms=}")
        self.dlg.cb_flashing_geoms.setChecked(flashing_geoms)
        self.dlg.cb_yellow_cross.setChecked(not flashing_geoms)
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
            self.dlg.servicesView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

            self.geocoderProxyModel = QSortFilterProxyModel()
            self.geocoder_source_model = QStandardItemModel()

            self.geocoderProxyModel.setSourceModel(self.geocoder_source_model)
            self.geocoderProxyModel.setFilterKeyColumn(2)
            self.dlg.geocoderResultView.setModel(self.geocoderProxyModel)
            self.dlg.geocoderResultView.setEditTriggers(
                QAbstractItemView.EditTrigger.NoEditTriggers
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

            self.dlg.servicesView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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

        self.sourceModel.setHeaderData(2, Qt.Orientation.Horizontal, "Service")
        self.sourceModel.setHeaderData(1, Qt.Orientation.Horizontal, "Type")
        self.sourceModel.setHeaderData(0, Qt.Orientation.Horizontal, "Laagnaam")
        self.sourceModel.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.sourceModel.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.sourceModel.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
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

        for a_val, b_val in zip(a_list, b_list):
            if a_val > b_val:
                return True
        return a_list == b_list

    def show_ls_feature(self):
        """qgis supports "hidden" layers from QGIS version 3.18.0 and higher, see https://gis.stackexchange.com/a/230804. So only show locatie server feature instead of centroid from 3.18.0 and higher.

        Returns:
            bool: boolean indicating whether qgis supports "hidden" layers
        """
        semversion = qgis.utils.Qgis.QGIS_VERSION.split("-")[0]
        if self.semver_greater_or_equal_then(semversion, "3.18.0") and self.valueToBool(
            QSettings().value(f"/{PLUGIN_ID}/flashing_geoms")
        ):
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
        self.dlg.lookupinfo.setHtml(f"<lu>{result_list}</lu>")

    def remove_pointer_or_layer(self):
        if not self.show_ls_feature():
            self.remove_pointer()

    def lookup_dialog_search(self):
        self.remove_pointer_or_layer()
        if len(self.dlg.geocoderResultView.selectedIndexes()) == 0:
            return
        data = self.dlg.geocoderResultView.selectedIndexes()[0].data(Qt.ItemDataRole.UserRole)
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
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
        )

    def show_warning(self, message, title="PDOK plugin"):
        message = textwrap.dedent(
            message
        )  # textwrap.dedent nodig want anders leading whitespace issue, zie https://stackoverflow.com/a/1412728/1763690
        QMessageBox.warning(
            self.iface.mainWindow(),
            title,
            (message),
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
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

                action = menu.exec(self.dlg.servicesView.mapToGlobal(position))
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
                # when creating the menu, we ALSO have to take the current selected style AND current selected CRS
                # into account
                selected_style = self.get_selected_style()
                if selected_style is not None:
                    # this looks like a complex way to set selectedStyle in self.current_layer ???
                    # why not: self.current_layer["selectedStyle"] = selected_style ?
                    self.current_layer = {
                        **self.current_layer,
                        **{"selectedStyle": selected_style},
                    }
                selected_crs = self.get_crs_comboselect()
                if selected_crs is not None:
                    self.current_layer["selectedCrs"] = selected_crs
                add_fav_action = QAction(f"Voeg deze laag toe aan favorieten")
                add_fav_action.setIcon(self.fav_icon)
                menu.addAction(add_fav_action)
                action = menu.exec(self.dlg.servicesView.mapToGlobal(position))
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
            if layer:
                if layer and "selectedStyle" in fav_layer:
                    layer["selectedStyle"] = fav_layer["selectedStyle"]
                if layer and "selectedCrs" in fav_layer:
                    layer["selectedCrs"] = fav_layer["selectedCrs"]
                if migrate_fav:
                    QSettings().setValue(f"/{PLUGIN_ID}/favourite_{index}", layer)
                self.current_layer = layer
                self.load_layer()
                return
        # layer fav_layer not found, ask user to delete it, do NOT open the dialog (old behaviour)
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            "Geen Favoriet aanwezig (of verouderd)...",
            "Het lijkt erop dat deze Favoriet niet meer bestaat (bij PDOK). Uit uw Favorieten verwijderen?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        # if YES: clean it up from settings and update the toolbar actions
        if reply == QMessageBox.StandardButton.Yes:
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
