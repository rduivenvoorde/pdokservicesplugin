import json
import os
import urllib
import urllib2
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

# Set Proxy from QGIS-Settings
def setup_urllib2():
    # TODO: test with different proxy settings
    settings = QtCore.QSettings()

    if settings.value("/proxy/proxyEnabled"):
        proxyHost = str(settings.value("proxy/proxyHost", unicode()))
        proxyPassword = str(settings.value("proxy/proxyPassword", unicode()))
        proxyPort = str(settings.value("proxy/proxyPort", unicode()))
        proxyType = str(settings.value("proxy/proxyType", unicode()))
        proxyTypes = { 'DefaultProxy' : 'http', 'HttpProxy' : 'http', 'Socks5Proxy' : 'socks', 'HttpCachingProxy' : 'http', 'FtpCachingProxy' : 'ftp' }
        if proxyType in proxyTypes: 
            proxyType = proxyTypes[proxyType]
        proxyUser = str(settings.value("proxy/proxyUser", unicode()))
        proxyString = 'http://' + proxyUser + ':' + proxyPassword + '@' + proxyHost + ':' + proxyPort
        proxy = urllib2.ProxyHandler({proxyType : proxyString})
        auth = urllib2.HTTPBasicAuthHandler()
        opener = urllib2.build_opener(proxy, auth, urllib2.HTTPHandler)
        urllib2.install_opener(opener)

def search(searchstring):
    """

    :param searchstring:
    """
    # be carefull NO spaces in it: urllib2 will think these are two urls and choke
    # in QGIS 1.8 searchstring will be a QString, that is why we cast to string
    url = "http://geodata.nationaalgeoregister.nl/geocoder/Geocoder?zoekterm=" + urllib.quote_plus(unicode(searchstring))
    #url = "http://www.geocoders.nl/places?format=xml&address=" + urllib.quote_plus(searchstring)
    #print url
    addressesarray = []
    try:
        setup_urllib2()
        response = urllib2.urlopen(url)
        if response.code != 200:
            print 'ERROR %s' % response.code
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
            if isinstance(adres, str) or isinstance(adres, unicode):
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
    except Exception, e:
        print e
    return addressesarray

if __name__ == "__main__":
    search(searchstring)
