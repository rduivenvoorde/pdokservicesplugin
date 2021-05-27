# coding=utf-8
"""Tests PDOK Locatie Server client"""
import os
import unittest
import logging
import urllib.parse
from unittest.mock import patch
from PyQt5.QtCore import QByteArray

from qgis.core import (
    QgsWkbTypes,
)

LOGGER = logging.getLogger("QGIS")


from pdok_services.locatieserver import (
    LsType,
    TypeFilter,
    Projection,
    suggest_query,
    lookup_object,
    free_query,
)
from qgis.PyQt.QtNetwork import QNetworkReply

from unittest.mock import patch

BASE_PATH = os.path.dirname(__file__)


class MockReply:
    def __init__(self, content, error):
        self._content = content
        self._error = error  # QNetworkReply.NoError

    def error(self):
        return self._error

    def content(self):
        return self._content

    def rawHeader(self, value):
        if value == b"Content-Type":
            return b"application/json;charset=utf-8"
        return QByteArray()


class PdokLocatieServerClientTest(unittest.TestCase):
    def setup_mock_request(self, mock_request, result_type):
        if result_type not in ["suggest", "free", "lookup", "empty"]:
            raise AssertionError(f"unexpected result_type: {result_type}")

        with open(os.path.join(BASE_PATH, "data", f"{result_type}.json"), "rb") as f:
            data = f.read()
        mock_request.return_value.reply.return_value = MockReply(
            data,
            QNetworkReply.NoError,
        )
        return mock_request

    def test_ls_type_geom_mapping(self):
        gemeente_type = LsType.gemeente
        geom_type = gemeente_type.geom_type()
        self.assertEqual(geom_type, QgsWkbTypes.MultiPolygon)

    def test_projection_available(self):
        proj_strings = []
        for proj in Projection:
            proj_strings.append(proj.value)
        expected_projections = ["EPSG:28992", "EPSG:4326"]
        self.assertSetEqual(set(expected_projections), set(proj_strings))

    def test_projection_value(self):
        rd_proj = Projection.EPSG_28992
        proj_str = rd_proj.value
        expected_proj_str = "EPSG:28992"
        self.assertEqual(expected_proj_str, proj_str)

    def test_type_filter_query_all_types(self):
        tf_query = TypeFilter()
        query = str(tf_query)
        expected_query = urllib.parse.quote(
            "type:(adres OR appartementsrecht OR buurt OR gemeente OR hectometerpaal OR perceel OR postcode OR provincie OR weg OR wijk OR waterschap OR woonplaats)"
        )
        self.assertEqual(expected_query, query)

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_return_type_suggest_query(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "suggest")
        result_suggest = suggest_query("Amsterdam")
        self.assertTrue(isinstance(result_suggest, list))
        self.assertTrue(all(isinstance(x, dict) for x in result_suggest))

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_return_type_lookup(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "lookup")
        result_lookup = lookup_object(
            "wpl-d7676180b7f172bcb7356429b19563a5", Projection.EPSG_4326
        )
        self.assertTrue(isinstance(result_lookup, dict))

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_non_existing_lookup(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "empty")
        result_lookup = lookup_object("wpl-doesnotexist", Projection.EPSG_4326)
        self.assertIsNone(result_lookup)

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_return_type_free_query(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "free")
        result_free = free_query(
            "Varkensstraat 44-1, 6811GN Arnhem", Projection.EPSG_4326
        )
        self.assertTrue(isinstance(result_free, list))
        self.assertTrue(all(isinstance(x, dict) for x in result_free))

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_default_nr_results(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "free")
        get_calls = mock_request.return_value.get.call_args_list
        free_query("Varkensstraat 44-1, 6811GN Arnhem", Projection.EPSG_4326)
        requested_url = get_calls[0][0][0].url().url()
        self.assertIn("&rows=10", requested_url)

    @patch("pdok_services.http_client.QgsBlockingNetworkRequest")
    def test_nr_results(self, mock_request):
        mock_request = self.setup_mock_request(mock_request, "free")
        get_calls = mock_request.return_value.get.call_args_list
        free_query("Varkensstraat 44-1, 6811GN Arnhem", Projection.EPSG_28992, rows=20)
        requested_url = get_calls[0][0][0].url().url()
        self.assertIn("&rows=20", requested_url)


if __name__ == "__main__":
    unittest.main()
