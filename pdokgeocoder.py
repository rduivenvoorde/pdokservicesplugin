import json
from networkaccessmanager import NetworkAccessManager, RequestsException

from xml.dom.minidom import parse
from PyQt4 import QtCore

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

    def __init__(self, iface):
        self.nam = NetworkAccessManager()
        #self.canvas = iface.mapCanvas()


    def search(self, searchstring):
        # https://github.com/PDOK/locatieserver/wiki/API-Locatieserver
        url = 'http://geodata.nationaalgeoregister.nl/locatieserver/v3/free?q={}'.format(searchstring)
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
                straat = u''
                adres = u''
                postcode = u''
                plaats = u''
                gemeente = doc['gemeentenaam']
                provincie = doc['provincienaam']
                x = u""
                y = u""
                centroide_rd = doc['centroide_rd']
                if doc['type'] == 'adres':
                    adrestekst = 'adres: ' + doc['weergavenaam']
                    adres = doc['weergavenaam']
                    straat = doc['straatnaam']
                    plaats = doc['woonplaatsnaam']
                elif doc['type'] == 'weg':
                    adrestekst = 'straat: ' + doc['weergavenaam']
                    straat = doc['straatnaam']
                    plaats = doc['woonplaatsnaam']
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
                    'adres': adres,
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

        return addressesarray
