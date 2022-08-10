# -*- coding: utf-8 -*-
import os.path
import textwrap
import uuid
import re
import struct
import traceback
from math import floor
import email.parser
from osgeo import gdal
from requests.structures import CaseInsensitiveDict
from owslib.etree import etree
from owslib.coverage.wcs201 import WebCoverageService_2_0_1
from qgis.core import QgsMessageLog

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from PyQt5 import QtGui
from qgis.core import (
    QgsProject,
    QgsProcessing,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
)

from pdokservicesplugin.lib.util import (
    get_processing_error_message,
)

import logging
log = logging.getLogger(__name__)

from ..lib.http_client import get_request_bytes, PdokServicesNetworkException

# util methods for unpacking wcs response


def get_boundary(response):
    pattern = b"^\r\n(--.*)\r\n"
    m = re.search(pattern, response)
    if m:
        return m.group(1)
    return ""


def split_on_find(content, bound):
    point = content.find(bound)
    return content[:point], content[point + len(bound) :]


def encode_with(string, encoding):
    if not (string is None or isinstance(string, bytes)):
        return string.encode(encoding)
    return string


def header_parser(string, encoding):
    string = string.decode(encoding)
    headers = email.parser.HeaderParser().parsestr(string).items()
    return ((encode_with(k, encoding), encode_with(v, encoding)) for k, v in headers)


def parse_response(content):
    encoding = "utf-8"
    sep = get_boundary(content)
    parts = content.split(b"".join((b"\r\n", sep)))
    parts = parts[1:-1]
    result = []
    for part in parts:
        if b"\r\n\r\n" in part:
            first, body = split_on_find(part, b"\r\n\r\n")
            headers = header_parser(first.lstrip(), encoding)
            headers = CaseInsensitiveDict(headers)
            item = {}
            item["headers"] = headers
            item["content"] = body
            result.append(item)
    return result


# end - util methods for unpacking wcs response
# TODO: move code to lib folder


class PDOKWCSTool(QgsProcessingAlgorithm):
    """ """

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        # Must return a new copy of your algorithm.
        return PDOKWCSTool()

    def name(self):
        """
        Returns the unique algorithm name.
        """
        return "pdok-ahn3-wcs-tool"

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr("PDOK AHN3 WCS Tool")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr("AHN3")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs
        to.
        """
        return "pdok-ahn3"

    def icon(self):
        provider_path = os.path.dirname(__file__)
        plugin_path = os.path.dirname(provider_path)
        img_path = os.path.join(plugin_path, "resources", "icon_pdok.svg")

        icon = QtGui.QIcon(img_path)
        return icon

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr(
            textwrap.dedent(
                """
                Deze processing tool haalt hoogtedata op van de <a href="https://geodata.nationaalgeoregister.nl/ahn3/wcs?service=WCS&request=GetCapabilities">AHN3 WCS</a> service voor elk punt in de input-laag. De output is een puntenlaag met het toegevoegde hoogte attribuut. Wanneer voor een locatie in de AHN3 WCS een <tt>NODATA</tt> waarde wordt gevonden is de resulterende waarde in de outputlaag <tt>NULL</tt>.


                <h3>Parameters</h3>
                <dl>
                    <dt><b>Input point layer</b><dt>
                    <dd>input-laag met punten</dd>
                    <dt><b>CoverageId:</b></dt>
                    <dd>coverage om te bevragen, de AHN3 biedt verschillende coverages; voornaamste verschil is resolutie (5m vs 0.5m) en terrein (dtm) - vs oppervlaktemodel (dsm), zie de <a href="https://www.ahn.nl/kwaliteitsbeschrijving">AHN documentatie</a></dd>
                    <dt><b>Attribute name:</b></dt>
                    <dd>attribuutnaam om de hoogte op te slaan in de outputlaag</dd>
                    <dt><b>Output layer:</b></dt>
                    <dd>outputlaag met hoogteattribuut, projectie hetzelfde als de inputlaag</dd>
                </dl>
                """
            )
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and outputs of the algorithm.
        """
        try:
            self.INPUT = "INPUT"  # recommended name for the main input parameter
            self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter
            self.ATTRIBUTE_NAME = "ATTRIBUTE_NAME"
            self.COVERAGE_ID = "COVERAGE_ID"
            self.wcs_url = "https://geodata.nationaalgeoregister.nl/ahn3/wcs"
            self.cap_url = f"{self.wcs_url}?request=GetCapabilities&service=WCS"
            _xml_bytes = get_request_bytes(self.cap_url)
            self.wcs = WebCoverageService_2_0_1(self.wcs_url, _xml_bytes, None)

            _coverages = list(self.wcs.contents.keys())

            for cov in _coverages:
                desc_cov_url = f"{self.wcs_url}?request=DescribeCoverage&service=WCS&version=2.0.1&coverageId={cov}"
                desc_cov_resp = get_request_bytes(desc_cov_url)
                self.wcs._describeCoverage[cov] = etree.fromstring(desc_cov_resp)

            self.coverages = [item for item in _coverages]

            self.addParameter(
                QgsProcessingParameterFeatureSource(
                    self.INPUT,
                    self.tr("Input point layer"),
                    types=[QgsProcessing.TypeVectorPoint],
                )
            )
            self.addParameter(
                QgsProcessingParameterEnum(
                    self.COVERAGE_ID,
                    self.tr("CoverageId"),
                    options=self.coverages,
                    defaultValue=self.coverages.index(
                        "ahn3_05m_dtm"
                    ),  # sensible default? - although many nodata areas due to buildings
                    optional=False,
                )
            )
            self.addParameter(
                QgsProcessingParameterString(
                    self.ATTRIBUTE_NAME,
                    self.tr("Attribute name"),
                    defaultValue="elevation",
                    optional=True,
                )
            ),
            self.addParameter(
                QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Output layer"))
            )
        except Exception as e:
            # IF there is a network issue, the init of the algo would fail during the startup of QGIS, raising an exception
            # see: https://github.com/rduivenvoorde/pdokservicesplugin/issues/79
            # I choose to (silently) fail here, to be able to raise a QgsProcessingException when the user actually tries
            # to USE the algorithm
            log.debug(e)
            pass


    def processAlgorithm(self, parameters, context, feedback):
        # see above, it is possible that initing of the algo failed, we check here and let user know...
        if parameters == {}:
            raise QgsProcessingException("Er is iets misgegaan met het initialiseren van de input parameters.<br/>"
                                         "Misschien geen (werkende) internet verbinding?<br/>"
                                         "Dan kan namelijk de AHN service niet worden bereikt...<br/>"
                                         "Raadpleeg ook de MessageLog.")

        try:
            # read out parameters
            input_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            in_crs = input_layer.crs()
            attribute_name = parameters[self.ATTRIBUTE_NAME]
            coverage_id = [
                self.coverages[i]
                for i in self.parameterAsEnums(parameters, self.COVERAGE_ID, context)
            ][0]
            # start processing
            fields = input_layer.fields()
            fields.append(QgsField(attribute_name, QVariant.Double))
            field_names = [field.name() for field in fields]
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                input_layer.wkbType(),
                in_crs,
            )
            if feedback.isCanceled():
                return {}

            wcs_proj_authid = self.get_native_proj_authid(coverage_id)

            if in_crs.authid() != wcs_proj_authid:
                wcs_crs = QgsCoordinateReferenceSystem(wcs_proj_authid)
                transform_input = QgsCoordinateTransform(
                    in_crs, wcs_crs, QgsProject.instance()
                )
            for feature in input_layer.getFeatures():
                geom = feature.geometry()
                if in_crs.authid() != wcs_proj_authid:
                    geom.transform(transform_input)
                point_geom = QgsGeometry.asPoint(geom)
                point_xy = QgsPointXY(point_geom)
                x = point_xy.x()
                y = point_xy.y()
                attrs = feature.attributes()
                new_ft = QgsFeature(fields)
                for i in range(len(attrs)):
                    attr = attrs[i]
                    field_name = field_names[i]
                    new_ft.setAttribute(field_name, attr)
                ds = self.get_gdal_ds_from_wcs(x, y, coverage_id, feedback)
                nodata = self.get_nodata_from_gdal_ds(ds)
                ahn_val = self.get_val_from_gdal_ds(x, y, ds)
                ds = None

                if ahn_val == nodata:
                    fid = feature.id()
                    feedback.pushWarning(
                        f"NODATA value found for feature with id: {fid}, geom: POINT({x},{y})"
                    )
                    ahn_val = None
                new_ft.setAttribute(attribute_name, ahn_val)
                new_ft.setGeometry(geom)
                sink.addFeature(new_ft, QgsFeatureSink.FastInsert)
                if feedback.isCanceled():
                    return {}
            results = {}
            results[self.OUTPUT] = dest_id
            return results

        except PdokServicesNetworkException as ex:
            message = get_processing_error_message(
                "an error",
                self.displayName(),
                ex,
                traceback.format_exc(),
                "while executing HTTP request",
            )
            raise QgsProcessingException(message)
        except Exception as e:
            message = get_processing_error_message(
                "an unexpected error",
                self.displayName(),
                e,
                traceback.format_exc(),
            )
            raise QgsProcessingException(message)

    def get_gdal_ds_from_wcs(self, x, y, coverage_id, feedback):
        origin = [float(i) for i in self.wcs.contents[coverage_id].grid.origin]
        cell_size = float(self.wcs.contents[coverage_id].grid.offsetvectors[0][0])
        x_lower_bound = origin[0] + (((x - origin[0]) // cell_size) * cell_size)
        x_upper_bound = x_lower_bound + (2 * cell_size)
        y_lower_bound = origin[1] + (((y - origin[1]) // cell_size) * cell_size)
        y_upper_bound = y_lower_bound + (2 * cell_size)
        url = f"{self.wcs_url}?service=WCS&Request=GetCoverage&version=2.0.1&CoverageId={coverage_id}&format=image/tiff&subset=x({x_lower_bound},{x_upper_bound})&subset=y({y_lower_bound},{y_upper_bound})"
        feedback.pushInfo(f"WCS GetCoverage url: {url}")
        response_body = get_request_bytes(url)
        multipart_data = parse_response(response_body)
        for part in multipart_data:
            if part["headers"][b"content-type"] == b"image/tiff":
                coverage = part["content"]
        uuid_string = str(uuid.uuid4())
        tif_file_name = f"/vsimem/{uuid_string}.tif"
        gdal.UseExceptions()
        gdal.FileFromMemBuffer(tif_file_name, coverage)
        ds = gdal.Open(tif_file_name)
        return ds

    def get_nodata_from_gdal_ds(self, ds):
        band = ds.GetRasterBand(1)  # assuming single band raster
        nodata = band.GetNoDataValue()
        band = None
        return nodata

    def log_message(self, message, loglevel=0):
        """loglevel:
        Info
        Warning
        Critical
        Success
        None"""
        QgsMessageLog.logMessage(
            message,
            self.displayName(),
            loglevel,
        )

    def get_val_from_gdal_ds(self, x, y, ds):
        band = ds.GetRasterBand(1)  # assuming single band raster
        gt = ds.GetGeoTransform()
        px = floor((x - gt[0]) / gt[1])
        py = floor((y - gt[3]) / gt[5])
        structval = band.ReadRaster(px, py, 1, 1, buf_type=gdal.GDT_Float32)
        floatval = struct.unpack("f", structval)
        band = None
        gt = None
        return floatval[0]

    def get_native_proj_authid(self, coverage_id):
        coverage = self.wcs.contents[coverage_id]
        proj_string = coverage.boundingboxes[0]["nativeSrs"]
        # http://www.opengis.net/def/crs/EPSG/0/28992
        p = re.compile("^.*\/(.*?)\/.*?\/(.*)$")
        m = p.match(proj_string)
        if not m:
            raise ValueError("unable to extract EPSG code from {proj_string}")
        auth = m.group(1)
        identifier = m.group(2)
        return f"{auth}:{identifier}"
