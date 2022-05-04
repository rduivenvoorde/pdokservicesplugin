# -*- coding: utf-8 -*-
import json
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsLocatorFilter,
    QgsLocatorResult,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
    QgsGeometry,
)

from ..lib.locatieserver import suggest_query, lookup_object, Projection

from qgis.PyQt.QtCore import pyqtSignal

# SEE: https://github.com/qgis/QGIS/blob/master/src/core/locator/qgslocatorfilter.h
#      for all attributes/members/functions to be implemented
class PDOKLocatieserverLocatorFilter(QgsLocatorFilter):

    # some magic numbers to be able to zoom to more or less defined levels
    ADDRESS = 1000
    STREET = 1500
    ZIP = 3000
    PLACE = 30000
    CITY = 120000
    ISLAND = 250000
    COUNTRY = 4000000

    resultProblem = pyqtSignal(str)

    def __init__(self, iface):
        # you REALLY REALLY have to save the handle to iface, else segfaults!!
        self.iface = iface
        super(QgsLocatorFilter, self).__init__()

    def name(self):
        return self.__class__.__name__

    def clone(self):
        return PDOKLocatieserverLocatorFilter(self.iface)

    def displayName(self):
        return self.tr("PDOK Locatieserver")

    def prefix(self):
        return "pdok"

    def fetchResults(self, search, context, feedback):
        if len(search) < 2:
            return
        try:
            docs = suggest_query(search)
            for doc in docs:
                result = QgsLocatorResult()
                result.filter = self
                result.displayString = "{} ({})".format(
                    doc["weergavenaam"], doc["type"]
                )
                # use the json full item as userData, so all info is in it:
                result.userData = doc
                result.score = doc[
                    "score"
                ]  # setting a score makes QGIS sort on it in the results!
                self.resultFetched.emit(result)
        except Exception as err:
            # Handle exception..
            # only this one seems to work
            self.info(err)
            # THIS: results in a floating window with a warning in it, wrong thread/parent?
            # self.iface.messageBar().pushWarning("PDOKLocatieserverLocatorFilter Error", '{}'.format(err))
            # THIS: emitting the signal here does not work either?
            self.resultProblem.emit("{}".format(err))

    def triggerResult(self, result):
        self.info("UserClick: {}".format(result.displayString))
        # PDOK Location server return id's which have to picked up then
        id = result.userData["id"]
        try:
            response = lookup_object(id, Projection.EPSG_4326)
            if response is not None:
                doc = response
                # TODO: zoom to the actual geometry instead of the centroid
                geom = QgsGeometry.fromWkt(doc["wkt_geom"])
                centroid = geom.centroid()
                point = centroid.asPoint()
                point_xy = QgsPointXY(point)

                dest_crs = QgsProject.instance().crs()
                results_crs = QgsCoordinateReferenceSystem(
                    4326, QgsCoordinateReferenceSystem.PostgisCrsId
                )
                transform = QgsCoordinateTransform(
                    results_crs, dest_crs, QgsProject.instance()
                )
                point_xy = transform.transform(point_xy)
                self.iface.mapCanvas().setCenter(point_xy)

                scale_denominator = 10000.0
                # map the result types to generic GeocoderLocator types to determine the zoom
                if doc["type"] == "adres":
                    scale_denominator = self.ADDRESS
                elif doc["type"] == "weg":
                    scale_denominator = self.STREET
                elif doc["type"] == "postcode":
                    scale_denominator = self.ZIP
                elif doc["type"] == "gemeente":
                    scale_denominator = self.PLACE
                elif doc["type"] == "woonplaats":
                    scale_denominator = self.CITY
                self.iface.mapCanvas().zoomScale(scale_denominator)
                self.iface.mapCanvas().refresh()
        except Exception as err:
            # Handle exception..
            # only this one seems to work
            self.info(err)
            # THIS: results in a floating window with a warning in it, wrong thread/parent?
            # self.iface.messageBar().pushWarning("PDOKLocatieserverLocatorFilter Error", '{}'.format(err))
            # THIS: emitting the signal here does not work either?
            self.resultProblem.emit("{}".format(err))

    def info(self, msg=""):
        QgsMessageLog.logMessage(
            "{} {}".format(self.__class__.__name__, msg),
            "PDOKLocatieserverLocatorFilter",
            Qgis.Info,
        )
