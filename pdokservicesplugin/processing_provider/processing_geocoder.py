# -*- coding: utf-8 -*-

"""pdok-geocoder.py: QGIS Processing tool for geocoding with the PDOK \
Locatieserver. Tested with QGIS version 3.16, but will probably work with any \
3.X version."""

import textwrap
import traceback
import re
import os.path

from PyQt5 import QtGui
from PyQt5.QtCore import QCoreApplication, QVariant

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
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField,
    NULL,
)

from pdokservicesplugin.lib.util import (
    get_processing_error_message,
)

from pdokservicesplugin.lib.http_client import PdokServicesNetworkException

from ..lib.locatieserver import (
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
                Dit is een processing tool die de PDOK LocatieServer geocodeer service bevraagd  voor elke feature in de input laag met het target attribuut. De geometrie uit het antwoord van de geocodeer service zal worden toegevoegd aan de output laag. Lagen zonder geometrieën zoals CSV en XSLX gebaseerd lagen worden ook ondersteund. Bestaande attributen worden overschreven in de output laag. Om op postcode en huisnummer te bevragen dient de input data aan het volgende format te voldoen:

                <pre><code>{postcode} {huisnr}</pre></code>

                Bij voorbeeld: <em><tt>"6821BN 40-2"</tt></em> (zonder aanhalingstekens, merk op dat de huisnummer en postcode gescheiden zijn met een enkele spatie).

                Zie ook de PDOK Locatieserver API <a href="https://github.com/PDOK/locatieserver/wiki/API-Locatieserver">documentatie</a>.

                <h3>Parameters</h3>
                <dl>
                    <dt><b>Input layer</b></dt>
                    <dd>voor elke feature in de input laag wordt de geocoder service bevraagd</dd>
                    <dt><b>Geocode attribute</b></dt>
                    <dd>attribuut in input laag om de geocoder service mee te bevragen</dd>
                    <dt><b>Geocode result type</b></dt>
                    <dd>Locatieserver result type om te bevragen</dd>
                    <dt><b>Target CRS</b></dt>
                    <dd>CRS van de outputlaag</dd>
                    <dt><b>Retrieve actual geometry (instead of centroid)</b> - <em>default value: <tt>false</tt></em></dt>
                    <dd>daadwerkelijke geometry ophalen in plaats van centroïde indien beschikbaar (hangt af <em>Geocode result type</em>)</dd>
                    <dt><b>Add x and Y attribute</b> - <em>default value: <tt>false</tt></em></dt>
                    <dd>voeg <tt>gc_x</tt> and <tt>gc_y</tt> attributen aan de outputlaag die de coördinaten van de centroïde bevatten</dd>
                    <dt><b>Add <tt>weergavenaam</tt> (display name) attribute</b> - <em>default value: <tt>false</tt></em></dt>
                    <dd>voeg <tt>gc_naam</tt> attribuut toe aan de outputlaag, met het <tt>weergavenaam</tt> veld uit het geocoder resultaat</dd>
                    <dt><b>Add score attribute</b> - <em>default value: <tt>false</tt></em></dt>
                    <dd>voeg <tt>gc_score</tt> attribuut toe aan de outputlaag, met het <tt>score</tt> veld uit het geocoder resultaat</dd>
                    <dt><b>Add dummy geometry</b> - <em>default value: <tt>false</tt></dt>
                    <dd>voeg dummy features toe (in de buurt van <tt>0,0</tt>) voor niet gevonden locaties, anders worden deze locaties niet meegenomen in het resultaat. Dit kan handig zijn voor het naderhand handmatig verplaatsten van deze features.</dd>
                    <dt><b>Score threshold [optional]</b></dt>
                    <dd>resultaten van de geocoder bevatten een score, die een indicatie geven van hoe goed het resultaat matcht met de query, resultaten met een score lager dan de score threshold worden achterwege gelaten</dd>
                    <dt><b>Output layer</b></dt>
                    <dd>outputlaag met het resultaat van de geocoder</dd>
                </dl>
                """
            )
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
        self.SCORE_THRESHOLD = "SCORE_THRESHOLD"
        self.OUTPUT = "OUTPUT"  # recommended name for the main output parameter
        self.ADD_DISPLAY_NAME = "ADD_DISPLAY_NAME"
        self.GET_ACTUAL_GEOM = "GET_ACTUAL_GEOM"
        self.ADD_DUMMY_GEOMETRY = "ADD_DUMMY_GEOMETRY"
        self.ADD_SCORE_FIELD = "ADD_SCORE_FIELD"

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
                self.ADD_XY_FIELD, self.tr("Add x and y attribute"), False
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
            QgsProcessingParameterBoolean(
                self.ADD_SCORE_FIELD,
                self.tr("Add score attribute"),
                False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_DUMMY_GEOMETRY,
                self.tr("Add dummy geometry (near 0,0) for not found locations"),
                False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SCORE_THRESHOLD,
                self.tr("Score threshold"),
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
        feedback.setProgress(0)
        try:
            # read out parameters
            input_layer = self.parameterAsSource(parameters, self.INPUT, context)
            feedback.pushDebugInfo(str(input_layer))
            out_crs = parameters[self.TARGET_CRS]
            result_type_str = [
                self.predicates[i][0]
                for i in self.parameterAsEnums(parameters, self.RESULT_TYPE, context)
            ][0]
            result_type = LsType[result_type_str]
            score_threshold = parameters[self.SCORE_THRESHOLD]
            add_xy_field = parameters[self.ADD_XY_FIELD]
            add_display_name = parameters[self.ADD_DISPLAY_NAME]
            add_score_field = parameters[self.ADD_SCORE_FIELD]
            src_field = parameters[self.SRC_FIELD]
            get_actual_geom = parameters[self.GET_ACTUAL_GEOM]
            add_dummy_geometry = parameters[self.ADD_DUMMY_GEOMETRY]

            # start processing
            transform = None
            fields = input_layer.fields()
            field_names = [field.name() for field in fields]

            x_att_name = "gc_x"
            y_att_name = "gc_y"
            if add_xy_field:
                fields.append(QgsField(x_att_name, QVariant.Double))
                fields.append(QgsField(y_att_name, QVariant.Double))

            display_name_att_name = "gc_naam"
            if add_display_name:
                fields.append(QgsField(display_name_att_name, QVariant.String))

            score_att_name = "gc_score"
            if add_score_field:
                fields.append(QgsField(score_att_name, QVariant.Double))

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

            dummy_x = 0
            dummy_y = 0

            feature_counter = 0
            feature_total = input_layer.featureCount()

            for feature in input_layer.getFeatures():
                # TODO: check if src_field value is None if so skip feature
                src_field_val = feature.attribute(src_field)
                # feedback.pushInfo(f"src_field_val: {src_field_val}")

                # Set returned NULL value to None (workaround, cause QGIS does not yet return a None for empty cells)
                if src_field_val == NULL:
                    src_field_val = None

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
                score = None
                if len(data) > 0:
                    score = data[0]["score"]
                    if score_threshold != None and score <= score_threshold:
                        geom = None
                    else:
                        geom = self.get_geom(
                            get_actual_geom, result_type, data, feedback
                        )
                        display_name = data[0]["weergavenaam"]

                if add_dummy_geometry and geom is None:
                    geom = QgsGeometry().fromWkt(f"POINT({dummy_x} {dummy_y})")
                    dummy_y -= 50  # Next location will be 50m north

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
                        new_ft.setAttribute(x_att_name, x)
                        new_ft.setAttribute(y_att_name, y)

                    if add_display_name:
                        new_ft.setAttribute(display_name_att_name, display_name)

                    if add_score_field:
                        new_ft.setAttribute(score_att_name, score)

                    new_ft.setGeometry(geom)
                    sink.addFeature(new_ft, QgsFeatureSink.FastInsert)

                feature_counter += 1
                feedback.setProgress((feature_counter / feature_total) * 100)

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
                ex,
                traceback.format_exc(),
            )
            raise QgsProcessingException(message)
