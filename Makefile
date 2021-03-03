#/***************************************************************************
# PdokServicesPlugin
# 
# bla
#                             -------------------
#        begin                : 2012-10-11
#        copyright            : (C) 2012 by Richard Duivenvoorde
#        email                : richard@webmapper.net
# ***************************************************************************/
# 
#/***************************************************************************
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# ***************************************************************************/

# CONFIGURATION
PLUGIN_UPLOAD = $(CURDIR)/plugin_upload.py

# Makefile for a PyQGIS plugin 

# translation
SOURCES = pdokservicesplugin.py ui_pdokservicesplugin.py __init__.py pdokservicesplugindialog.py pdokgeocoder.py networkaccessmanager.py
#TRANSLATIONS = i18n/pdokservicesplugin_en.ts
TRANSLATIONS = 

# global

PLUGINNAME = pdokservicesplugin

VERSION=$(shell cat metadata.txt | grep version= | sed -e 's,version=,,')

PY_FILES = pdokservicesplugin.py pdokservicesplugindialog.py __init__.py pdokgeocoder.py  networkaccessmanager.py

EXTRAS = pdok.json metadata.txt pdok.version icon_add_service.svg icon_help.png icon_pdok.svg icon_remove_cross.svg

UI_FILES = ui_pdokservicesplugindialog.py

RESOURCE_FILES = resources_rc.py

QGISDIR=.local/share/QGIS/QGIS3/profiles/default


HELP = help/build/html

default: compile

compile: $(UI_FILES) $(RESOURCE_FILES)

%_rc.py : %.qrc
	pyrcc5 -o $*_rc.py  $<

%.py : %.ui
	pyuic5 -do $@ $<

%.qm : %.ts
	lrelease $<

# The deploy  target only works on unix like operating system where
# the Python plugin directory is located at:
# $HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins
#deploy: compile
deploy: compile
	mkdir -p $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	cp -vf $(UI_FILES) $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	cp -vf $(RESOURCE_FILES) $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	cp -vf $(EXTRAS) $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	#cp -vfr i18n $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
	#cp -vfr $(HELP) $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)/help

# The dclean target removes compiled python files from plugin directory
# also delets any .svn entry
dclean:
	find $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME) -iname "*.pyc" -delete
	find $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME) -iname ".svn" -prune -exec rm -Rf {} \;
	find $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME) -iname "__pycache__" -prune -exec rm -Rf {} \;

# The derase deletes deployed plugin
derase:
	rm -Rf $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)

# The zip target deploys the plugin and creates a zip file with the deployed
# content. You can then upload the zip file on http://plugins.qgis.org
zip: deploy dclean
	rm -f $(PLUGINNAME).zip
	rm -rf __pycache__
	cd $(HOME)/$(QGISDIR)/python/plugins; zip -9r $(CURDIR)/$(PLUGINNAME)_$(VERSION).zip $(PLUGINNAME)
	mv $(CURDIR)/$(PLUGINNAME)_$(VERSION).zip repo


# Create a symlink for development in the default profile python plugins dir
symlink:
	mkdir -p $(HOME)/$(QGISDIR)/python/plugins
	# in case there is a deployed version: remove it
	rm -rf $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	ln -s `pwd` $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)

# Remove the created symlink
desymlink:
	rm -Rf $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)

# Create a zip package of the plugin named $(PLUGINNAME).zip. 
# This requires use of git (your plugin development directory must be a 
# git repository).
# To use, pass a valid commit or tag as follows:
#   make package VERSION=Version_0.3.3
package: compile
		rm -f $(PLUGINNAME).zip
		git archive --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip $(VERSION)
		echo "Created package: $(PLUGINNAME).zip"

upload: zip
	$(PLUGIN_UPLOAD) $(PLUGINNAME).zip

# transup
# update .ts translation files
transup:
	pylupdate4 Makefile

# transcompile
# compile translation files into .qm binary format
transcompile: $(TRANSLATIONS:.ts=.qm)

# transclean
# deletes all .qm files
transclean:
	rm -f i18n/*.qm

clean:
	rm $(UI_FILES) $(RESOURCE_FILES)

# build documentation with sphinx
doc: 
	cd help; make html
