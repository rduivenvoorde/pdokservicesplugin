# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PdokServicesPlugin
                                 A QGIS plugin
 bla
                             -------------------
        begin                : 2012-10-11
        copyright            : (C) 2012 by Richard Duivenvoorde
        email                : richard@webmapper.net
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
def name():
    return "Pdok service plugin"
def description():
    return "Check dutch pdok services"
def version():
    return "Version 0.1"
def icon():
    return "icon.png"
def qgisMinimumVersion():
    return "1.0"
def classFactory(iface):
    # load PdokServicesPlugin class from file PdokServicesPlugin
    from pdokservicesplugin import PdokServicesPlugin
    return PdokServicesPlugin(iface)
