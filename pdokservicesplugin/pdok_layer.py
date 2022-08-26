from qgis.core import QgsMapLayer
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
import urllib.request, urllib.parse, urllib.error
from .constants import PLUGIN_NAME
from .util import show_error

import logging

log = logging.getLogger(__name__)


class ServiceTypeNotSupportedException(Exception):
    pass


class LayerManager:
    def __init__(self, iface):
        self._iface = iface

    def _quote_wmts_url(self, url):
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

    def get_bookmark_title(self, pdok_config_layer):
        title = pdok_config_layer["title"]
        if pdok_config_layer["service_type"] == "wms":
            if "selectedStyle" in pdok_config_layer:
                selected_style = pdok_config_layer["selectedStyle"]
                if selected_style is not None:
                    selected_style_title = selected_style["name"]
                    if "title" in selected_style:
                        selected_style_title = selected_style["title"]
                title = f'{pdok_config_layer["title"]} [{selected_style_title}]'
        stype = pdok_config_layer["service_type"].upper()
        return f"{title} ({stype})"

    def _create_qgsmaplayer_from_pdok_layer(
        self, pdok_config_layer, crs
    ) -> QgsMapLayer:
        def _func_dict():
            return {
                "wms": _create_wms_layer,
                "wcs": _create_wcs_layer,
                "wfs": _create_wfs_layer,
                "wmts": _create_wmts_layer,
            }

        def _create_wms_layer():
            imgformat = pdok_config_layer["imgformats"].split(",")[0]

            selected_style_name = ""
            if "selectedStyle" in pdok_config_layer:
                _selected_style = pdok_config_layer["selectedStyle"]
            if _selected_style is not None:
                selected_style_name = _selected_style["name"]

            _title = self.get_bookmark_title(pdok_config_layer)
            uri = f"crs={crs}&layers={layername}&styles={selected_style_name}&format={imgformat}&url={url}"
            return QgsRasterLayer(uri, _title, "wms")

        def _create_wmts_layer():
            quoted_url = self._quote_wmts_url(url)
            tilematrixset = crs
            imgformat = pdok_config_layer["imgformats"].split(",")[0]
            if tilematrixset.startswith("EPSG:"):
                crs_param = tilematrixset
                i = crs_param.find(":", 5)
                if i > -1:
                    crs_param = crs_param[:i]
            elif tilematrixset.startswith("OGC:1.0"):
                crs_param = "EPSG:3857"
            uri = f"tileMatrixSet={tilematrixset}&crs={crs_param}&layers={layername}&styles=default&format={imgformat}&url={quoted_url}"
            return QgsRasterLayer(
                uri, title, "wms"
            )  # `wms` is correct, zie ook quote_wmts_url

        def _create_wcs_layer():
            # HACK to be able to make WCS working for now:
            # 1) fixed format to "GEOTIFF_FLOAT32"
            # 2) remove the '?request=getcapabiliteis....' part from the url
            # But service is rather slow, maybe better to remove the WCS part from the plugin?q
            # normally you would do a DescribeCoverage to find out about the format etc etc
            format = "GEOTIFF_FLOAT32"
            uri = f"cache=AlwaysNetwork&crs=EPSG:28992&format={format}&identifier={layername}&url={url.split('?')[0]}"
            return QgsRasterLayer(uri, title, "wcs")

        def _create_wfs_layer():
            uri = f" pagingEnabled='true' restrictToRequestBBOX='1' srsname='EPSG:28992' typename='{layername}' url='{url}' version='2.0.0'"
            return QgsVectorLayer(uri, title, "wfs")

        layername = pdok_config_layer["name"]
        url = pdok_config_layer["service_url"]
        title = pdok_config_layer["title"]
        service_type = pdok_config_layer["service_type"]

        if service_type not in ["wcs", "wms", "wfs", "wmts"]:
            raise ServiceTypeNotSupportedException(
                f"service type {service_type} is not supported by the PDOK Services Plugin"
            )

        fun = _func_dict()[service_type]
        return fun()

    def load_layer(self, pdok_config_layer, crs="EPSG:28992", tree_location=None):
        default_tree_locations = {
            "wms": "top",
            "wmts": "bottom",
            "wfs": "top",
            "wcs": "top",
        }
        if pdok_config_layer == None:
            return
        servicetype = pdok_config_layer["service_type"]
        if tree_location is None:
            tree_location = default_tree_locations[servicetype]
        try:
            map_layer = self._create_qgsmaplayer_from_pdok_layer(pdok_config_layer, crs)
            if map_layer is None:
                return
            self.add_layer(map_layer, tree_location)
        except ServiceTypeNotSupportedException as ex:
            title = f"{PLUGIN_NAME} - Error adding layer"
            message = f"{str(ex)}"
            show_error(message, title)

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
        layer_tree = self._iface.layerTreeCanvasBridge().rootGroup()
        if tree_location == "top":
            layer_tree.insertChildNode(0, new_layer_tree_layer)
        if tree_location == "bottom":
            layer_tree.insertChildNode(-1, new_layer_tree_layer)
