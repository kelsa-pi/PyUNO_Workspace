# -*- coding: utf-8 -*-
# PyUNO Workspace helper module

import platform


def configStringToInt(bstring):
    bint = 0
    if bstring == 'True':
        bint = 2
    return bint


# def getDocumentationBrowser():
#     """Determine documentation browser"""
#
#     help_browser = ''
#     if platform.system() == 'Linux':
#         help_browser = 'Zeal'
#     elif platform.system() == 'OSX':
#         help_browser = 'Dash'
#     elif platform.system() == 'Windows':
#         help_browser = 'Velocity'
#
#     return help_browser
    




    

