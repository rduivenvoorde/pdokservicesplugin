import requests
import lxml.etree as etree
from urllib import parse
import json

NSMAP = {"atom": "http://www.w3.org/2005/Atom", "georss":"http://www.georss.org/georss","inspire_dls":"http://inspire.ec.europa.eu/schemas/inspire_dls/1.0"}

def get_node_text(node):
    return node.text if node is not None else ""

def get_text_element(ref_node, xpath):
    result_node = ref_node.find(xpath, NSMAP)
    return get_node_text(result_node)

def get_attr_value(ref_node, xpath, att):
    # "./atom:link[@type='application/atom+xml']"
    print(ref_node)
    print(xpath)
    result_node = ref_node.find(xpath, NSMAP)
    print(result_node)
    return result_node.get(att) if result_node is not None else ""


def parse_service_feed(service_url):
    response = requests.get(service_url)
    tree = etree.fromstring(response.content)
    result = {}
    result["title"] =   get_text_element(tree, "./atom:title")
    result["subtitle"]   =   get_text_element(tree, "./atom:subtitle")
    result["license"] =      get_text_element(tree, "./atom:rights"   )
    result["updated"] =      get_text_element(tree, "./atom:updated")
    service_md_node = tree.find("./atom:link[@rel='describedby']", NSMAP)
    result["service_md_url"] = service_md_node.get("href") if service_md_node is not None else ""
    datasets = []
    for child in tree.findall(".//atom:entry", NSMAP):
        ds = {}
        ds["id"] = get_text_element(child, "./atom:id")
        ds["title"] = get_text_element(child, "./atom:title")
        ds["summary"] = get_text_element(child, "./atom:summary")
        ds["updated"] = get_text_element(child, "./atom:updated")
        ds["polygon"] = get_text_element(child, "./georss:polygon")
        ds["spatial_dataset_identifier_code"] = get_text_element(child, "./inspire_dls:spatial_dataset_identifier_code")
        ds["spatial_dataset_identifier_namespace"] = get_text_element(child, "./inspire_dls:spatial_dataset_identifier_namespace")
        dataset_md_node = child.find("./atom:link[@rel='describedby']", NSMAP)
        ds["dataset_md_url"] = dataset_md_node.get("href") if dataset_md_node is not None else ""
        datafeed_url_node = child.find("./atom:link[@type='application/atom+xml']", NSMAP)
        ds["datafeed_url"] = datafeed_url_node.get("href") if datafeed_url_node is not None else ""

        response = requests.get(ds["datafeed_url"])
        ds_tree = etree.fromstring(response.content)
        dls = []
        for dl_child in ds_tree.findall(".//atom:entry", NSMAP):
            dl = {}
            dl["title"] = get_text_element(dl_child, "./atom:title")
            dl["updated"] = get_text_element(dl_child, "./atom:updated")
            dl["license"] = get_text_element(dl_child, "./atom:rights")
            dl["polygon"] = get_text_element(dl_child, "./georss:polygon")
            proj = {}
            proj["url"] = get_attr_value(dl_child, "./atom:category", "term")
            proj["label"] = get_attr_value(dl_child, "./atom:category", "label")
            dl["projection"] = proj
            dls.append(dl)
        ds["downloads"]  = dls
        datasets.append(ds)
    result["datasets"] = datasets
    print(json.dumps(result, indent=4))

parse_service_feed("https://service.pdok.nl/brt/top100nl/atom/v1_0/index.xml")
