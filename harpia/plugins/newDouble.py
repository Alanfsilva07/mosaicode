#!/usr/bin/env python
 # -*- coding: utf-8 -*-

from harpia.constants import *
import gettext
_ = gettext.gettext
gettext.bindtextdomain(APP, DIR)
gettext.textdomain(APP)

from harpia.GUI.fieldtypes import *
from harpia.model.plugin import Plugin

class NewDouble(Plugin):

# ------------------------------------------------------------------------------
    def __init__(self):
        Plugin.__init__(self)
        self.id = -1
        self.type = self.__class__.__module__
        self.doubleVal = 1

    # ----------------------------------------------------------------------
    def get_help(self):#Função que chama a help
        return "Creates new literal value (Double)"

    # ----------------------------------------------------------------------
    def generate(self, blockTemplate):
        blockTemplate.imagesIO = 'double  block$$_double_o1; // New Double Out\n'

        blockTemplate.functionCall = 'block$$_double_o1 = ' + str(float(self.doubleVal)) + ';\n'

        blockTemplate.dealloc = ''

    # ----------------------------------------------------------------------
    def __del__(self):
        pass

    # ----------------------------------------------------------------------
    def get_description(self):
        return {"Type": str(self.type),
            'Label': _('New Double'),
            'Icon': 'images/newDouble.png',
            'Color': '50:50:200:150',
            'InTypes': "",
            'OutTypes': {0: 'HRP_DOUBLE'},
            'Description': _('Creates new literal value (Double)'),
            'TreeGroup': _('Basic Data Type'),
            "IsSource": True
            }

    # ----------------------------------------------------------------------
    def get_properties(self):
        return {
            "doubleVal":{"name": "Value",
                        "type": HARPIA_FLOAT,
                        "value": self.doubleVal,
                        "lower":0,
                        "upper":65535,
                        "step":1
                            }
        }

# ------------------------------------------------------------------------------
