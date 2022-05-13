#!/usr/bin/env python3
import logging
import json
import asyncio
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import re
from cv2 import sort
import requests
from copy import deepcopy
from owslib.csw import CatalogueServiceWeb
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from owslib.wfs import WebFeatureService
from owslib.wcs import WebCoverageService
import warnings

from urllib import parse

CSW_URL = "https://nationaalgeoregister.nl/geonetwork/srv/dut/csw"
LOG_LEVEL = "INFO"
PROTOCOLS = ["OGC:WMS", "OGC:WFS", "OGC:WMTS", "OGC:WCS"]


SORTING_RULES = {
    0: {"names": ["opentopo+"], "types": ["wmts"]},
    10: {"names": ["^actueel_orthohr$"], "types": ["wmts"]},
    11: {"names": ["^actueel_ortho25$"], "types": ["wmts"]},
    12: {"names": ["^actueel_ortho25ir$"], "types": ["wmts"]},
    13: {"names": ["lufolabels"], "types": ["wmts"]},
    # 15: {'names': ['^\d{4}_ortho'], 'types': ['wmts']},
    # 16: {'names': ['^\d{4}_ortho+IR'], 'types': ['wmts']},
    20: {
        "names": ["landgebied", "provinciegebied", "gemeentegebied"],
        "types": ["wfs"],
    },
    30: {"names": ["top+"], "types": ["wmts"]},
    32: {
        "names": ["^standaard$", "^grijs$", "^pastel$", "^water$"],
        "types": ["wmts"],
    },  # BRT-lagen
    34: {"names": ["bgtstandaardv2", "bgtachtergrond"], "types": ["wmts"]},
    60: {"names": ["ahn3+"], "types": ["wmts"]},
    # 90: {'names': ['aan+'], 'types': ['wmts']},
}


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s: %(message)s",
)


def get_sorting_value(layer_info):
    if not "name" in layer_info:
        return 101
    layer_name = layer_info["name"].lower()
    for key, sorting_rule in SORTING_RULES.items():
        if layer_info["service_type"].lower() in sorting_rule["types"]:
            for name in sorting_rule["names"]:
                if re.search(name, layer_name) is not None:
                    return key
    if layer_info["service_type"].lower() == "wmts":
        return 99  # other wmts layers
    else:
        return 100  # all other layers


def is_popular(service):
    if service["service_type"].lower() == "wmts":
        return True
    return False


def join_lists_by_property(list_1, list_2, prop_name):
    lst = sorted(itertools.chain(list_1, list_2), key=lambda x: x[prop_name])
    result = []
    for k, v in itertools.groupby(lst, key=lambda x: x[prop_name]):
        d = {}
        for dct in v:
            d.update(dct)
        result.append(d)
    return result


def get_csw_results(query, maxresults=0):
    csw = CatalogueServiceWeb(CSW_URL)
    md_ids = []
    start = 1
    maxrecord = maxresults if (maxresults < 100 and maxresults != 0) else 100

    while True:
        csw.getrecords2(maxrecords=maxrecord, cql=query, startposition=start)
        result = [{"md_id": rec} for rec in csw.records]
        md_ids.extend(result)
        if (
            maxresults != 0 and len(result) >= maxresults
        ):  # break only early when maxresults set
            break
        if csw.results["nextrecord"] != 0:
            start = csw.results["nextrecord"]
            continue
        break
    return md_ids


def get_csw_results_by_id(id):
    query = f"identifier='{id}'"
    md_ids = get_csw_results(query)
    print(md_ids)
    return md_ids


def get_csw_results_by_protocol(protocol, maxresults=0):
    svc_owner = "Beheer PDOK"
    query = (
        f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}'"
        # f"identifier='e1b5861b-f94c-4b1f-8012-4e51c69df98f'"
        # to be able to check specific services:
        # f"type='service' AND organisationName='{svc_owner}' AND protocol='{protocol}' AND any='zeegras'"
    )
    md_ids = get_csw_results(query, maxresults)
    md_ids = [x | {"protocol": protocol} for x in md_ids]
    logging.info(f"Found {len(md_ids)} {protocol} services")
    return md_ids


def get_record_by_id(md_id):
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[md_id])
    return csw.records[md_id]


def get_protocol_by_ur(url):
    for prot in PROTOCOLS:
        # pattern looks like this: '.*\/wms(:?\/|\?).*'
        pattern = re.compile(f'.*\/{prot.split(":")[1].lower()}(:?\/|\?).*')
        m = pattern.match(url)
        if m:
            return prot
    return ""


def get_service_url(result):
    md_id = result["md_id"]
    csw = CatalogueServiceWeb(CSW_URL)
    csw.getrecordbyid(id=[md_id])
    record = csw.records[md_id]
    uris = record.uris
    service_url = ""

    if len(uris) > 0:

        service_url = uris[0]["url"]
        service_url = service_url.partition("?")[0]

        if (
            "protocol" not in result
        ):  # TODO: improve code to extract protocol from retrieved md record

            protocol = get_protocol_by_ur(uris[0]["url"])
            print(protocol)
            result["protocol"] = protocol
        else:
            protocol = result["protocol"]
        service_str = protocol.split(":")[1]

        if (
            "https://geodata.nationaalgeoregister.nl/tiles/service/wmts" in service_url
        ):  # shorten paths, some wmts services have redundant path elements in service_url
            service_url = "https://geodata.nationaalgeoregister.nl/tiles/service/wmts"

        if service_url.endswith(
            "/WMTSCapabilities.xml"
        ):  # handle cases for restful wmts url, assume kvp variant is supported
            service_url = service_url.replace("/WMTSCapabilities.xml", "")

        service_url = f"{service_url}?request=GetCapabilities&service={service_str}"

    else:
        error_message = (
            f"expected at least 1 service url in service record {md_id}, found 0"
        )
        logging.error(error_message)
    return {"md_id": md_id, "url": service_url}


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
    function_mapping = {
        "OGC:WMS": get_wms_cap,
        "OGC:WFS": get_wfs_cap,
        "OGC:WCS": get_wcs_cap,
        "OGC:WMTS": get_wmts_cap,
    }
    result = function_mapping[result["protocol"]](result)
    return result


def empty_string_if_none(input_str):
    return input_str if input_str is not None else ""


def get_wcs_cap(result):
    def convert_layer(lyr):
        return {
            "title": empty_string_if_none(wcs[lyr].title),
            "abstract": empty_string_if_none(wcs[lyr].abstract),
            "name": wcs[lyr].id,
            "dataset_md_id": "",  # pdok wcs services do not advertise dataset md link for now, so left empty since unsure how to access dataset md link with owslib for wcs
        }

    try:
        url = result["url"]
        md_id = result["md_id"]
        logging.info(f"{md_id} - {url}")
        wcs = WebCoverageService(url, version="2.0.1")
        keywords = wcs.identification.keywords
        getcoverage_op = next(
            (x for x in wcs.operations if x.name == "GetCoverage"), None
        )
        result["formats"] = ",".join(getcoverage_op.formatOptions)
        layers = list(wcs.contents)
        result["title"] = empty_string_if_none(wcs.identification.title)
        result["abstract"] = empty_string_if_none(wcs.identification.abstract)
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md_id: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WCS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wfs_cap(result):
    def convert_layer(lyr):
        md_urls = [x for x in wfs[lyr].metadataUrls]
        dataset_md_url = md_urls[0]["url"] if len(md_urls) > 0 else ""
        dataset_md_id = "" if not dataset_md_url else get_md_id_from_url(dataset_md_url)

        return {
            "title": empty_string_if_none(wfs[lyr].title),
            "abstract": empty_string_if_none(wfs[lyr].abstract),
            "name": wfs[lyr].id,
            "dataset_md_id": dataset_md_id,
        }

    try:
        url = result["url"]
        md_id = result["md_id"]
        logging.info(f"{md_id} - {url}")
        wfs = WebFeatureService(url, version="2.0.0")
        keywords = wfs.identification.keywords
        getfeature_op = next(
            (x for x in wfs.operations if x.name == "GetFeature"), None
        )
        result["formats"] = ",".join(getfeature_op.formatOptions)
        layers = list(wfs.contents)
        result["title"] = empty_string_if_none(wfs.identification.title)
        result["abstract"] = empty_string_if_none(wfs.identification.abstract)
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WFS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_md_id_from_url(url):
    logging.debug(f"get_md_id_from_url url: {url}")
    params = dict(parse.parse_qsl(parse.urlsplit(url).query))
    params = {k.lower(): v for k, v in params.items()}  # lowercase dict keys
    if "uuid" in params:
        return params["uuid"]
    else:
        return params["id"]


def get_wms_cap(result):
    def convert_layer(lyr):
        styles = (
            list(wms[lyr].styles.keys())
            if len(list(wms[lyr].styles.keys())) > 0
            else ""
        )
        minscale = (
            wms[lyr].min_scale_denominator.text
            if wms[lyr].min_scale_denominator is not None
            else ""
        )
        maxscale = (
            wms[lyr].max_scale_denominator.text
            if wms[lyr].max_scale_denominator is not None
            else ""
        )
        tc211_md_urls = [x for x in wms[lyr].metadataUrls if x["type"] == "TC211"]
        dataset_md_url = tc211_md_urls[0]["url"] if len(tc211_md_urls) > 0 else ""
        dataset_md_id = "" if not dataset_md_url else get_md_id_from_url(dataset_md_url)

        return {
            "name": lyr,
            "title": empty_string_if_none(wms[lyr].title),
            "abstract": empty_string_if_none(wms[lyr].abstract),
            "styles": styles,
            "crs": ",".join([x[4] for x in wms[lyr].crs_list]),
            "minscale": minscale,
            "maxscale": maxscale,
            "dataset_md_id": dataset_md_id,
        }

    try:
        url = result["url"]
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return result
        md_id = result["md_id"]
        logging.info(f"{md_id} - {url}")
        wms = WebMapService(url, version="1.3.0")
        keywords = wms.identification.keywords
        getmap_op = next((x for x in wms.operations if x.name == "GetMap"), None)
        result["imgformats"] = ",".join(getmap_op.formatOptions)
        layers = list(wms.contents)
        result["title"] = empty_string_if_none(wms.identification.title)
        result["abstract"] = empty_string_if_none(wms.identification.abstract)
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"exception while retrieving WMS cap for service md-identifier: {md_id}, url: {url}"
        logging.exception(message)
    return result


def get_wmts_cap(result):
    def convert_layer(lyr):
        return {
            "name": lyr,
            "title": empty_string_if_none(wmts[lyr].title),
            "abstract": empty_string_if_none(wmts[lyr].abstract),
            "tilematrixsets": ",".join(list(wmts[lyr].tilematrixsetlinks.keys())),
            "imgformats": ",".join(wmts[lyr].formats),
            "dataset_md_id": "",  # pdok wmts services do not advertise dataset md link for now, so left empty since unsure how to access dataset md link with owslib for wmts
        }

    try:
        url = result["url"]
        md_id = result["md_id"]
        logging.info(f"{md_id} - {url}")
        if "://secure" in url:
            # this is a secure layer not for the general public: ignore
            return result
        wmts = WebMapTileService(url)
        keywords = wmts.identification.keywords
        layers = list(wmts.contents)
        result["title"] = empty_string_if_none(wmts.identification.title)
        result["abstract"] = empty_string_if_none(wmts.identification.abstract)
        result["layers"] = list(map(convert_layer, layers))
        result["keywords"] = keywords
    except requests.exceptions.HTTPError as e:
        logging.error(f"md-identifier: {md_id} - {e}")
    except Exception:
        message = f"unexpected error occured while retrieving cap doc, md-identifier {md_id}, url: {url}"
        logging.exception(message)
    return result


def flatten_service(service):
    def flatten_layer_wms(layer):
        def flatten_styles(stylename):
            layer_copy = deepcopy(
                layer
            )  #  to prevent the same layer object to be modified each iteration
            layer_copy["imgformats"] = service["imgformats"]
            layer_copy["service_url"] = service["url"]
            layer_copy["service_title"] = service["title"]
            layer_copy["service_type"] = service["protocol"].split(":")[1].lower()
            layer_copy["service_abstract"] = service["abstract"]
            layer_copy["service_md_id"] = service["md_id"]
            layer_copy["style"] = stylename
            layer_copy.pop("layers", None)
            return layer_copy

        styles = layer["styles"]
        layer.pop("styles", None)
        return list(map(flatten_styles, styles))

    def flatten_layer_wcs(layer):
        layer["service_url"] = service["url"]
        layer["service_title"] = service["title"]
        layer["service_type"] = service["protocol"].split(":")[1].lower()
        layer["service_abstract"] = service["abstract"] if (not None) else ""
        layer["service_md_id"] = service["md_id"]
        return layer

    def flatten_layer_wfs(layer):
        layer["service_url"] = service["url"]
        layer["service_title"] = service["title"]
        layer["service_type"] = service["protocol"].split(":")[1].lower()
        layer["service_abstract"] = service["abstract"] if (not None) else ""
        layer["service_md_id"] = service["md_id"]
        return layer

    def flatten_layer_wmts(layer):
        layer["service_title"] = service["title"]
        layer["service_url"] = service["url"]
        layer["service_type"] = service["protocol"].split(":")[1].lower()
        layer["service_abstract"] = service["abstract"] if (not None) else ""
        layer["service_md_id"] = service["md_id"]
        return layer

    def flatten_layer(layer):
        fun_mapping = {
            "OGC:WMS": flatten_layer_wms,
            "OGC:WFS": flatten_layer_wfs,
            "OGC:WCS": flatten_layer_wcs,
            "OGC:WMTS": flatten_layer_wmts,
        }
        return fun_mapping[service["protocol"]](layer)

    result = list(map(flatten_layer, service["layers"]))
    return result


def sort_service_layers(layers):
    sorted_layer_dict = {}
    for layer in layers:
        sorting_value = get_sorting_value(layer)
        if sorting_value in sorted_layer_dict:
            sorted_layer_dict[sorting_value].append(layer)
        else:
            sorted_layer_dict[sorting_value] = [layer]
    result = []
    for key in sorted(sorted_layer_dict.keys()):
        if len(sorted_layer_dict[key]) == 0:
            logging.info(f"no layers found for sorting rule: {SORTING_RULES[key]}")
        result += sorted_layer_dict[key]
    return result


def main(out_file, number_records, sort, pretty, protocols, identifier):
    if protocols:
        protocols = protocols.split(",")
    else:
        protocols = PROTOCOLS

    if identifier:
        csw_results = get_csw_results_by_id(identifier)
    else:
        csw_results = list(
            map(
                lambda x: get_csw_results_by_protocol(x, number_records),
                protocols,
            )
        )
        csw_results = [
            item for sublist in csw_results for item in sublist
        ]  # flatten list of lists
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(get_data_asynchronous(csw_results, get_service_url))
    loop.run_until_complete(future)
    get_record_results = join_lists_by_property(csw_results, future.result(), "md_id")
    get_record_results = filter(
        lambda x: "url" in x and x["url"], get_record_results
    )  # filter out results without serviceurl

    # delete duplicate service entries, some service endpoint have multiple service records
    new_dict = dict()
    for obj in get_record_results:
        new_dict[obj["url"]] = obj

    get_record_results_filtered = [value for key, value in new_dict.items()]

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
    cap_results = filter(
        lambda x: "layers" in x, cap_results
    )  # filter out services where getcap req failed
    config = list(map(flatten_service, cap_results))

    # each services returns as a list of layers, flatten list, see https://stackoverflow.com/a/953097
    config = [item for sublist in config for item in sublist]
    wms_layers = list(filter(lambda x: isinstance(x, list), config))
    config = list(filter(lambda x: isinstance(x, dict), config))
    # wms layers are nested one level deeper, due to exploding layers on styles
    wms_layers = [item for sublist in wms_layers for item in sublist]
    config.extend(wms_layers)
    nr_layers = len(config)

    if sort:
        logging.info(f"sorting services")
        config = sort_service_layers(config)

    with open(out_file, "w") as f:
        if pretty:
            json.dump(config, f, indent=4)
        else:
            json.dump(config, f)

    logging.info(f"indexed {nr_services} services with {nr_layers} layers")
    if nr_failed_services > 0:
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
    parser.add_argument(
        "-i",
        "--id",
        action="store",
        type=str,
        default="",
        help="only process specific service (by service metadata identifier)",
    )
    parser.add_argument(
        "-p",
        "--protocols",
        action="store",
        type=str,
        default="",
        help="service type protocols to query, comma separated",
    )

    parser.add_argument(
        "--sort",
        action="store_true",
        help="sort service layers based on default sorting rules",
    )

    parser.add_argument(
        "--pretty", dest="pretty", action="store_true", help="pretty JSON output"
    )
    parser.add_argument(
        "--warnings",
        dest="show_warnings",
        action="store_true",
        help="show user warnings - owslib tends to show warnings about capabilities",
    )
    args = parser.parse_args()

    if args.show_warnings:
        main(
            args.output_file,
            args.number,
            args.sort,
            args.pretty,
            args.protocols,
            args.id,
        )
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            main(
                args.output_file,
                args.number,
                args.sort,
                args.pretty,
                args.protocols,
                args.id,
            )
