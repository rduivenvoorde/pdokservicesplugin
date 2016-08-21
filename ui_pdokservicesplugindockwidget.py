# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_pdokservicesplugindockwidget.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_PDOKservices(object):
    def setupUi(self, PDOKservices):
        PDOKservices.setObjectName(_fromUtf8("PDOKservices"))
        PDOKservices.resize(565, 756)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(PDOKservices.sizePolicy().hasHeightForWidth())
        PDOKservices.setSizePolicy(sizePolicy)
        self.dockWidgetContents = QtGui.QWidget()
        self.dockWidgetContents.setObjectName(_fromUtf8("dockWidgetContents"))
        self.verticalLayout_4 = QtGui.QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout_4.setObjectName(_fromUtf8("verticalLayout_4"))
        self.tabWidget = QtGui.QTabWidget(self.dockWidgetContents)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tabWidget.sizePolicy().hasHeightForWidth())
        self.tabWidget.setSizePolicy(sizePolicy)
        self.tabWidget.setObjectName(_fromUtf8("tabWidget"))
        self.tab_2 = QtGui.QWidget()
        self.tab_2.setObjectName(_fromUtf8("tab_2"))
        self.gridLayout_2 = QtGui.QGridLayout(self.tab_2)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.servicesView = QtGui.QTableView(self.tab_2)
        self.servicesView.setMinimumSize(QtCore.QSize(0, 0))
        self.servicesView.setObjectName(_fromUtf8("servicesView"))
        self.gridLayout_2.addWidget(self.servicesView, 1, 0, 1, 2)
        self.btnLoadLayer = QtGui.QPushButton(self.tab_2)
        self.btnLoadLayer.setEnabled(False)
        self.btnLoadLayer.setObjectName(_fromUtf8("btnLoadLayer"))
        self.gridLayout_2.addWidget(self.btnLoadLayer, 4, 0, 1, 2)
        self.label = QtGui.QLabel(self.tab_2)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout_2.addWidget(self.label, 0, 0, 1, 1)
        self.layerSearch = QtGui.QLineEdit(self.tab_2)
        self.layerSearch.setObjectName(_fromUtf8("layerSearch"))
        self.gridLayout_2.addWidget(self.layerSearch, 0, 1, 1, 1)
        self.layerInfo = QtGui.QTextEdit(self.tab_2)
        self.layerInfo.setMaximumSize(QtCore.QSize(16777215, 200))
        self.layerInfo.setObjectName(_fromUtf8("layerInfo"))
        self.gridLayout_2.addWidget(self.layerInfo, 2, 0, 1, 2)
        self.tabWidget.addTab(self.tab_2, _fromUtf8(""))
        self.tab_3 = QtGui.QWidget()
        self.tab_3.setObjectName(_fromUtf8("tab_3"))
        self.gridLayout_4 = QtGui.QGridLayout(self.tab_3)
        self.gridLayout_4.setObjectName(_fromUtf8("gridLayout_4"))
        self.geocoderSearch = QtGui.QLineEdit(self.tab_3)
        self.geocoderSearch.setText(_fromUtf8(""))
        self.geocoderSearch.setObjectName(_fromUtf8("geocoderSearch"))
        self.gridLayout_4.addWidget(self.geocoderSearch, 0, 0, 1, 2)
        self.geocoderSearchBtn = QtGui.QPushButton(self.tab_3)
        self.geocoderSearchBtn.setObjectName(_fromUtf8("geocoderSearchBtn"))
        self.gridLayout_4.addWidget(self.geocoderSearchBtn, 0, 2, 1, 1)
        self.label_2 = QtGui.QLabel(self.tab_3)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout_4.addWidget(self.label_2, 1, 0, 1, 1)
        self.geocoderResultSearch = QtGui.QLineEdit(self.tab_3)
        self.geocoderResultSearch.setObjectName(_fromUtf8("geocoderResultSearch"))
        self.gridLayout_4.addWidget(self.geocoderResultSearch, 1, 1, 1, 2)
        self.geocoderResultView = QtGui.QTableView(self.tab_3)
        self.geocoderResultView.setObjectName(_fromUtf8("geocoderResultView"))
        self.gridLayout_4.addWidget(self.geocoderResultView, 2, 0, 1, 3)
        self.tabWidget.addTab(self.tab_3, _fromUtf8(""))
        self.tab_4 = QtGui.QWidget()
        self.tab_4.setObjectName(_fromUtf8("tab_4"))
        self.verticalLayout = QtGui.QVBoxLayout(self.tab_4)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.groupBox = QtGui.QGroupBox(self.tab_4)
        self.groupBox.setObjectName(_fromUtf8("groupBox"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.label_3 = QtGui.QLabel(self.groupBox)
        self.label_3.setWordWrap(True)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.verticalLayout_2.addWidget(self.label_3)
        self.label_4 = QtGui.QLabel(self.groupBox)
        self.label_4.setWordWrap(True)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.verticalLayout_2.addWidget(self.label_4)
        self.btn_check_pdokjson = QtGui.QPushButton(self.groupBox)
        self.btn_check_pdokjson.setObjectName(_fromUtf8("btn_check_pdokjson"))
        self.verticalLayout_2.addWidget(self.btn_check_pdokjson)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem)
        self.verticalLayout.addWidget(self.groupBox)
        self.groupBox_2 = QtGui.QGroupBox(self.tab_4)
        self.groupBox_2.setObjectName(_fromUtf8("groupBox_2"))
        self.verticalLayout_3 = QtGui.QVBoxLayout(self.groupBox_2)
        self.verticalLayout_3.setObjectName(_fromUtf8("verticalLayout_3"))
        self.label_5 = QtGui.QLabel(self.groupBox_2)
        self.label_5.setWordWrap(True)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.verticalLayout_3.addWidget(self.label_5)
        self.radio_dialog = QtGui.QRadioButton(self.groupBox_2)
        self.radio_dialog.setEnabled(True)
        self.radio_dialog.setChecked(True)
        self.radio_dialog.setObjectName(_fromUtf8("radio_dialog"))
        self.verticalLayout_3.addWidget(self.radio_dialog)
        self.radio_docked_widget = QtGui.QRadioButton(self.groupBox_2)
        self.radio_docked_widget.setObjectName(_fromUtf8("radio_docked_widget"))
        self.verticalLayout_3.addWidget(self.radio_docked_widget)
        self.verticalLayout.addWidget(self.groupBox_2)
        spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem1)
        self.tabWidget.addTab(self.tab_4, _fromUtf8(""))
        self.tab = QtGui.QWidget()
        self.tab.setObjectName(_fromUtf8("tab"))
        self.webView = QtGui.QTextBrowser(self.tab)
        self.webView.setGeometry(QtCore.QRect(0, 0, 789, 669))
        self.webView.setObjectName(_fromUtf8("webView"))
        self.tabWidget.addTab(self.tab, _fromUtf8(""))
        self.verticalLayout_4.addWidget(self.tabWidget)
        PDOKservices.setWidget(self.dockWidgetContents)

        self.retranslateUi(PDOKservices)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(PDOKservices)

    def retranslateUi(self, PDOKservices):
        PDOKservices.setWindowTitle(_translate("PDOKservices", "PDOK services", None))
        self.btnLoadLayer.setText(_translate("PDOKservices", "Laad deze laag in QGIS (of dubbelklik op de regel)", None))
        self.label.setText(_translate("PDOKservices", "Zoeken: ", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), _translate("PDOKservices", "PDOK services", None))
        self.geocoderSearchBtn.setText(_translate("PDOKservices", "Zoek", None))
        self.label_2.setText(_translate("PDOKservices", "Filter resultaten op:", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), _translate("PDOKservices", "PDOK geocoder", None))
        self.groupBox.setTitle(_translate("PDOKservices", "PDOK services check", None))
        self.label_3.setText(_translate("PDOKservices", "Er worden periodiek nieuwe services of lagen toegevoegd aan de PDOK services.", None))
        self.label_4.setText(_translate("PDOKservices", "Klik op de Check services button om te kijken of er op qgis.nl een nieuw configuratie bestand beschikbaar is.", None))
        self.btn_check_pdokjson.setText(_translate("PDOKservices", "Check services", None))
        self.groupBox_2.setTitle(_translate("PDOKservices", "Docked widget of Dialoog", None))
        self.label_5.setText(_translate("PDOKservices", "De plugin kan zich tonen als een losse Dialoog, of zich als een Docked Widget gedragen (QGIS herstart vereist).", None))
        self.radio_dialog.setText(_translate("PDOKservices", "Losse dialoog", None))
        self.radio_docked_widget.setText(_translate("PDOKservices", "Docked widget", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), _translate("PDOKservices", "Extra", None))
        self.webView.setHtml(_translate("PDOKservices", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'Cantarell\'; font-size:11pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:18px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:xx-large; font-weight:600; color:#444444;\">QGIS plugin voor PDOK services</span><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\"> </span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">Deze plugin wordt gemaakt door Richard Duivenvoorde (</span><a href=\"http://www.zuidt.nl\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; text-decoration: underline; color:#0000ff;\">Zuidt</span></a><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">).<br />De code van deze plugin is te vinden op </span><a href=\"https://github.com/rduivenvoorde/pdokservicesplugin\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; text-decoration: underline; color:#0000ff;\">Github</span></a><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">. Bugs kunt u daar melden. </span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><img src=\":/plugins/pdokservicesplugin/pdok.png\" /></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><a href=\"http://www.pdok.nl\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; text-decoration: underline; color:#0000ff;\">PDOK</span></a><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\"> stelt webservices beschikbaar van landsdekkende geo-informatie afkomstig van overheden. Deze data komen rechtstreeks bij de bron vandaan, d.w.z. dat overheidsorganisaties bronhouder van deze data zijn. Daardoor zijn de data actueel en betrouwbaar. Bovendien zijn ze door elke afnemer (overheid, bedrijf, particulier) kosteloos te gebruiken. </span></p>\n"
"<p style=\" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">Service url\'s voor alle in de plugin aanwezige lagen zijn afkomstig van deze pagina:<br /></span><a href=\"https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; text-decoration: underline; color:#0000ff;\">https://www.pdok.nl/nl/producten/pdok-services/overzicht-urls</span></a><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">. </span></p>\n"
"<p style=\" margin-top:16px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:x-large; font-weight:600; color:#444444;\">OpenGeoGroep. Anders denken, Anders doen...</span></p>\n"
"<p style=\" margin-top:16px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\">De </span><a href=\"http://www.opengeogroep.nl\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; text-decoration: underline; color:#0000ff;\">OpenGeoGroep</span></a><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\"> is een commerciele ICT-dienstverlener die diensten en oplossingen biedt voor geo-informatie vraagstukken. Al onze diensten zijn leveranciersonafhankelijk. De OpenGeoGroep onderscheidt zich door het aanbieden van diensten en innovatieve oplossingen gebaseerd op professionele Open Source Software en op basis van Open Standaarden.</span></p>\n"
"<p style=\" margin-top:16px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-family:\'Helvetica Neue,Helvetica,Arial,sans-serif\'; font-size:15px; font-weight:296; color:#444444;\"> </span><img src=\":/plugins/pdokservicesplugin/ogg.gif\" /></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), _translate("PDOKservices", "OpenGeoGroep en PDOK", None))

import resources_rc
