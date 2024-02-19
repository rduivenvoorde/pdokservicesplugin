import json
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtCore import QUrl
from qgis.core import QgsBlockingNetworkRequest
from http.client import responses


class PdokServicesNetworkException(Exception):
    """Raise for my specific kind of exception"""

    pass


def get_reply(url):
    qgs_request = QgsBlockingNetworkRequest()
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"User-Agent", b"qgis-pdokservices-plugin")
    _ = qgs_request.get(
        request, True
    )  # not sure if it is necessary to to test if error is returned here, the reply.error() call also seems to catch network errors, that's why return value of qgs_request.get is not examined

    reply = qgs_request.reply()
    reply_err = reply.error()
    if reply_err != QNetworkReply.NetworkError.NoError:
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        message = ""
        if status_code is not None:
            status_string = responses[status_code]
            message = f"{status_code} - {status_string}"
        reply_error_message = f"{reply.errorString()}{message}"
        raise PdokServicesNetworkException(reply_error_message)

    return reply


def get_request_bytes(url, expected_content_type: str = None) -> bytes:
    reply = get_reply(url)

    if expected_content_type:
        content_type = str(reply.rawHeader(b"Content-Type"), encoding="utf-8")
        if content_type != expected_content_type:
            raise Exception(
                f"unexpected Content-Type of response {content_type}, expected Content-Type {expected_content_type}. Request url: {url}"
            )
    result = bytes(reply.content())
    return result


def get_request_text(url) -> str:
    reply = get_reply(url)
    content_type = bytes(reply.rawHeader(b"Content-Type")).decode(
        "ascii"
    )  # https://stackoverflow.com/a/4410331
    encoding = "utf-8"
    if len(content_type.split(";")) > 1:
        encoding = content_type.split(";")[1].replace("charset=", "")
    content_str = str(reply.content(), encoding)
    return content_str


def get_request_json(url):
    reply = get_reply(url)
    content_type = bytes(reply.rawHeader(b"Content-Type")).decode(
        "ascii"
    )  # https://stackoverflow.com/a/4410331
    encoding = "utf-8"
    if len(content_type.split(";")) > 1:
        encoding = content_type.split(";")[1].replace("charset=", "")
    content_str = str(reply.content(), encoding)
    if not content_type.startswith("application/json"):
        raise ValueError(
            f"Received Content-Type:{content_type}  expected Content-Type:application/json"
        )
    return json.loads(content_str)
