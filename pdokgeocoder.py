from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str
import json
import os
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
from xml.dom.minidom import parse
from qgis.PyQt.QtCore import QSettings

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

# Set Proxy from QGIS-Settings
def setup_urllib2():
    # TODO: test with different proxy settings
    settings = QSettings()

    if settings.value( "proxy/proxyEnabled", 'false' ) == 'false':
        # no action needed
        pass
    else:
        # set up for using the actual proxy
        proxyHost = str(settings.value("proxy/proxyHost", str()))
        proxyPassword = str(settings.value("proxy/proxyPassword", str()))
        proxyPort = str(settings.value("proxy/proxyPort", str()))
        proxyType = str(settings.value("proxy/proxyType", str()))
        proxyTypes = { 'DefaultProxy' : 'http', 'HttpProxy' : 'http', 'Socks5Proxy' : 'socks', 'HttpCachingProxy' : 'http', 'FtpCachingProxy' : 'ftp' }
        if proxyType in proxyTypes:
            proxyType = proxyTypes[proxyType]
        proxyUser = str(settings.value("proxy/proxyUser", str()))
        proxyString = 'http://' + proxyUser + ':' + proxyPassword + '@' + proxyHost + ':' + proxyPort
        proxy = urllib.request.ProxyHandler({proxyType : proxyString})
        auth = urllib.request.HTTPBasicAuthHandler()
        opener = urllib.request.build_opener(proxy, auth, urllib.request.HTTPHandler)
        urllib.request.install_opener(opener)


def search(searchstring):
    """

    :param searchstring:
    """
    # be carefull NO spaces in it: urllib2 will think these are two urls and choke
    # in QGIS 1.8 searchstring will be a QString, that is why we cast to string
    url = "http://geodata.nationaalgeoregister.nl/geocoder/Geocoder?zoekterm=" + urllib.parse.quote_plus(str(searchstring))
    #url = "http://www.geocoders.nl/places?format=xml&address=" + urllib.quote_plus(searchstring)
    #print url
    addressesarray = []
    try:
        setup_urllib2()
        response = urllib.request.urlopen(url)
        if response.code != 200:
            # fix_print_with_import
            print('ERROR %s' % response.code)
            exit()
        doc = parse(response)

        addresses = doc.getElementsByTagName("xls:GeocodedAddress")
        for address in addresses:
            street = u""
            building = u""
            streetAddress = address.getElementsByTagName("xls:StreetAddress")
            if len(streetAddress)>0:
                streetAddress = streetAddress[0]
                street = streetAddress.getElementsByTagName("xls:Street")
                if len(street)>0:
                    street = street[0].firstChild.nodeValue
                else:
                    street = u""
                building = streetAddress.getElementsByTagName("xls:Building")
                if len(building)>0:
                    building = building[0]
                    number = building.getAttribute("number")
                    subdivision = building.getAttribute("subdivision")
                    building = number+subdivision
                else:
                    building = u""
            postalcode = address.getElementsByTagName("xls:PostalCode")
            if len(postalcode)>0:
                postalcode = postalcode[0].firstChild.nodeValue
            else:
                postalcode = u""
            plaats = u""
            gemeente = u""
            provincie = u""
            places = address.getElementsByTagName("xls:Place")
            for place in places:
                if place.getAttribute("type")=="CountrySubdivision":
                    prov = place.firstChild.nodeValue
                if place.getAttribute("type")=="Municipality":
                    gemeente = place.firstChild.nodeValue
                if place.getAttribute("type")=="MunicipalitySubdivision":
                    plaats = place.firstChild.nodeValue
            pos = address.getElementsByTagName("gml:pos")[0].firstChild.nodeValue
            # if total_address is correctly written xmlTag exists:
            if pos:
                remark=True
                # split X and Y coordinate in list
                XY = pos.split()
                if XY:
                    x = float(XY[0])
                    y = float(XY[1])
                    #print "point: " + str(x) + ", " + str(y)
            adres = ""
            if len(street)>0:
                # sometimes we only get gemeente
                plaatsgemeente = plaats
                if len(plaatsgemeente)==0:
                    plaatsgemeente = gemeente
                if len(building)>0:
                    adres = 'adres: ' + (street + " " + building + " " + postalcode + " " + plaatsgemeente + " " + prov).replace('  ',' ')
                else:
                    adres = 'straat: ' + (street + " " + building + " " + postalcode  + " " + plaatsgemeente + " " + prov).replace('  ',' ')
            elif len(plaats)>0:
                adres = 'plaats: '+ (plaats + " (" + gemeente + ") in " + prov).replace('  ',' ')
            elif len(gemeente)>0:
                adres = 'gemeente: ' +(gemeente + " in " + prov).replace('  ',' ')
            elif len(prov)>0:
                adres = 'provincie: ' + prov
            #print adres.strip().replace('  ',' ') + ' ('+str(x) + ", " + str(y)+')'
            if isinstance(adres, str) or isinstance(adres, str):
                adres = adres.strip().replace('  ',' ')
            else:
                # QGIS 1.8
                adres = adres.simplified()

            addressdict = {
                'straat':street,
                'adres':building,
                'postcode':postalcode,
                'plaats':plaats,
                'gemeente':gemeente,
                'provincie':prov,
                'x':x,
                'y':y,
                'adrestekst': adres
            }
            addressesarray.append(addressdict)
    except Exception as e:
        # fix_print_with_import
        print(e)
    return addressesarray

if __name__ == "__main__":
    search(searchstring)
