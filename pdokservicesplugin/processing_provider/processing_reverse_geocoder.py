# -*- coding: utf-8 -*-

"""pdok-reverse-geocoder.py: QGIS Processing tool for reverse geocoding with the PDOK \
   Locatieserver. Tested with QGIS version 3.16, but will probably work with any \
   3.X version.
"""
import sys, traceback
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
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
)
from PyQt5 import QtGui

from qgis import processing

from pdok_services.locatieserver import (
    LsType,
    reverse_lookup,
    TypeFilter,
    Projection,
    lookup_object,
    free_query,
)


class PDOKReverseGeocoder(QgsProcessingAlgorithm):
    """
    This processing tool queries the PDOK Locatieserver reverse geocoder service for each point in the input
    layer and adds the first result to the target attribute.
    """

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        # Must return a new copy of your tool.
        return PDOKReverseGeocoder()

    def name(self):
        """
        Returns the unique tool name.
        """
        return "pdok-reverse-geocoder"

    def displayName(self):
        """
        Returns the translated tool name.
        """
        return self.tr("PDOK Reverse Geocoder")

    def group(self):
        """
        Returns the name of the group this tool belongs to.
        """
        return self.tr("Locatie Server")

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        icon_path = ":/plugins/pdok_services/icon.png"
        icon = QtGui.QIcon(icon_path)
        return icon

    def groupId(self):
        """
        Returns the unique ID of the group this tool belongs
        to.
        """
        return "pdok-locatie-server"

    def shortHelpString(self):
        """
        Returns a localised short help string for the tool.
        """
        return self.tr(
            'This processing tool queries the PDOK Locatieserver (PDOK-LS) reverse geocoder service for each\
            point in the input layer and adds the selected fields of the reverse geocoder result to the point.\n\n\
            See also the PDOK Locatieserver reverse geocoding API <a href="https://github.com/PDOK/locatieserver/wiki/API-Reverse-Geocoder">documentation</a> \n\
            Parameters:\n\n\
            <ul><li><b>Input point layer:</b> for each point the PDOK-LS reverse geocoder service will be queried</li>\
            <li><b>Fields:</b> fields to add to input point layer from reverse geocoder response, defaults to "weergavenaam" \
            (note that in the resulting output weergavenaam is remapped to "weergavenaam_{result_type}")</li>\
            <li><b>Result type to query</b></li>\
            <li><b>Score treshold, optional:</b> objects returned by the PDOK-LS geocoder each have a score, \
            to indicate how well they match the query. Results with a score lower than the treshold \
            are excluded</li>\
            <li><b>Output point layer:</b> output layer with fields added from the PDOK-LS reverse geocoder \
            response, projection same as input point layer</li></ul>\
            '
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and outputs of the tool.
        """

        self.predicates = [
            (ls_type.value, self.tr(ls_type.value)) for ls_type in LsType
        ]
        self.INPUT = "INPUT"  # recommended name for the main input parameter
        self.FIELDS = "FIELDS"
        self.RESULT_TYPE = "RESULT_TYPE"
        self.DISTANCE_TRESHOLD = "DISTANCE_TRESHOLD"
        self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input point layer"),
                types=[QgsProcessing.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, self.tr("Output point layer")
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.FIELDS,
                self.tr("Fields (comma seperated list)"),
                defaultValue="weergavenaam",
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RESULT_TYPE,
                self.tr("Result type to query"),
                options=[p[1] for p in self.predicates],
                defaultValue=0,
                optional=False,
            )
        )
        dist_param = QgsProcessingParameterDistance(
            self.DISTANCE_TRESHOLD,
            self.tr("Score treshold"),
            defaultValue=None,
            optional=True,
            minValue=0,
        )
        dist_param.setDefaultUnit(QgsUnitTypes.DistanceMeters)
        self.addParameter(dist_param)

    def processAlgorithm(self, parameters, context, feedback):
        try:
            # read out algorithm parameters
            input_points = self.parameterAsVectorLayer(parameters, self.INPUT, context)
            distance_treshold = parameters[self.DISTANCE_TRESHOLD]
            result_type_str = [
                self.predicates[i][0]
                for i in self.parameterAsEnums(parameters, self.RESULT_TYPE, context)
            ][0]
            result_type = LsType[result_type_str]
            input_fields = [x.strip() for x in parameters[self.FIELDS].split(",")]
            input_layer_fields = input_points.fields()
            input_layer_fields_names = [field.name() for field in input_layer_fields]
            field_mapping = {}

            for input_field in input_fields:
                mapped_field_name = input_field
                if input_field == "weergavenaam":
                    mapped_field_name = f"weergavenaam_{result_type.value}"
                # TODO: improve field mapping, since no check if ls_{input_field} exists
                # in input_layer_fields_names
                if mapped_field_name in input_layer_fields_names:
                    mapped_field_name = f"ls_{input_field}"
                field_mapping[input_field] = mapped_field_name

            for input_field in input_fields:
                input_layer_fields.append(
                    QgsField(field_mapping[input_field], QVariant.String)
                )

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                input_layer_fields,
                QgsWkbTypes.Point,
                input_points.sourceCrs(),
            )

            # Setup transformation if required
            in_crs = input_points.crs()
            out_crs = QgsCoordinateReferenceSystem.fromEpsgId(28992)
            transform = None
            if in_crs.authid() != "EPSG:28992":
                transform = QgsCoordinateTransform(
                    in_crs, out_crs, QgsProject.instance()
                )

            if feedback.isCanceled():
                return {}

            # start processing features
            for point in input_points.getFeatures():
                geom = point.geometry()
                fid = point.id()
                if transform:
                    geom.transform(transform)

                point_geom = QgsGeometry.asPoint(geom)
                pxy = QgsPointXY(point_geom)
                x = pxy.x()
                y = pxy.y()

                # afstand field required, add if not requested by user
                if "afstand" not in input_fields:
                    input_fields.append("afstand")
                data = reverse_lookup(x, y, input_fields, TypeFilter([result_type]))
                # TODO: add exception handling reverse_lookup

                result = None
                if len(data) > 0:
                    if (
                        distance_treshold != None
                        and data[0]["afstand"] > distance_treshold
                    ):
                        distance = data[0]["afstand"]
                        feedback.pushInfo(
                            f"feature id: {fid} - distance treshold ({distance_treshold}) exceeded: {distance}"
                        )
                        pass
                    else:
                        result = {}
                        for key in field_mapping:
                            if key in data[0]:
                                result[key] = data[0][key]
                            else:
                                feedback.pushInfo(
                                    f'feature id: {fid} - field "{key}" not in response'
                                )
                else:
                    feedback.pushInfo(
                        f"feature id: {fid} - no objects found for x,y ({x},{y}) with result_type: {result_type.value}"
                    )

                attrs = point.attributes()
                new_ft = QgsFeature(input_layer_fields)

                for i in range(len(attrs)):
                    attr = attrs[i]
                    field_name = input_layer_fields_names[i]
                    new_ft.setAttribute(field_name, attr)

                for key in result:
                    new_ft.setAttribute(field_mapping[key], result[key])

                new_ft.setGeometry(point.geometry())
                sink.addFeature(new_ft, QgsFeatureSink.FastInsert)

                if feedback.isCanceled():
                    return {}

            results = {}
            results[self.OUTPUT] = dest_id
            return results
        except Exception as e:
            traceback_str = traceback.format_exc()
            raise QgsProcessingException(
                f"Unexpected error occured while running PDOKReverseGeocoder: {str(e)} - {traceback_str}"
            )
