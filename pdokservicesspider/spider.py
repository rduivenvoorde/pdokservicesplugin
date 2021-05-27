#!/usr/bin/env python3
import logging
import json
import xml
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import requests
from owslib.csw import CatalogueServiceWeb
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from owslib.wfs import WebFeatureService
from owslib.wcs import WebCoverageService

CSW_URL = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw"
LOG_LEVEL = "INFO"
PROTOCOLS = ["OGC:WMS", "OGC:WFS", "OGC:WMTS", "OGC:WCS"]

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s: %(message)s",
)


def join_lists_by_property(list_1, list_2, prop_name):
    lst = sorted(itertools.chain(list_1, list_2), key=lambda x: x[prop_name])
    result = []
    for k, v in itertools.groupby(lst, key=lambda x: x[prop_name]):
        d = {}
        for dct in v:
            d.update(dct)
        result.append(d)
    return result


def get_csw_results(protocol, maxresults=0):
    csw = CatalogueServiceWeb(CSW_URL)
    svc_owner = "Beheer PDOK"
    query = (
        f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}'"
        # to be able to check specific services:
        #f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}' AND any='zeegras'"
    )
    md_ids = []
    start = 1
    maxrecord = maxresults if (maxresults < 100 and maxresults != 0) else 100
    while True:
        csw.getrecords2(maxrecords=maxrecord, cql=query, startposition=start)
        md_ids.extend([{"mdId": rec, "protocol": protocol} for rec in csw.records])
        if len(md_ids) >= maxresults:
            break
        if csw.results["nextrecord"] != 0:
            start = csw.results["nextrecord"]
            continue
        break
    logging.info(f"Found {len(md_ids)} results for protocol {protocol}")
    return md_ids


def get_record_by_id(mdId):
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[mdId])
    return csw.records[mdId]


def get_service_url(result):
    md_id = result["mdId"]
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[md_id])
    record = csw.records[md_id]
    uris = record.uris
    service_url = ""

    if len(uris) > 0:
        service_url = uris[0]["url"]
        service_url = service_url.split("?")[0]
        service_str = result["protocol"].split(":")[1]
        if "https://geodata.nationaalgeoregister.nl/tiles/service/wmts" in service_url:
            service_url = "https://geodata.nationaalgeoregister.nl/tiles/service/wmts"
        service_url = f"{service_url}?request=GetCapabilities&service={service_str}"
    else:
        error_message = (
            f"expected at least 1 service url in service record {md_id}, found 0"
        )
        logging.error(error_message)
    return {"mdId": md_id, "url": service_url}


async def get_data_asynchronous(results, fun):
    result = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                fun,
                *(in_result,),
            )
            for in_result in results
        ]
        for task_result in await asyncio.gather(*tasks):
            result.append(task_result)
        return result


def get_cap(result):
    function_mapping = {"OGC:WMS": get_wms_cap, "OGC:WFS": get_wfs_cap, "OGC:WCS": get_wcs_cap, "OGC:WMTS": get_wmts_cap}
    try:
        result = function_mapping[result["protocol"]](result)
    except requests.exceptions.SSLError:
        md_id = result["mdId"]
        url = result["url"]
        message = f"requests.exceptions.SSLError occured while retrieving capabilities for service mdID {md_id} and url {url}"
        logging.error(message)
    return result

def get_wcs_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wcs[lyr].title,
            "layers": wcs[lyr].id
        }

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(url)
        wcs = WebCoverageService(url, version="2.0.1")
        title = wcs.identification.title
        abstract = wcs.identification.abstract
        keywords = wcs.identification.keywords
        getcoverage_op = next((x for x in wcs.operations if x.name == "GetCoverage"), None)
        result["formats"] = ",".join(getcoverage_op.formatOptions)
        layers = list(wcs.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except Exception:
        message = f"exception while retrieving WCS cap for service mdId: {md_id}, url: {url}"
        logging.exception(message)
    return result

def get_wfs_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wfs[lyr].title,
            "layers": wfs[lyr].id
        }

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(url)
        wfs = WebFeatureService(url, version="2.0.0")
        title = wfs.identification.title
        abstract = wfs.identification.abstract
        keywords = wfs.identification.keywords
        getfeature_op = next((x for x in wfs.operations if x.name == "GetFeature"), None)
        result["formats"] = ",".join(getfeature_op.formatOptions)
        layers = list(wfs.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except Exception:
        message = f"exception while retrieving WFS cap for service mdId: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wms_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wms[lyr].title,
            "style": list(wms[lyr].styles.keys())[0]
            if len(list(wms[lyr].styles.keys())) > 0
            else "",
            "crs": ",".join([x[4] for x in wms[lyr].crs_list]),
            "minscale": wms[lyr].min_scale_denominator.text
            if wms[lyr].min_scale_denominator is not None
            else "",
            "maxscale": wms[lyr].max_scale_denominator.text
            if wms[lyr].max_scale_denominator is not None
            else "",
        }

    try:
        url = result["url"]
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return {"url": f' SECURE SERVICE {result["url"]}'}
        md_id = result["mdId"]
        logging.info(url)
        wms = WebMapService(url, version="1.3.0")
        title = wms.identification.title
        abstract = wms.identification.abstract
        keywords = wms.identification.keywords
        getmap_op = next((x for x in wms.operations if x.name == "GetMap"), None)
        result["imgformats"] = ",".join(getmap_op.formatOptions)
        layers = list(wms.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except Exception:
        message = f"exception while retrieving WMS cap for service mdId: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wmts_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": wmts[lyr].title,
            "tilematrixsets": ",".join(list(wmts[lyr].tilematrixsetlinks.keys())),
            "imgformats": ",".join(wmts[lyr].formats),
        }

    try:
        url = result["url"]
        md_id = result["mdId"]
        logging.info(url)
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return {"url": f' SECURE SERVICE {result["url"]}'}
        wmts = WebMapTileService(url)
        title = wmts.identification.title
        abstract = wmts.identification.abstract
        keywords = wmts.identification.keywords
        layers = list(wmts.contents)
        result["title"] = title
        result["abstract"] = abstract
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except Exception:
        message = f"exception while retrieving WMTS cap for service mdId: {md_id}, url: {url}"
        logging.exception(message)
        
    return result


def flatten_service(service):
    def flatten_layer_wms(layer):
        fields = ["imgformats", "url"]
        for field in fields:
            layer[field] = service[field]
        layer["servicetitle"] = service["title"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer_wcs(layer):
        fields = ["url"]
        for field in fields:
            layer[field] = service[field]
        layer["servicetitle"] = service["title"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["title"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer_wfs(layer):
        fields = ["url"]
        for field in fields:
            layer[field] = service[field]
        layer["servicetitle"] = service["title"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer_wmts(layer):
        layer["servicetitle"] = service["title"]
        layer["url"] = service["url"]
        layer["type"] = service["protocol"].split(":")[1].lower()
        layer["layers"] = layer["name"]
        layer["abstract"] = service["abstract"] if (not None) else ""
        layer["md_id"] = service["mdId"]
        return layer

    def flatten_layer(layer):
        fun_mapping = {
            "OGC:WMS": flatten_layer_wms,
            "OGC:WFS": flatten_layer_wfs,
            "OGC:WCS": flatten_layer_wcs,
            "OGC:WMTS": flatten_layer_wmts,
        }
        return fun_mapping[service["protocol"]](layer)

    return list(map(flatten_layer, service["layers"]))


def main(out_file, number_records):
    protocols = PROTOCOLS
    csw_results = list(
        map(
            lambda x: get_csw_results(x, number_records),
            protocols,
        )
    )
    csw_results = [
        item for sublist in csw_results for item in sublist
    ]  # flatten list of lists
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(get_data_asynchronous(csw_results, get_service_url))
    loop.run_until_complete(future)
    get_record_results = join_lists_by_property(csw_results, future.result(), "mdId")
    get_record_results = filter(
        lambda x: "url" in x and x["url"], get_record_results
    )  # filter out results without serviceurl

    # delete duplicate service entries, some service endpoint have multiple service records
    new_dict = dict()
    for obj in get_record_results:
        if obj["url"] not in new_dict:
            new_dict[obj["url"]] = obj
    get_record_results_filtered = [
        value for key, value in new_dict.items()
    ]  
    nr_services = len(get_record_results_filtered)

    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(
        get_data_asynchronous(get_record_results_filtered, get_cap)
    )
    loop.run_until_complete(future)
    cap_results = future.result()
    
    failed_services = list(filter(lambda x: "layers" not in x, cap_results))
    failed_svc_urls = map(lambda x: x["url"], failed_services)
    nr_failed_services = len(failed_services)
    cap_results = filter(lambda x: "layers" in x, cap_results)  # filter out services where getcap req failed
    config = list(map(flatten_service, cap_results))
    config = [
        item for sublist in config for item in sublist
    ]  # remove nesting due to flattening

    nr_layers = len(config)

    with open(out_file, "w") as f:
        #services = {"services": config}
        #json.dump(services, f, indent=4)
        f.write('{"services": [\n')
        for i in range(0, len(config)):
            json.dump(config[i], f)
            if i < len(config)-1:
                f.write(',\n')
        f.write('\n]}')

    logging.info(f"indexed {nr_services} services with {nr_layers} layers") 
    logging.info(f"failed to index {nr_failed_services} services")
    failed_svc_urls_str = "\n".join(failed_svc_urls)
    logging.info(f"failed service urls:\n{failed_svc_urls_str}")
    logging.info(f"output written to {out_file}")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate XML against schema")
    parser.add_argument(
        "output_file", metavar="output-file", type=str, help="JSON output file"
    )
    parser.add_argument(
        "-n",
        "--number",
        action="store",
        type=int,
        default=0,
        help="nr of records to retrieve per service type",
    )
    args = parser.parse_args()
    main(args.output_file, args.number)
