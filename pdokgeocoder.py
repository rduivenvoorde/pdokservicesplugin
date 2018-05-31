import json
import copy
from .networkaccessmanager import NetworkAccessManager, RequestsException

#from xml.dom.minidom import parse
#from qgis.PyQt import QtCore

searchstring = 'riouwstaat, haarlem'
#searchstring = 'kenaustraat 12, haarlem'
#searchstring = 'amperestraat, den bosch'
searchstring = 'kenaustraat, haarlem'
searchstring = 'riouwstraat 23'
#searchstring = 'Riouwstraat 1 Haarlem Noord-Holland'
#searchstring = ''
#searchstring = 'utrecht'
#searchstring = 'kerkstraat 1'
#searchstring = 'veld 1'
#searchstring = 'valkenburg' # geeft 0 hits en valkeburg heeft de juiste??
#searchstring = 'noordwijk'
#searchstring = '2022ZJ'
#searchstring = '2022ZJ 23'


class PDOKGeoLocator:

    LOCATIESERVER_BASE_URL = 'https://geodata.nationaalgeoregister.nl/locatieserver/v3'

    def __init__(self, iface):
        self.nam = NetworkAccessManager()
        #self.canvas = iface.mapCanvas()


    def search(self, searchstring):
        # https://github.com/PDOK/locatieserver/wiki/API-Locatieserver
        url = '{}/free?q={}'.format(self.LOCATIESERVER_BASE_URL, searchstring)
        addressesarray = []
        try:
            # TODO: Provide a valid HTTP Referer or User-Agent identifying the application (QGIS geocoder)
            (response, content) = self.nam.request(url)
            #print('xx response: {}'.format(response))
            # TODO: check statuscode etc in RESPONSE
            #print('xx content: {}'.format(content))

            content_string = content.decode('utf-8')
            obj = json.loads(content_string)
            docs = obj['response']['docs']
            for doc in docs:
                #print(doc)
                straat = ''
                nummer = ''
                postcode = ''
                plaats = ''
                gemeente = doc['gemeentenaam']
                provincie = doc['provincienaam']
                x = ''
                y = ''
                centroide_rd = doc['centroide_rd']
                if doc['type'] == 'adres':
                    adrestekst = 'adres: ' + doc['weergavenaam']
                    nummer = doc['huis_nlt']  # huis_nlt  = huisnummer + letter/toevoeging
                    straat = doc['straatnaam']
                    if 'postcode' in doc:  # optional ?
                        postcode = doc['postcode']
                    plaats = doc['woonplaatsnaam']
                elif doc['type'] == 'weg':
                    adrestekst = 'straat: ' + doc['weergavenaam']
                    straat = doc['straatnaam']
                    if 'woonplaatsnaam' in doc:
                        plaats = doc['woonplaatsnaam']
                    if 'gemeentenaam' in doc:
                        plaats = doc['gemeentenaam']
                elif doc['type'] == 'postcode':
                    adrestekst = 'postcode: ' + doc['weergavenaam']
                    postcode = doc['postcode']
                    straat = doc['straatnaam']
                    plaats = doc['woonplaatsnaam']
                elif doc['type'] == 'woonplaats':
                    adrestekst = 'plaats: ' + doc['woonplaatsnaam']
                    plaats = doc['woonplaatsnaam']
                elif doc['type'] == 'gemeente':
                    adrestekst = 'gemeente: ' + doc['gemeentenaam']

                addressdict = {
                    'straat': straat,
                    'nummer': nummer,
                    'postcode': postcode,
                    'plaats': plaats,
                    'gemeente': gemeente,
                    'provincie': provincie,
                    'x': x,
                    'y': y,
                    'centroide_rd': centroide_rd,
                    'adrestekst': adrestekst
                }
                addressesarray.append(addressdict)

        except RequestsException:
            # Handle exception
            #errno, strerror = RequestsException.args
            #print('!!!!!!!!!!! EXCEPTION !!!!!!!!!!!!!: \n{}\n{}'. format(errno, strerror))
            pass

        return addressesarray

    def suggest(self, searchstring):
        url = '{}/suggest?q={}'.format(self.LOCATIESERVER_BASE_URL, searchstring)
        # {"response": {
        #   "numFound": 21,
        #   "start": 0,
        #   "maxScore": 18.388767,
        #   "docs": [
        #      { "type": "postcode",
        #        "weergavenaam": "Riouwstraat, 2022ZJ Haarlem",
        #        "id":"pcd - c0a1d71a53a3977ca4ed8f9180482942",
        #        "score":18.388767},
        #      { "type":"adres",
        #        "weergavenaam":"Riouwstraat 1, 2022ZJ Haarlem",
        #        "id":"adr-521e3fb0b4343d92b2e47f869071ed5e",
        #        "score":13.6195135}
        #    }
        #
        resultsarray = []
        try:
            # TODO: Provide a valid HTTP Referer or User-Agent identifying the application (QGIS geocoder)
            (response, content) = self.nam.request(url)
            #print('xx response: {}'.format(response))
            # TODO: check statuscode etc in RESPONSE
            #print('xx content: {}'.format(content))

            content_string = content.decode('utf-8')
            obj = json.loads(content_string)
            docs = obj['response']['docs']
            for doc in docs:
                #print(doc)
                adrestekst = doc['weergavenaam']
                type = doc['type']
                id = doc['id']
                score = doc['score']
                resultdict = {
                    'adrestekst': adrestekst,
                    'type': type,
                    'id': id,
                    'score': score
                }
                resultsarray.append(resultdict)

        except RequestsException:
            # Handle exception
            #errno, strerror = RequestsException.args
            #print('!!!!!!!!!!! EXCEPTION !!!!!!!!!!!!!: \n{}\n{}'. format(errno, strerror))
            pass

        return resultsarray

    def lookup(self, idstring):
        url = '{}lookup?id={}'.format(self.LOCATIESERVER_BASE_URL, idstring)

        # https://geodata.nationaalgeoregister.nl/locatieserver/v3/lookup?id=adr-521e3fb0b4343d92b2e47f869071ed5e

        # {"response": {
        #   "numFound": 1,
        #   "start": 0,
        #   "maxScore": 15.695365,
        #   "docs": [
        #     {
        #       "bron": "BAG",
        #       "woonplaatscode": "2907",
        #       "type": "adres",
        #       "woonplaatsnaam": "Haarlem",
        #       "huis_nlt": "1",
        #       "openbareruimtetype": "Weg",
        #       "gemeentecode": "0392",
        #       "weergavenaam": "Riouwstraat 1, 2022ZJ Haarlem",
        #       "straatnaam_verkort": "Riouwstr",
        #       "id": "adr-521e3fb0b4343d92b2e47f869071ed5e",
        #       "gekoppeld_perceel": ["STN01-B-7838"],
        #       "gemeentenaam": "Haarlem",
        #       "identificatie": "0392010000053203-0392200000053203",
        #       "openbareruimte_id": "0392300000011160",
        #       "provinciecode": "PV27",
        #       "postcode": "2022ZJ",
        #       "provincienaam": "Noord-Holland",
        #       "centroide_ll": "POINT(4.64739941 52.39738762)",
        #       "nummeraanduiding_id": "0392200000053203",
        #       "adresseerbaarobject_id": "0392010000053203",
        #       "huisnummer": 1,
        #       "provincieafkorting": "NH",
        #       "centroide_rd": "POINT(104647.676 490206.575)",
        #       "straatnaam": "Riouwstraat"}
        #   ]}}

        result = {}
        try:
            # TODO: Provide a valid HTTP Referer or User-Agent identifying the application (QGIS geocoder)
            (response, content) = self.nam.request(url)
            #print('xx response: {}'.format(response))
            # TODO: check statuscode etc in RESPONSE
            #print('xx content: {}'.format(content))

            content_string = content.decode('utf-8')
            obj = json.loads(content_string)
            doc = obj['response']['docs'][0]
            # print(doc)
            centroide_rd = doc['centroide_rd']
            type = doc['type']
            adrestekst = '{}: {}'.format(doc['type'], doc['weergavenaam'])
            data = copy.deepcopy(doc)
            result = {
                'centroide_rd': centroide_rd,
                'adrestekst': adrestekst,
                'type': type,
                'data': data
            }

        except RequestsException:
            # Handle exception
            # errno, strerror = RequestsException.args
            # print('!!!!!!!!!!! EXCEPTION !!!!!!!!!!!!!: \n{}\n{}'. format(errno, strerror))
            pass

        return result
