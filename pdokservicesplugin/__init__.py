from .pdokservicesplugin import PdokServicesPlugin

def classFactory(iface):
    return PdokServicesPlugin(iface)
