# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin
                                 A QGIS plugin
 
                             -------------------
        begin                : 2012-10-11
        copyright            : (C) 2012 by Richard Duivenvoorde
        email                : richard@zuidt.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""
from qgis.core import (
    Qgis,
)
import logging

"""
The name of logger we use in this plugin.
It is created in the plugin.py and logs to the QgsMessageLog under the 
given LOGGER_NAME tab
"""
LOGGER_NAME = 'PDOK services plugin'


class QgisLogHandler(logging.StreamHandler):
    """
    Some magic to make it possible to use code like:

    import logging
    from . import LOGGER_NAME
    log = logging.getLogger(LOGGER_NAME)

    in all this plugin code, and it will show up in the QgsMessageLog

    """
    def __init__(self, topic):
        logging.StreamHandler.__init__(self)
        # topic is used both as logger id and for tab
        self.topic = topic

        """"
          Qgis.MessageLevel:
            Info = 0,     //!< Information message
            Warning = 1,  //!< Warning message
            Critical = 2, //!< Critical/error message
            Success = 3,  //!< Used for reporting a successful operation
            NoLevel = 4,  //!< No level

          Python logging:
            CRITICAL = 50
            ERROR = 40
            WARNING = 30
            INFO = 20
            DEBUG = 10
            NOTSET = 0
        """

        self.level_to_qgis = {
            0: Qgis.MessageLevel.Info,
            10: Qgis.MessageLevel.Info,
            20: Qgis.MessageLevel.Info,
            30: Qgis.MessageLevel.Warning,
            40: Qgis.MessageLevel.Warning,
            50: Qgis.MessageLevel.Critical
        }

    def emit(self, record):
        # Below makes sure that logging of 'self' will show the repr of the object
        # Without this it will not be shown because it is something like
        # <qgisnetworklogger.plugin.QgisNetworkLogger object at 0x7f580dac6b38>
        # which looks like an html element so is not shown in the html panel
        #msg = self.format(record)
        msg = record.getMessage().replace('<', '&lt;').replace('>', '&gt;')
        from qgis.core import QgsMessageLog  # we need this... else QgsMessageLog is None after a plugin reload
        QgsMessageLog.logMessage(f'{record.filename}:{record.lineno} - {msg}', self.topic, self.level_to_qgis[record.levelno])



# using the root logger here, so we also can view the api logging if needed
# alternative would be:
log = logging.getLogger(LOGGER_NAME)
#log = logging.getLogger()

# so to SHOW: COMMENT these lines
logging.getLogger(LOGGER_NAME).setLevel(logging.WARNING)

# checking below is needed, else we add this handler every time the plugin
# is reloaded (during development), then the msg is emitted several times
if not log.hasHandlers():
    handler = QgisLogHandler(LOGGER_NAME)
    handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
    log.addHandler(handler)
# set logging level (NOTSET = no, else: DEBUG or INFO)
log.setLevel(logging.DEBUG)
log.propagate = True

def classFactory(iface):
    # load PdokServicesPlugin class from file PdokServicesPlugin
    from .pdokservicesplugin import PdokServicesPlugin
    return PdokServicesPlugin(iface)
