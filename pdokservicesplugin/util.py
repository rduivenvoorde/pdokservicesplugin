from qgis.PyQt.QtWidgets import (
    QMessageBox,
)
from qgis.core import QgsMessageLog, Qgis
from .constants import PLUGIN_NAME
import textwrap


def info(message):
    QgsMessageLog.logMessage("{}".format(message), PLUGIN_NAME, Qgis.Info)


def show_error(self, message, title):
    title = f"{PLUGIN_NAME} - {title}"
    message = textwrap.dedent(
        message
    )  # textwrap.dedent nodig want anders leading whitespace issue, zie https://stackoverflow.com/a/1412728/1763690
    QMessageBox.critical(
        self.iface.mainWindow(),
        title,
        (message),
        QMessageBox.Ok,
        QMessageBox.Ok,
    )


def show_warning(self, message, title):
    title = f"{PLUGIN_NAME} - {title}"
    message = textwrap.dedent(
        message
    )  # textwrap.dedent nodig want anders leading whitespace issue, zie https://stackoverflow.com/a/1412728/1763690
    QMessageBox.warning(
        self.iface.mainWindow(),
        title,
        (message),
        QMessageBox.Ok,
        QMessageBox.Ok,
    )
