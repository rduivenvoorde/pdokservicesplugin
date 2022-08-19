from PyQt5.QtCore import QSettings

# QSettings holds variables as list or dict or str.
# if int or bool value is set, they are converted to str in the Class.
# In particular, isVectorEnabled is treated as bool by cast str '0' or '1' to int(bool).

import logging

log = logging.getLogger(__name__)


class SettingsManager:
    SETTING_GROUP = "pdokservicesplugin"

    def get_setting(self, key):

        qsettings = QSettings()
        qsettings.beginGroup(self.SETTING_GROUP)
        value = qsettings.value(key)
        qsettings.endGroup()
        if value:
            log.debug(f"{self.SETTING_GROUP}/{key}")
            log.debug(value)
            return value
        return None

    def store_setting(self, key, value):
        qsettings = QSettings()
        qsettings.beginGroup(self.SETTING_GROUP)
        qsettings.setValue(key, value)
        qsettings.endGroup()

    def delete_setting(self, key):
        qsettings = QSettings()
        qsettings.beginGroup(self.SETTING_GROUP)
        qsettings.remove(key)
        qsettings.endGroup()
