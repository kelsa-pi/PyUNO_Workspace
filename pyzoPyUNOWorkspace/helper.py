# -*- coding: utf-8 -*-

import platform


def configStringToInt(bstring):
    bint = 0
    if bstring == 'True':
        bint = 2
    return bint


def getDocumentationBrowser():
    """Determine documentation browser"""
    
    help_browser = ''
    if platform.system() == 'Linux':
        help_browser = 'Zeal'
    elif platform.system() == 'OSX':
        help_browser = 'Dash'
    elif platform.system() == 'Windows':
        help_browser = 'Velocity'
    
    return help_browser


def getWorkspaceMenu(help_browser):
    """Set wokspace context menu"""
    workspace_menu = ['Show namespace', 'Show help', 'Delete', 'sep', 'Search in forum', 'Search snippets']
    dash_menu = ['sep', 'Search in ' + help_browser]
    unostarter_menu = ['sep', 'Inspect in shell - pyuno', 'Inspect in shell - PyUNO_callable']

    if conf_dash == 2:
        workspace_menu = workspace_menu + dash_menu

    if conf_unostarter == 2:
        workspace_menu = workspace_menu + unostarter_menu

    return workspace_menu
    

