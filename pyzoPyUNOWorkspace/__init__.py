# -*- coding: utf-8 -*-
# Copyright (C) 2013, the Pyzo development team
#
# Pyzo is distributed under the terms of the (new) BSD License.
# The full license can be found in 'license.txt'.


import os, re, sys, time
import subprocess, threading, time
import webbrowser

import pyzo
from pyzo.util.qt import QtCore, QtGui, QtWidgets

import configparser

from .helper import configStringToInt, getDocumentationBrowser

tool_name = "PyUNO Workspace"
tool_summary = "Lists Python and PyUNO variables in the current shell's namespace."

# Read configuration
full_path = os.path.dirname(__file__)
conf_file = os.path.join(full_path, 'config.ini')
config = configparser.ConfigParser()
config.read(conf_file)

# Get configuration options
conf_dash = configStringToInt(config.get('GENERAL', 'dash'))
conf_unostarter = configStringToInt(config.get('GENERAL', 'unostarter'))

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

# Set documentation browser
help_browser = getDocumentationBrowser()

# Set workspace context menu    
workspace_menu = getWorkspaceMenu(help_browser)

# Frequently used argument 
drill = ['getByIndex', 'getByName', 'getCellByPosition', 'getCellRangeByPosition', 'getCellRangesByName']


def splitName(name):
    """ splitName(name)
    Split an object name in parts, taking dots and indexing into account.
    """
    name = name.replace('[', '.[')
    parts = name.split('.')
    return [p for p in parts if p]


def joinName(parts):
    """ joinName(parts)
    Join the parts of an object name, taking dots and indexing into account.
    """
    name = '.'.join(parts)
    return name.replace('.[', '[')


class PyUNOWorkspaceProxy(QtCore.QObject):
    """ WorkspaceProxy

    A proxy class to handle the asynchonous behaviour of getting information
    from the shell. The workspace tool asks for a certain name, and this
    class notifies when new data is available using a qt signal.

    """

    haveNewData = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)

        # Variables
        self._variables = []

        # Element to get more info of
        self._name = ''

        # Bind to events
        self._variables = []

        # Element to get more info of
        self._name = ''

        # Bind to events
        pyzo.shells.currentShellChanged.connect(self.onCurrentShellChanged)
        pyzo.shells.currentShellStateChanged.connect(self.onCurrentShellStateChanged)

        # Initialize
        self.onCurrentShellStateChanged()

    def addNamePart(self, part):
        """ addNamePart(part)
        Add a part to the name.
        """
        parts = splitName(self._name)
        parts.append(part)
        self.setName(joinName(parts))

    def setName(self, name):
        """ setName(name)
        Set the name that we want to know more of.
        """
        self._name = name

        shell = pyzo.shells.getCurrentShell()
        if shell:
            future = shell._request.dir2(self._name)
            future.add_done_callback(self.processResponse)

    def goUp(self):
        """ goUp()
        Cut the last part off the name.
        """
        parts = splitName(self._name)
        if parts:
            parts.pop()
        self.setName(joinName(parts))

    def onCurrentShellChanged(self):
        """ onCurrentShellChanged()
        When no shell is selected now, update this. In all other cases,
        the onCurrentShellStateChange will be fired too.
        """
        shell = pyzo.shells.getCurrentShell()
        if not shell:
            self._variables = []
            self.haveNewData.emit()

    def onCurrentShellStateChanged(self):
        """ onCurrentShellStateChanged()
        Do a request for information!
        """
        shell = pyzo.shells.getCurrentShell()
        if not shell:
            # Should never happen I think, but just to be sure
            self._variables = []
        elif shell._state.lower() != 'busy':
            future = shell._request.dir2(self._name)
            future.add_done_callback(self.processResponse)

    def processResponse(self, future):
        """ processResponse(response)
        We got a response, update our list and notify the tree.
        """

        response = []

        # Process future
        if future.cancelled():
            pass  # print('Introspect cancelled') # No living kernel
        elif future.exception():
            print('Introspect-queryDoc-exception: ', future.exception())
        else:
            response = future.result()

        self._variables = response
        self.haveNewData.emit()


class PyUNOWorkspaceItem(QtWidgets.QTreeWidgetItem):
    def __lt__(self, otherItem):
        column = self.treeWidget().sortColumn()
        try:
            return float(self.text(column).strip('[]')) > float(otherItem.text(column).strip('[]'))
        except ValueError:
            return self.text(column) > otherItem.text(column)


class PyUNOWorkspaceTree(QtWidgets.QTreeWidget):
    """ WorkspaceTree

    The tree that displays the items in the current namespace.
    I first thought about implementing this using the mode/view
    framework, but it is so much work and I can't seem to fully
    understand how it works :(

    The QTreeWidget is so very simple and enables sorting very
    easily, so I'll stick with that ...

    """

    def __init__(self, parent):
        QtWidgets.QTreeWidget.__init__(self, parent)

        self._config = parent._config
        self.old_item = ''

        # Set header stuff
        self.setHeaderHidden(False)
        self.setColumnCount(3)
        self.setHeaderLabels(['Name', 'Type', 'Repr'])
        # self.setColumnWidth(0, 100)
        self.setSortingEnabled(True)

        # Nice rows
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

        # Create proxy
        self._proxy = PyUNOWorkspaceProxy()
        self._proxy.haveNewData.connect(self.fillWorkspace)

        # For menu
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self._menu = QtWidgets.QMenu()
        self._menu.triggered.connect(self.contextMenuTriggered)

        # Bind to events
        self.itemActivated.connect(self.onItemExpand)

    def contextMenuEvent(self, event):
        """ contextMenuEvent(event)
        Show the context menu.
        """

        QtWidgets.QTreeView.contextMenuEvent(self, event)

        # Get if an item is selected
        item = self.currentItem()
        if not item:
            return

        # Create menu
        self._menu.clear()

        for a in workspace_menu:
            if a == 'sep':
                self._menu.addSeparator()
            else:
                action = self._menu.addAction(a)
                parts = splitName(self._proxy._name)
                parts.append(item.text(0))
                action._objectName = joinName(parts)
                action._item = item

        # Show
        self._menu.popup(QtGui.QCursor.pos() + QtCore.QPoint(3, 3))

    def contextMenuTriggered(self, action):
        """ contextMenuTriggered(action)
        Process a request from the context menu.
        """

        # Get text
        req = action.text().lower()
        # Get current shell
        shell = pyzo.shells.getCurrentShell()

        search = splitName(action._objectName)
        ob = '.'.join(search[:-1])
        search = search[-1]

        if 'namespace' in req:
            # Go deeper
            self.onItemExpand(action._item)

        elif 'help' in req:
            # Show help in help tool (if loaded)
            hw = pyzo.toolManager.getTool('pyzointeractivehelp')
            if hw:
                hw.setObjectName(action._objectName)

        # PyUNO
        elif help_browser.lower() in req:
            # Search in Dash-like offline browser
            t = threading.Thread(None, subprocess.call([help_browser.lower(), search]))
            t.start()

        elif 'forum' in req:
            # Search in forum
            url = 'https://forum.openoffice.org/en/forum/search.php?keywords=' + search + '&fid[0]=20'
            webbrowser.open(url)

        elif 'snippets' in req:
            # Search in forum snippets
            url = 'https://forum.openoffice.org/en/forum/search.php?keywords=' + search + '&fid[0]=21'
            webbrowser.open(url)

        elif 'pyuno_callable' in req:
            # Inspect PyUNO_callable type in shell
            shell.executeCommand("out= Inspector().inspect(" + ob + ", item='" + search + "', console='yes')\n")

        elif 'pyuno' in req:
            # Inspect pyuno type in shell
            a_name = str(action._objectName)
            shell.executeCommand("out= Inspector().inspect(" + a_name + ", console='yes')\n")

        elif 'delete' in req:
            # Delete the variable
            if shell:
                shell.processLine('del ' + action._objectName)

    def onItemExpand(self, item):
        """ onItemExpand(item)
        Inspect the attributes of that item.
        # """

        # ADD
        # line = self.parent()._line
        # argument line
        argument = self.parent()._argument_line.text()
        inspect_item = item.text(0)

        if argument:
            inspect_item = inspect_item + '(' + argument + ')'
        else:
            if inspect_item.startswith('get'):
                inspect_item = inspect_item + '()'

        # set item for inspection
        self._proxy.addNamePart(inspect_item)

        # clear argument line
        self.parent()._argument_line.clear()

    def fillWorkspace(self):
        """ fillWorkspace()
        Update the workspace tree.
        """

        # Clear first
        self.clear()

        # Set name
        line = self.parent()._line
        line.setText(self._proxy._name)

        # Add elements
        for des in self._proxy._variables:

            # Get parts
            parts = des.split(',', 4)
            if len(parts) < 4:
                continue

            name = parts[0]

            # Pop the 'kind' element
            kind = parts.pop(2)

            if kind in self._config.hideTypes:
                continue
            if name.startswith('_') and 'private' in self._config.hideTypes:
                continue

            # Create item
            item = PyUNOWorkspaceItem(parts, 0)
            self.addTopLevelItem(item)

            # Set background color for special methods
            if name in drill:
                item.setBackground(0, QtGui.QColor(224, 224, 224))

            # Set tooltip
            tt = '%s: %s' % (parts[0], parts[-1])
            item.setToolTip(0, tt)
            item.setToolTip(1, tt)
            item.setToolTip(2, tt)


class PyzoPyUNOWorkspace(QtWidgets.QWidget):
    """ PyzoWorkspace

    The main widget for this tool.

    """

    def __init__(self, parent):
        QtWidgets.QWidget.__init__(self, parent)

        # Make sure there is a configuration entry for this tool
        # The pyzo tool manager makes sure that there is an entry in
        # config.tools before the tool is instantiated.
        toolId = self.__class__.__name__.lower()
        self._config = pyzo.config.tools[toolId]
        if not hasattr(self._config, 'hideTypes'):
            self._config.hideTypes = []

        style = QtWidgets.qApp.style()

        self.argument_tip = 'Add argument and duble clik on method'

        # Create tool button
        self._up = QtWidgets.QToolButton(self)
        style = QtWidgets.qApp.style()
        self._up.setIcon(style.standardIcon(style.SP_ArrowLeft))
        self._up.setIconSize(QtCore.QSize(16, 16))
        self._up.setToolTip("Go back")

        # Create "path" line edit
        self._line = QtWidgets.QLineEdit(self)
        self._line.setReadOnly(True)
        self._line.setStyleSheet("QLineEdit { background:#ddd; }")
        self._line.setFocusPolicy(QtCore.Qt.NoFocus)

        # Create "insert_code" button
        self._insert_code = QtWidgets.QToolButton(self)
        self._insert_code.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))
        self._insert_code.setToolTip("Insert code in the script at the cursor position")

        # Create "argument_line" line edit
        self._argument_line = QtWidgets.QLineEdit(self)
        self._argument_line.setReadOnly(False)
        self._argument_line.setToolTip(self.argument_tip)

        # Create "argument_label" label
        self._argument_label = QtWidgets.QLabel(self)
        self._argument_label.setText("Argument: ")

        # Create option line
        self._option_label = QtWidgets.QLabel(self)
        self._option_label.setText("Options: ")
        self._dash = QtWidgets.QCheckBox(self)
        self._dash.setText('Dash')
        self._dash.setCheckState(conf_dash)

        self._unostarter = QtWidgets.QCheckBox(self)
        self._unostarter.setText('UNOstarter')
        self._unostarter.setCheckState(conf_unostarter)

        self._option_save = QtWidgets.QToolButton(self)
        self._option_save.setText('Save')

        # Create options menu
        self._options = QtWidgets.QToolButton(self)
        self._options.setIcon(pyzo.icons.filter)
        self._options.setIconSize(QtCore.QSize(16, 16))
        self._options.setPopupMode(self._options.InstantPopup)
        self._options.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._options._menu = QtWidgets.QMenu()
        self._options.setMenu(self._options._menu)
        self.onOptionsPress()  # create menu now

        # Create tree
        self._tree = PyUNOWorkspaceTree(self)

        # Set layouts
        layout_1 = QtWidgets.QHBoxLayout()
        layout_1.addWidget(self._up, 0)
        layout_1.addWidget(self._line, 1)
        layout_1.addWidget(self._insert_code, 0)

        layout_2 = QtWidgets.QHBoxLayout()
        layout_2.addWidget(self._argument_label, 0)
        layout_2.addWidget(self._argument_line, 0)
        layout_2.addWidget(self._options, 0)

        layout_3 = QtWidgets.QVBoxLayout()
        layout_3.addWidget(self._tree, 0)

        layout_4 = QtWidgets.QHBoxLayout()
        layout_4.addWidget(self._option_label, 0)
        layout_4.addWidget(self._dash, 0)
        layout_4.addWidget(self._unostarter, 0)
        layout_4.addWidget(self._option_save, 0)

        # Set main layout
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.addLayout(layout_1, 0)
        mainLayout.addLayout(layout_2, 0)
        mainLayout.addLayout(layout_3, 0)
        mainLayout.addLayout(layout_4, 0)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(mainLayout)

        # Bind events
        self._up.pressed.connect(self._tree._proxy.goUp)
        self._insert_code.pressed.connect(self.onWriteCodePress)
        self._options.pressed.connect(self.onOptionsPress)
        self._options._menu.triggered.connect(self.onOptionMenuTiggered)
        self._option_save.pressed.connect(self.onOptionsSave)

    def onOptionsSave(self):
        """ Save options """
        config.set('GENERAL', 'dash', str(self._dash.isChecked()))
        config.set('GENERAL', 'unostarter', str(self._unostarter.isChecked()))

        with open(conf_file, 'w') as configfile:
            config.write(configfile)

    def onOptionsPress(self):
        """ Create the menu for the button, Do each time to make sure
        the checks are right. """

        # Get menu
        menu = self._options._menu
        menu.clear()

        for type in ['type', 'function', 'module', 'private']:
            checked = type in self._config.hideTypes
            action = menu.addAction('Hide %s' % type)
            action.setCheckable(True)
            action.setChecked(checked)

    def onOptionMenuTiggered(self, action):
        """  The user decides what to hide in the workspace. """

        # What to show
        type = action.text().split(' ', 1)[1]

        # Swap
        if type in self._config.hideTypes:
            while type in self._config.hideTypes:
                self._config.hideTypes.remove(type)
        else:
            self._config.hideTypes.append(type)

        # Update
        self._tree.fillWorkspace()

    def getCode(self):
        """
        """
        line = str(self._line.text())
        data = line.split('.')
        target = 'initial_target'
        code = ''
        for index in range(0, len(data)):
            try:
                if index == 0:
                    code = target + ' = ' + data[index] + '.' + data[index + 1] + '\n    '
                else:
                    first_item = target
                    try:
                        if data[index + 1].startswith('getByIndex') or data[index + 1].startswith('getByName'):
                            target = 'item'
                        else:
                            words = re.findall('[A-Z][^A-Z]*', data[index + 1])
                            second = words[len(words) - 1].lower()
                            second = second.split('(')
                            target = second[0]
                        code = code + target + ' = ' + first_item + '.' + data[index + 1] + '\n    '
                    except:
                        pass
            except:
                pass
        new_code = code
        return new_code

    def onWriteCodePress(self):
        """ fill playground
        Update the code generation.
        """
        code = self.getCode()
        editor = pyzo.editors.getCurrentEditor()
        editor.insertPlainText(code)
