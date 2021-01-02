#!/usr/bin/env python3

url = 'https://geodata.nationaalgeoregister.nl/nok2014/wms?request=GetCapabilities&service=wms'
#url = 'https://geodata.nationaalgeoregister.nl/nok2014/wfs?request=GetCapabilities&service=wfs&version=2.0.0'
#url= 'https://geoserver.nieuwegein.nl/geoserver/wms?request=getcapabilities'
#url= 'https://geoserver.nieuwegein.nl/geoserver/wfs?request=getcapabilities'
#url= 'https://duif.net'
#url = 'https://nos.nl'
#url = 'https://www.freedom.nl'
print(f'test url: {url}')



# urllib manier
# traag bij Freedom
import urllib.request, urllib.error

# originele manier, altijd gewerkt
response = urllib.request.urlopen(url)

# https://medium.com/python-pandemonium/debugging-an-inactive-python-process-2b11f88730c7
# hoe te debuggen EN zet altijd een timout!
#response = urllib.request.urlopen(url, timeout=5)

# trying to set some headers... because PDOK was not responding...

# req = urllib.request.Request(
#     url,
#     data=None,
#     headers={
#         'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36',
#         'Referer': 'https://zuidt.nl'
#     }
# )
# response = urllib.request.urlopen(req)

string = response.read()
print(f'string: {string}')


# Requests (module) manier... maakt niks uit
# import requests
# response = requests.get(url)
# print(f'response: {response}')
# print(response.text)





    # url = 'https://geodata.nationaalgeoregister.nl/nok2014/wms?request=GetCapabilities&service=wms'
    # print(f'test url: {url}')
    # import urllib.request, urllib.error
    # response = urllib.request.urlopen(url)
    # string = response.read()
    # print(f'string: {string}')
