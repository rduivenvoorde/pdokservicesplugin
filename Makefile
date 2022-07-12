PLUGINNAME = pdokservicesplugin

VERSION=$(shell cat pdokservicesplugin/metadata.txt | grep version= | sed -e 's,version=,,')

zip:
	@echo
	@echo "---------------------------"
	@echo "Creating plugin zip bundle."
	@echo "---------------------------"
	# The zip target deploys the plugin and creates a zip file with the deployed
	# content. You can then upload the zip file on http://plugins.qgis.org or install from within QGIS
	#$(CURDIR)/repo$(CURDIR)/repo First remove an maybe already available older zip (with same version number)
	mkdir -p $(CURDIR)/repo
	rm -f $(CURDIR)/repo/$(PLUGINNAME).$(VERSION).zip
	zip -9r $(CURDIR)/repo/$(PLUGINNAME).$(VERSION).zip $(PLUGINNAME) -x *.pyc -x *__pycache__*
	@echo Successfully created zip: $(CURDIR)/repo/$(PLUGINNAME).$(VERSION).zip
