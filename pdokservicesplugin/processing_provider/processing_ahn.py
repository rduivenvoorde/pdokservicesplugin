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


class PDOKWCSTool(QgsProcessingAlgorithm):
    """ """

    wcs_url = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
    cap_url = f"{wcs_url}?request=GetCapabilities&service=WCS"
    coverages = [ "dtm_05m", "dsm_05m"]
    default_coverage = coverages[0]


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
        return "pdok-ahn-wcs-tool"

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr("PDOK AHN WCS Tool")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr("AHN")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs
        to.
        """
        return "pdok-ahn"

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
                f"""
                Deze processing tool haalt hoogtedata op van de <a href="https://service.pdok.nl/rws/ahn/wcs/v1_0?request=GetCapabilities&service=WCS">AHN WCS</a> service voor elk punt in de input-laag. De output is een puntenlaag met het toegevoegde hoogte attribuut. Wanneer voor een locatie in de AHN WCS een <tt>NODATA</tt> waarde wordt gevonden is de resulterende waarde in de outputlaag <tt>NULL</tt>.

                <h3>Metadata</h3>
                <dl>
                    <dt><b>Dataset metadata</b><dt>
                    <dd><a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/41daef8b-155e-4608-b49c-c87ea45d931g" >Actueel Hoogtebestand Nederland DSM</a></dd>
                    <dd><a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/41daef8b-155e-4608-b49c-c87ea45d931c" >Actueel Hoogtebestand Nederland DTM</a></dd>
                    <dt><b>Service metadata</b><dt>
                    <dd><a href="https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/bfcc588f-9393-4c70-b989-d9e92ac2f493" >Actueel Hoogtebestand Nederland (AHN) WCS</a></dd>
                </dl>
                              

                <h3>Parameters</h3>
                <dl>
                    <dt><b>Input point layer</b><dt>
                    <dd>input-laag met punten</dd>
                    <dt><b>CoverageId:</b></dt>
                    <dd>coverage om te bevragen, de AHN biedt twee coverages: {", ".join(PDOKWCSTool.coverages)} (een terrein- (dtm) vs oppervlaktemodel (dsm), zie de <a href="https://www.ahn.nl/kwaliteitsbeschrijving">AHN documentatie)</a></dd>
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
                    options=PDOKWCSTool.coverages,
                    defaultValue=PDOKWCSTool.coverages.index(
                        PDOKWCSTool.default_coverage
                    ),
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
            raise QgsProcessingException(
                "Er is iets misgegaan met het initialiseren van de input parameters.<br/>"
                "Misschien geen (werkende) internet verbinding?<br/>"
                "Dan kan namelijk de AHN service niet worden bereikt...<br/>"
                "Raadpleeg ook de MessageLog."
            )

        try:
            # retrieve wcs object
            _xml_bytes = get_request_bytes(PDOKWCSTool.cap_url)
            self.wcs = WebCoverageService_2_0_1(PDOKWCSTool.wcs_url, _xml_bytes, None)
            
            for cov in PDOKWCSTool.coverages:
                desc_cov_url = f"{PDOKWCSTool.wcs_url}?request=DescribeCoverage&service=WCS&version=2.0.1&coverageId={cov}"
                desc_cov_resp = get_request_bytes(desc_cov_url)
                self.wcs._describeCoverage[cov] = etree.fromstring(desc_cov_resp) # _describeCoverage is cache for DescribeCoverage responses => https://github.com/geopython/OWSLib/blob/0eaf201d587e42237415f0010e8940275cd50ba8/owslib/coverage/wcsBase.py#LL53C37-L53C37
                # so by filling cache, we ensure owslib does not retrieve describecoverage docs, but we do it ourselves

            # read out parameters
            input_source = self.parameterAsSource(parameters, self.INPUT, context)
            in_crs = input_source.sourceCrs()
            attribute_name = parameters[self.ATTRIBUTE_NAME]

            coverage_id = [
                self.coverages[i]
                for i in self.parameterAsEnums(parameters, self.COVERAGE_ID, context)
            ][0]
            # start processing
            fields = input_source.fields()
            fields.append(QgsField(attribute_name, QVariant.Double))
            field_names = [field.name() for field in fields]
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                input_source.wkbType(),
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
            for feature in input_source.getFeatures():
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

                if ds is None:
                    ahn_val = None
                else:
                    nodata = self.get_nodata_from_gdal_ds(ds)
                    ahn_val = self.get_val_from_gdal_ds(x, y, ds)
                    ds = None

                if ahn_val == nodata or ahn_val == None:
                    fid = feature.id()
                    feedback.pushWarning(
                        f"NODATA value found for feature with id: {fid}, geom: POINT({x},{y})"
                    )
                    ahn_val = None
                else:
                    ahn_val = round(ahn_val, 2) # reduce precision to 2 digits after the decimal point
                    
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
        """returns none when x,y outside coverage boundingbox
        """
        (minx,miny,maxx,maxy) = self.wcs.contents[coverage_id].boundingboxes[0]['bbox'] # assuming boundingboxes[0] contains nativeproj bounding box
        if x < minx or x > maxx or y < miny or y > maxy:
            return None
        origin = [float(i) for i in self.wcs.contents[coverage_id].grid.origin]
        cell_size = float(self.wcs.contents[coverage_id].grid.offsetvectors[0][0])
        x_lower_bound = origin[0] + (((x - origin[0]) // cell_size) * cell_size)
        x_upper_bound = x_lower_bound + (2 * cell_size)
        y_lower_bound = origin[1] + (((y - origin[1]) // cell_size) * cell_size)
        y_upper_bound = y_lower_bound + (2 * cell_size)
        url = f"{self.wcs_url}?service=WCS&Request=GetCoverage&version=2.0.1&CoverageId={coverage_id}&format=image/tiff&subset=x({x_lower_bound},{x_upper_bound})&subset=y({y_lower_bound},{y_upper_bound})"
        feedback.pushInfo(f"WCS GetCoverage url: {url}")
        response_body = get_request_bytes(url, "image/tiff")
        uuid_string = str(uuid.uuid4())
        tif_file_name = f"/vsimem/{uuid_string}.tif"
        gdal.UseExceptions()
        gdal.FileFromMemBuffer(tif_file_name, response_body)
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
        p = re.compile(r"^.*/(.*?)/.*?/(.*)$")
        m = p.match(proj_string)
        if not m:
            raise ValueError("unable to extract EPSG code from {proj_string}")
        auth = m.group(1)
        identifier = m.group(2)
        return f"{auth}:{identifier}"
