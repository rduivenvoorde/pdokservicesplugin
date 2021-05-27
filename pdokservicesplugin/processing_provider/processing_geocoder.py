# -*- coding: utf-8 -*-

"""pdok-geocoder.py: QGIS Processing tool for geocoding with the PDOK \
Locatieserver. Tested with QGIS version 3.16, but will probably work with any \
3.X version."""

import traceback
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProject,
    QgsProcessing,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsFeature,
    QgsUnitTypes,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField,
)
from PyQt5 import QtGui
import re

from pdok_services.locatieserver import (
    LsType,
    TypeFilter,
    Projection,
    lookup_object,
    free_query,
)


class PDOKGeocoder(QgsProcessingAlgorithm):
    """
    This processing tool queries the PDOK Locatieserver fe geocoder service for each point in the input
    layer and adds the first result to the target attribute.
    """

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        # Must return a new copy of your algorithm.
        return PDOKGeocoder()

    def name(self):
        """
        Returns the unique algorithm name.
        """
        return "pdok-geocoder"

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr("PDOK Geocoder")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr("Locatie Server")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs
        to.
        """
        return "pdok-locatie-server"

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = ":/plugins/pdok_services/icon.png"
        icon = QtGui.QIcon(icon_path)
        return icon

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr(
            'This is processing tool queries the PDOK Locatieserver (PDOK-LS) geocoder service for each\
            feature in the input layer, with the target attribute of the feature. The geometry returned by the PDOK-LS will be added to the output layer. Layers without geometry such as CSV and XSLX based layers are also suported. Existing attributes will be overwritten in the output layer. To query based on\
            postcode and house number, ensure your input data conforms to this format:\n\n\
            <pre><code>{postcode} {house-nr}</pre></code>\n\
            For example "6821BN 40-2" (note the space between postcode and housenumber).\n\n\
            See also the PDOK Locatieserver API <a href="https://github.com/PDOK/locatieserver/wiki/API-Locatieserver">documentation</a>\n\
            Parameters:\n\n\
            <ul><li><b>Input layer:</b> for each feature the PDOK-LS geocoder service will be queried</li>\
            <li><b>Geocode attribute:</b> attribute in input layer to query PDOK-LS with</li>\
            <li><b>Geocode result type</b></li>\
            <li><b>Target CRS:</b> CRS of the resulting output layer</li>\
            <li><b>Retrieve actual geometry (instead of centroid):</b> default value: false, will return higher order geometry type if available (depends on <em>Geocode result type</em>)</li>\
            <li><b>Add x and Y attribute:</b> default value: false, add "x" and "y" attributes to the output layer containing \ the geometry centroid coordinates\
            <li><b>Add "weergavenaam" (display name) attribute: </b>, default value false, add "weergavenaam" attribute to the output layer</li>\
            <li><b>Score treshold [optional]:</b> objects returned by the PDOK-LS geocoder each have a score, \
            to indicate how well they match with the query. Results with a score lower than the treshold \
            are excluded</li>\
            <li><b>Output layer:</b> resulting output layer</li></ul>'
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and outputs of the algorithm.
        """
        self.predicates = [
            (ls_type.value, self.tr(ls_type.value)) for ls_type in LsType
        ]

        self.TARGET_CRS = "TARGET_CRS"
        self.INPUT = "INPUT"  # recommended name for the main input parameter
        self.ADD_XY_FIELD = "ADD_XY_FIELD"
        self.SRC_FIELD = "SRC_FIELD"
        self.RESULT_TYPE = "RESULT_TYPE"
        self.SCORE_TRESHOLD = "SCORE_TRESHOLD"
        self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter
        self.ADD_DISPLAY_NAME = "ADD_DISPLAY_NAME"
        self.GET_ACTUAL_GEOM = "GET_ACTUAL_GEOM"

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                types=[QgsProcessing.TypeFile],
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.SRC_FIELD,
                self.tr("Geocode attribute"),
                None,
                "INPUT",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RESULT_TYPE,
                self.tr("Geocode result type"),
                options=[p[1] for p in self.predicates],
                defaultValue=0,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Output layer"))
        )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.TARGET_CRS, self.tr("Target CRS"), "EPSG:28992"
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GET_ACTUAL_GEOM,
                self.tr("Retrieve actual geometry (instead of centroid)"),
                False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_XY_FIELD, self.tr("Add x and Y attribute"), False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_DISPLAY_NAME,
                self.tr('Add "weergavenaam" (display name) attribute'),
                False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SCORE_TRESHOLD,
                self.tr("Score treshold"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=None,
                optional=True,
                minValue=0,
            )
        )

    def get_geom(self, get_actual_geom, result_type, data, feedback):
        """
        Returns a geometry depending on get_actual_geom boolean.
        If false: return geom based on "centroide_ll" from the data
        If true: retrieve the actual object from the lookup service and
        return the geom based on "geometrie_ll" from the lookup response
        """
        if not get_actual_geom or result_type in ["adres", "postcode"]:
            wkt_point = data[0]["wkt_geom"]
            return QgsGeometry.fromWkt(wkt_point)
        else:
            ls_id = wkt_point = data[0]["id"]
            data = lookup_object(ls_id, Projection.EPSG_28992)
            if data is None:
                raise QgsProcessingException(f"Failed to lookup object with id {ls_id}")
            wkt_geom = data["wkt_geom"]
            return QgsGeometry.fromWkt(wkt_geom)

    def processAlgorithm(self, parameters, context, feedback):
        try:
            # read out parameters
            input_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            out_crs = parameters[self.TARGET_CRS]
            result_type_str = [
                self.predicates[i][0]
                for i in self.parameterAsEnums(parameters, self.RESULT_TYPE, context)
            ][0]
            result_type = LsType[result_type_str]
            score_treshold = parameters[self.SCORE_TRESHOLD]
            add_xy_field = parameters[self.ADD_XY_FIELD]
            add_display_name = parameters[self.ADD_DISPLAY_NAME]
            src_field = parameters[self.SRC_FIELD]
            get_actual_geom = parameters[self.GET_ACTUAL_GEOM]

            # start processing
            transform = None
            fields = input_layer.fields()
            field_names = [field.name() for field in fields]

            if add_xy_field:
                fields.append(QgsField("x", QVariant.Double))
                fields.append(QgsField("y", QVariant.Double))

            display_name_att_name = "weergavenaam"
            if add_display_name:
                fields.append(QgsField(display_name_att_name, QVariant.String))

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                result_type.geom_type(),
                out_crs,
            )

            if feedback.isCanceled():
                return {}

            for feature in input_layer.getFeatures():

                # TODO: check if src_field value is None if so skip feature
                src_field_val = feature.attribute(src_field)
                if src_field_val is None:
                    continue

                # TODO: error handling from LS lib
                # maybe raise error:
                # raise QgsProcessingException(
                #     f"Unexpected response from HTTP GET {url}, response code: {response.status_code}"
                # )

                # check if src_field_val matches postcode in format exactly "9090AA 20-a"
                # TODO: make explicit behind option?
                match = re.search("^([0-9]{4}[A-Za-z]{2})\s(.*)$", src_field_val)
                if match and len(match.groups()) == 2:
                    postal_code = match.group(1)
                    house_nr = match.group(2)
                    src_field_val = f"postcode:{postal_code} and huisnummer:{house_nr}"

                # feedback.pushInfo(f"src_field: {src_field}")

                data = free_query(
                    src_field_val, Projection.EPSG_28992, TypeFilter([result_type])
                )

                geom = None
                display_name = ""
                if len(data) > 0:
                    if score_treshold != None and data[0]["score"] <= score_treshold:
                        geom = None
                    else:
                        geom = self.get_geom(
                            get_actual_geom, result_type, data, feedback
                        )
                        display_name = data[0]["weergavenaam"]

                if geom:
                    attrs = feature.attributes()
                    new_ft = QgsFeature(fields)

                    for i in range(len(attrs)):
                        attr = attrs[i]
                        field_name = field_names[i]
                        new_ft.setAttribute(field_name, attr)

                    in_crs = QgsCoordinateReferenceSystem.fromEpsgId(28992)

                    if out_crs.authid() != "EPSG:28992":
                        transform = QgsCoordinateTransform(
                            in_crs, out_crs, QgsProject.instance()
                        )
                        geom.transform(transform)

                    if add_xy_field:
                        point_geom = QgsGeometry.asPoint(geom.centroid())
                        pxy = QgsPointXY(point_geom)
                        x = pxy.x()
                        y = pxy.y()
                        new_ft.setAttribute("x", x)
                        new_ft.setAttribute("y", y)

                    if add_display_name:
                        new_ft.setAttribute(display_name_att_name, display_name)

                    new_ft.setGeometry(geom)
                    sink.addFeature(new_ft, QgsFeatureSink.FastInsert)

                if feedback.isCanceled():
                    return {}

            results = {}
            results[self.OUTPUT] = dest_id
            return results
        except Exception as e:
            traceback_str = traceback.format_exc()
            raise QgsProcessingException(
                f"Unexpected error occured while running PDOKGeocoder: {str(e)} - {traceback_str}"
            )
