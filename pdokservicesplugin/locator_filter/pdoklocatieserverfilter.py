# -*- coding: utf-8 -*-

from qgis.core import Qgis, QgsMessageLog, QgsLocatorFilter, QgsLocatorResult,  \
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsPoint, QgsPointXY

from . networkaccessmanager import NetworkAccessManager, RequestsException

from qgis.PyQt.QtCore import pyqtSignal

import json

# SEE: https://github.com/qgis/QGIS/blob/master/src/core/locator/qgslocatorfilter.h
#      for all attributes/members/functions to be implemented
class PDOKLocatieserverLocatorFilter(QgsLocatorFilter):

    USER_AGENT = b'Mozilla/5.0 QGIS PDOKLocatieserverLocatorFilter'

    SEARCH_URL = 'https://geodata.nationaalgeoregister.nl/locatieserver/v3/suggest?q='
    # test url to be able to force errors
    #SEARCH_URL = 'http://duif.net/cgi-bin/qlocatorcheck.cgi?q='

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
        return self.tr('PDOK Locatieserver')

    def prefix(self):
        return 'pdok'

    def fetchResults(self, search, context, feedback):

        if len(search) < 2:
            return

        url = '{}{}'.format(self.SEARCH_URL, search)
        self.info('Search url {}'.format(url))
        nam = NetworkAccessManager()
        try:
            # "Provide a valid HTTP Referer or User-Agent identifying the application (QGIS geocoder)"
            headers = {b'User-Agent': self.USER_AGENT}
            # use BLOCKING request, as fetchResults already has it's own thread!
            (response, content) = nam.request(url, headers=headers, blocking=True)
            #self.info(response)
            #self.info(response.status_code)
            if response.status_code == 200:  # other codes are handled by NetworkAccessManager
                content_string = content.decode('utf-8')
                obj = json.loads(content_string)
                docs = obj['response']['docs']
                for doc in docs:
                    result = QgsLocatorResult()
                    result.filter = self
                    result.displayString = '{} ({})'.format(doc['weergavenaam'], doc['type'])
                    # use the json full item as userData, so all info is in it:
                    result.userData = doc
                    self.resultFetched.emit(result)

        except RequestsException as err:
            # Handle exception..
            # only this one seems to work
            self.info(err)
            # THIS: results in a floating window with a warning in it, wrong thread/parent?
            #self.iface.messageBar().pushWarning("PDOKLocatieserverLocatorFilter Error", '{}'.format(err))
            # THIS: emitting the signal here does not work either?
            self.resultProblem.emit('{}'.format(err))


    def triggerResult(self, result):
        self.info("UserClick: {}".format(result.displayString))
        # PDOK Location server return id's which have to picked up then
        id = result.userData['id']
        url = 'https://geodata.nationaalgeoregister.nl/locatieserver/v3/lookup?id={}'.format(id)
        nam = NetworkAccessManager()
        try:
            (response, content) = nam.request(url)
            #print('response: {}'.format(response))
            # TODO: check statuscode etc
            #print('content: {}'.format(content))
            content_string = content.decode('utf-8')
            obj = json.loads(content_string)

            found = obj['response']['numFound']
            if found != 1:
                print('XXXXXXXXXXXXXXXXX  numFound != 1')
            else:
                doc = obj['response']['docs'][0]
                point = QgsPoint()
                point.fromWkt(doc['centroide_ll'])
                point_xy = QgsPointXY(point)
                dest_crs = QgsProject.instance().crs()
                results_crs = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.PostgisCrsId)
                transform = QgsCoordinateTransform(results_crs, dest_crs, QgsProject.instance())
                point_xy = transform.transform(point_xy)
                self.iface.mapCanvas().setCenter(point_xy)

                scale_denominator = 10000.0
                # map the result types to generic GeocoderLocator types to determine the zoom
                if doc['type'] == 'adres':
                    scale_denominator = self.ADDRESS
                elif doc['type'] == 'weg':
                    scale_denominator = self.STREET
                elif doc['type'] == 'postcode':
                    scale_denominator = self.ZIP
                elif doc['type'] == 'gemeente':
                    scale_denominator = self.PLACE
                elif doc['type'] == 'woonplaats':
                    scale_denominator = self.CITY
                self.iface.mapCanvas().zoomScale(scale_denominator)
                self.iface.mapCanvas().refresh()

        except RequestsException as err:
            # Handle exception..
            # only this one seems to work
            self.info(err)
            # THIS: results in a floating window with a warning in it, wrong thread/parent?
            #self.iface.messageBar().pushWarning("PDOKLocatieserverLocatorFilter Error", '{}'.format(err))
            # THIS: emitting the signal here does not work either?
            self.resultProblem.emit('{}'.format(err))

    def info(self, msg=""):
        QgsMessageLog.logMessage('{} {}'.format(self.__class__.__name__, msg), 'PDOKLocatieserverLocatorFilter', Qgis.Info)
