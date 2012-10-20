# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_pdokservicesplugin.ui'
#
# Created: Tue Oct 16 14:58:38 2012
#      by: PyQt4 UI code generator 4.8.5
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

class Ui_PdokServicesPlugin(object):
    def setupUi(self, PdokServicesPlugin):
        PdokServicesPlugin.setObjectName(_fromUtf8("PdokServicesPlugin"))
        PdokServicesPlugin.resize(510, 383)
        PdokServicesPlugin.setWindowTitle(QtGui.QApplication.translate("PdokServicesPlugin", "PdokServicesPlugin", None, QtGui.QApplication.UnicodeUTF8))
        self.gridLayout = QtGui.QGridLayout(PdokServicesPlugin)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.buttonBox = QtGui.QDialogButtonBox(PdokServicesPlugin)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.gridLayout.addWidget(self.buttonBox, 2, 1, 1, 1)
        self.layerSearch = QtGui.QLineEdit(PdokServicesPlugin)
        self.layerSearch.setObjectName(_fromUtf8("layerSearch"))
        self.gridLayout.addWidget(self.layerSearch, 0, 1, 1, 1)
        self.label = QtGui.QLabel(PdokServicesPlugin)
        self.label.setText(QtGui.QApplication.translate("PdokServicesPlugin", "Filter:", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.servicesListView = QtGui.QListView(PdokServicesPlugin)
        self.servicesListView.setObjectName(_fromUtf8("servicesListView"))
        self.gridLayout.addWidget(self.servicesListView, 1, 0, 1, 2)

        self.retranslateUi(PdokServicesPlugin)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), PdokServicesPlugin.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), PdokServicesPlugin.reject)
        QtCore.QMetaObject.connectSlotsByName(PdokServicesPlugin)

    def retranslateUi(self, PdokServicesPlugin):
        pass

import resources_rc
