# -*- coding: utf-8 -*-
# Copyright (C) 2013, the Pyzo development team
#
# Pyzo is distributed under the terms of the (new) BSD License.
# The full license can be found in 'license.txt'.
#
# PyUNO Workspace is a modified version of Pyzo's Workspace tool,
# designed for Python and PyUno introspection.
# Author: Sasa Kelecevic, 2017

import configparser
import os
import re
from json import load
from inspect import getsourcefile
import sqlite3
import webbrowser
import pyzo
from pyzo.util.qt import QtCore, QtGui, QtWidgets
from .helper import configStringToInt

tool_name = pyzo.translate("pyzoPyUNOWorkspace", "PyUNO Workspace")
tool_summary = "Lists Python and PyUNO variables in the current shell's namespace."

# Constants
WORKSPACE_INIT = os.path.abspath(getsourcefile(lambda: 0))
WORKSPACE_DIR = os.path.dirname(WORKSPACE_INIT)

# Read configuration
conf_file = os.path.join(WORKSPACE_DIR, 'config.ini')
config = configparser.ConfigParser()
config.read(conf_file)

# JSON serialization paths
RESULTFILE = 'result.txt'

RESULT = os.path.join(WORKSPACE_DIR, RESULTFILE)
with open(RESULT, 'w') as jfile:
    jfile.write('{}')

# documentation database
UNODOC_DB = os.path.join(WORKSPACE_DIR, 'unoDoc.db')
conn = sqlite3.connect(UNODOC_DB)

# Checked items
checked_dict= {}

def splitName(name):
    """ splitName(name)
    Split an object name in parts, taking dots and indexing into account.
    """
    name = name.replace('[', '.[')
    parts = name.split('.')
    return [p for p in parts if p]
        

def splitNameCleaner(name):
    """ splitNameCleaner(name)
    Split an object name in parts, taking dots, quotes, indexing etc. into account.
    Object name with extra dots eg. ctx.getByName("/singletons/com.sun.star.beans.theIntrospection"),
    enumerated objects eg. list(document.Text)
    """
    name = name.replace('[', '.[')
    parts = name.split('.')

    # Fix extra dots
    if '"' in parts[-1]:
        extra_dots = re.findall(r'"(.*?)"', name)
        if extra_dots:
            for part in extra_dots:
                new = part.replace('.', '_')
                new_name = name.replace(part, new)
            
            new_parts = new_name.split('.')
            np = [p for p in new_parts if p]
        
    else:

        np = [p for p in parts if p]

    # Fix list
    if np[0].startswith('list(') and np[-1].endswith(')'):
        np[0] = np[0].replace('list(', '')
        np[-1] = np[-1][:-1]
        np.append(np[-1])
    
    return np


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
        self._uno_dict = {}
        
        # Element to get more info of
        self._name = ''

        # Bind to events
        # self._variables = []

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
            # via unoinspect
            if str(self._name) == '':
                pass
            else:
                shell.executeCommand("Inspector().inspect(" + str(self._name) + ", result='m')\n")
            # via pyzo
            future = shell._request.dir2(self._name)
            future.add_done_callback(self.processResponse)
            
    def goUp(self):
        """ goUp()
        Cut the last part off the name.
        """
        parts = splitNameCleaner(self._name)
       
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
            self._uno_dict = {}
            self.haveNewData.emit()

    def onCurrentShellStateChanged(self):
        """ onCurrentShellStateChanged()
        Do a request for information!
        """
        shell = pyzo.shells.getCurrentShell()
        if not shell:
            # Should never happen I think, but just to be sure
            self._variables = []
            self._uno_dict = {}
            
        elif shell._state.lower() != 'busy':
            # via pyzo
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
        
        # via pyzo
        self._variables = response
        
        # via unoinspect - read json
        myfile = os.path.join(WORKSPACE_DIR, RESULTFILE) 
        with open(myfile) as resultf:
            self._uno_dict = load(resultf)
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
        # Set first column width
        self.setColumnWidth(0, 170)
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

        # menu items
        workspace_menu = ['Show namespace', 'Show help', 'Delete', 'sep', 'Search in forum', 'Search in snippets',
                          'sep', 'Check', 'Unmark']

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
        req = action.text()
        # Get current shell
        shell = pyzo.shells.getCurrentShell()

        search = splitName(action._objectName)
        ob = '.'.join(search[:-1])
        search = search[-1]
        
        if 'Show namespace' in req:
            # Go deeper
            self.onItemExpand(action._item)

        elif 'Show help' in req:
            # Show help in help tool (if loaded)
            hw = pyzo.toolManager.getTool('pyzointeractivehelp')
            if hw:
                hw.setObjectName(action._objectName)

        # ------- PyUNO ----------------

        elif 'Search in forum' in req:
            # Search in forum
            url = 'https://forum.openoffice.org/en/forum/search.php?keywords=' + search + '&fid[0]=20'
            webbrowser.open(url)

        elif 'Search in snippets' in req:
            # Search in forum snippets
            url = 'https://forum.openoffice.org/en/forum/search.php?keywords=' + search + '&fid[0]=21'
            webbrowser.open(url)

        elif 'Check' in req:
            # Check item
            if ob in checked_dict:
                if not search in checked_dict[ob]:
                    checked_dict[ob].append(search)
                    self.parent().onRefreshPress()
            else:
                checked_dict[ob] = []
                checked_dict[ob].append(search)
                self.parent().onRefreshPress()

        elif 'Unmark' in req:
            # Uncheck item
            if ob in checked_dict:
                if search in checked_dict[ob]:
                    checked_dict[ob].remove(search)
            
            self.parent().onRefreshPress()

        elif 'Delete' in req:
            # Delete the variable
            if shell:
                shell.processLine('del ' + action._objectName)

    def onItemExpand(self, item):
        """ onItemExpand(item)
        Inspect the attributes of that item.
        """

        # argument line
        argument = self.parent()._argument_line.text()
        inspect_item = item.text(0)

        if argument:
            inspect_item = inspect_item + '(' + argument + ')'
        else:
            if inspect_item.startswith('get'):
                inspect_item = inspect_item + '()'
            
            elif inspect_item in ['hasElements', 'isModified', 'createEnumeration', 'nextElement']:
                inspect_item = inspect_item + '()'
            
        # set item for inspection
        self._proxy.addNamePart(inspect_item)

        # clear argument line
        self.parent()._argument_line.clear()
        
    def resetWidget(self):
        """ resetWidget
        Reset widgets to default.
        """
        self.parent()._element_names.clear()
        self.parent()._element_index.clear()
        self.parent()._enumerate.setEnabled(False)
        self.parent()._element_names.setEnabled(False)
        self.parent()._element_index.setEnabled(False)
    
    def fillWidget(self):
        """ fillWidget
        Fill/activate widgets.
        """
        
        try:
            if self._proxy._uno_dict['getByName']['items']:
                self.parent()._element_names.addItem('--Name--')
                self.parent()._element_names.addItems(self._proxy._uno_dict['getByName']['items'])
                self.parent()._element_names.setEnabled(True)
        except:
            pass
            
        try:
            
            if self._proxy._uno_dict['getByIndex']['items']:
                self.parent()._element_index.addItem('--Index--')
                self.parent()._element_index.addItems(self._proxy._uno_dict['getByIndex']['items'])
                self.parent()._element_index.setEnabled(True)
        except:
            pass
            
        try:
            if self._proxy._uno_dict['createEnumeration']['items']:
                self.parent()._enumerate.setEnabled(True)
        except:
            pass

    def fillWorkspace(self):
        """ fillWorkspace()
        Update the workspace tree.
        """
        bChecked = False
        
        # Clear first
        self.clear()
        self.resetWidget()
        
        # Set name
        line = self.parent()._line
        line.setText(self._proxy._name)

        if self._proxy._name in checked_dict:
            bChecked = True
           
        # Fill widgets
        self.parent().onAddToHistory(line.text())
        self.fillWidget()
        
        # Add elements
        for des in self._proxy._variables:
            
            # Get parts
            parts = des.split(',', 4)
            
            if len(parts) < 4:
                continue

            name = parts[0]

            # Implementation name
            if name == 'ImplementationName':
                impl_name = parts[3].replace('com.sun.star', '~')
                self.parent()._impl_name.setText(impl_name )
            
            # Methods
            if name[0].islower() or name == 'HasExecutableCode':
                try:
                    parts[-1] = str(self._proxy._uno_dict[name]['repr'])
                    parts[1] = str(self._proxy._uno_dict[name]['type'])
                except:
                    pass

            # Pop the 'kind' element
            kind = parts.pop(2)

            if kind in self._config.hideTypes:
                continue
            if name.startswith('_') and 'private' in self._config.hideTypes:
                continue

            # Create item
            item = PyUNOWorkspaceItem(parts, 0)
            self.addTopLevelItem(item)

            # Set background color for checked items
            if bChecked:
                if name in checked_dict[self._proxy._name]:
                    item.setBackground(0, QtGui.QColor(224, 224, 224))
                    item.setBackground(1, QtGui.QColor(224, 224, 224))
                    item.setBackground(2, QtGui.QColor(224, 224, 224))
            else:
                item.setBackground(0, QtGui.QColor(255, 255, 255))
                item.setBackground(1, QtGui.QColor(255, 255, 255))
                item.setBackground(2, QtGui.QColor(255, 255, 255))
                

            # Set tooltip
            tt = '%s: %s' % (parts[0], parts[-1])
            item.setToolTip(0, tt)
            item.setToolTip(1, tt)
            item.setToolTip(2, tt)

        self.parent()._all.setChecked(True)

        # Clear UNO dict
        self._proxy._uno_dic = {}


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
            
        # JSON serialization file
        res = os.path.join(WORKSPACE_DIR, RESULTFILE)
        if not os.path.isfile(res):
            with open(res, 'w') as fl:
                fl.write('{}')
        
        style = QtWidgets.qApp.style()
        # ----- Layout 1 -----
        
        # Create Home tool button
        self._home = QtWidgets.QToolButton(self)
        self._home.setIcon(style.standardIcon(style.SP_ArrowUp))
        self._home.setIconSize(QtCore.QSize(16, 16))
        self._home.setToolTip("Home")
       
        # Create Refresh tool button
        self._refresh = QtWidgets.QToolButton(self)
        self._refresh.setIcon(style.standardIcon(style.SP_BrowserReload))
        self._refresh.setIconSize(QtCore.QSize(16, 16))
        self._refresh.setToolTip("Refresh")
        
        # Create Go back tool button
        self._up = QtWidgets.QToolButton(self)
        self._up.setIcon(style.standardIcon(style.SP_ArrowLeft))
        self._up.setIconSize(QtCore.QSize(16, 16))
        self._up.setToolTip("Go back")
        
        # Create "path" line edit
        self._line = QtWidgets.QLineEdit(self)
        self._line.setReadOnly(True)
        self._line.setStyleSheet("QLineEdit { background:#ddd; }")
        self._line.setFocusPolicy(QtCore.Qt.NoFocus)
        
        # Create enumerate tool button
        self._enumerate = QtWidgets.QToolButton(self)
        self._enumerate.setIcon(style.standardIcon(style.SP_ArrowDown))
        self._enumerate.setIconSize(QtCore.QSize(16, 16))
        self._enumerate.setToolTip("Enumerate")
        self._enumerate.setEnabled(False)
        
        # Create "insert_code" button
        self._insert_code = QtWidgets.QToolButton(self)
        self._insert_code.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))
        self._insert_code.setToolTip("Insert code in the script at the cursor position")
        
        # ----- Layout 2 -----
        
        # Create radio box All
        self._all = QtWidgets.QRadioButton(self)
        self._all.setText("Aa")
        self._all.setChecked(True)
        self._all.setToolTip("All")
        
        # Create radio box Properties
        self._only_p = QtWidgets.QRadioButton(self)
        self._only_p.setText("A")
        self._only_p.setToolTip("Uppercase")
        
        # Create radio box Methods
        self._only_m = QtWidgets.QRadioButton(self)
        self._only_m.setText("a")
        self._only_m.setToolTip("Lowercase")
        
        # Create radio box Checked
        self._only_star = QtWidgets.QRadioButton(self)
        # self._only_star.setIcon(style.standardIcon(style.SP_DialogApplyButton))
        self._only_star.setText("Checked")
        self._only_star.setToolTip("Checked")
        
        # Create element_index combo box
        self._element_index = QtWidgets.QComboBox(self)
        self._element_index.setToolTip("Get by index")
        self._element_index.setEnabled(False)
        
        # Create element_names combo box
        self._element_names = QtWidgets.QComboBox(self)
        self._element_names.setToolTip("Get by name")
        self._element_names.setEnabled(False)

        # Create history combo box
        self._history = QtWidgets.QComboBox(self)
        self._history.setToolTip("History")
        self._history.setEnabled(True)
        
        # Create options menu
        self._options = QtWidgets.QToolButton(self)
        self._options.setIcon(pyzo.icons.filter)
        self._options.setIconSize(QtCore.QSize(16, 16))
        self._options.setPopupMode(self._options.InstantPopup)
        self._options.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._options._menu = QtWidgets.QMenu()
        self._options.setMenu(self._options._menu)
        self.onOptionsPress()  # create menu now
        
        # ----- Layout 3 -----
        # Create tree
        self._tree = PyUNOWorkspaceTree(self)
        
        # ----- Layout4 -----
        
        # Create "argument_label" label
        self._argument_label = QtWidgets.QLabel(self)
        self._argument_label.setText("  Arguments: ")
        
        # Create "argument_line" line edit
        self._argument_line = QtWidgets.QLineEdit(self)
        self._argument_line.setReadOnly(False)
        self.argument_tip = 'Add argument and duble clik on method.\nExamples:\n"NAME" = object.getByName("NAME"),\n 0 = object.getByIndex(0),\n [space] = object.getMethod( )'
        self._argument_line.setToolTip(self.argument_tip)
        
        # Create "info_label" label
        self._info_label = QtWidgets.QLabel(self)
        self._info_label.setText("")
        
        # Create "impl_name" line edit
        self._impl_name = QtWidgets.QLabel(self)
        self._impl_name.setToolTip("Implementation name")
        self._impl_name.setStyleSheet("QLabel { background:#ddd; }")

        # General Option
        self._option_label = QtWidgets.QLabel(self)
        self._option_label.setText(" Options: ")
        #
        self._option_save = QtWidgets.QToolButton(self)
        self._option_save.setText("Save")
        self._option_save.setToolTip("Save all options")
        
        # ------ Set layouts
        
        # Layout 1: Object and insert code layout
        layout_1 = QtWidgets.QHBoxLayout()
        layout_1.addWidget(self._home, 0)
        layout_1.addWidget(self._refresh, 0)
        layout_1.addWidget(self._up, 0)
        layout_1.addWidget(self._line, 1)
        layout_1.addWidget(self._enumerate, 0)
        layout_1.addWidget(self._insert_code, 0)
        
        # Layout 2: Argument and option layout
        layout_2 = QtWidgets.QHBoxLayout()
        layout_2.addWidget(self._all, 0)
        layout_2.addWidget(self._only_p, 0)
        layout_2.addWidget(self._only_m, 0)
        layout_2.addWidget(self._only_star, 0)
        layout_2.addWidget(self._element_index, 0)
        layout_2.addWidget(self._element_names, 0)
        layout_2.addWidget(self._history, 1)
        layout_2.addWidget(self._options, 0)

        # Layout 3: Tree layout
        layout_3 = QtWidgets.QVBoxLayout()
        layout_3.addWidget(self._tree, 0)
        
        # Layout 4: Options layout
        layout_4 = QtWidgets.QHBoxLayout()
        layout_4.addWidget(self._argument_label, 0)
        layout_4.addWidget(self._argument_line, 1)
        layout_4.addWidget(self._info_label, 0)
        layout_4.addWidget(self._impl_name, 1)
        layout_4.addWidget(self._option_label, 0)
        layout_4.addWidget(self._option_save, 0)
        
        # Main Layout
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.addLayout(layout_1, 0)
        mainLayout.addLayout(layout_2, 0)
        mainLayout.addLayout(layout_3, 0)
        mainLayout.addLayout(layout_4, 0)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(mainLayout)

        # ------ Bind events

        self._home.pressed.connect(self.onHomePress)
        self._refresh.pressed.connect(self.onRefreshPress)
        self._up.pressed.connect(self._tree._proxy.goUp)
        self._enumerate.pressed.connect(self.onEnumeratePress)
        self._insert_code.pressed.connect(self.onInsertCodeInEditor)
        #
        self._all.toggled.connect(lambda:self.onRadioChangeState(self._all))
        self._only_p.toggled.connect(lambda:self.onRadioChangeState(self._only_p))
        self._only_m.toggled.connect(lambda:self.onRadioChangeState(self._only_m))
        self._only_star.toggled.connect(lambda:self.onRadioChangeState(self._only_star))
        #
        self._element_names.activated[str].connect(self.onElementNamesPress)
        self._element_index.activated[str].connect(self.onElementIndexPress)
        self._history.activated[str].connect(self.onBackToHistory)
        self._options.pressed.connect(self.onOptionsPress)
        self._options._menu.triggered.connect(self.onOptionMenuTiggered)
        #
        self._option_save.pressed.connect(self.onSaveOptionsInConf)

    # ---------------------------- 
    #           EVENTS
    # ----------------------------

    def onHomePress(self):
        """ Back to start """
        new_line = ''
        self._line.setText(new_line)
        self._tree._proxy.setName(new_line)
        
    def onRefreshPress(self):
        """ Refresh """
        # item = self._tree.currentItem()
        line = self._line.text()
        self._tree._proxy.setName(line)
    
    def getCodeSnippet(self):
        """
        """
        line = str(self._line.text())
        data = line.split('.')
        return self.createCodeSnippet(data)
    
    def createCodeSnippet(self, data):
        """ Create code snippet """
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

    def onInsertCodeInEditor(self):
        """ Insert code snippet in the editor. """
        
        code = self.getCodeSnippet()
        editor = pyzo.editors.getCurrentEditor()
        editor.insertPlainText(code)    

    #
    def onRadioChangeState(self, radiobox):
        """ Filter tree
        Show All, Uppercase or Lowercase elements
        """
        
        root = self._tree.invisibleRootItem()
        child_count = root.childCount()
        for i in range(child_count):
            item = root.child(i)
            name = item.text(0)
            # All
            if radiobox.text() == "Aa" and radiobox.isChecked() is True:
                if name[0].isupper() or name[0].islower():
                    self._tree.setRowHidden(i, QtCore.QModelIndex(), False)
            # Uppercase
            if radiobox.text() == "A" and radiobox.isChecked() is True:
                if name[0].islower():
                    self._tree.setRowHidden(i, QtCore.QModelIndex(), True)
                else:
                    self._tree.setRowHidden(i, QtCore.QModelIndex(), False)
            # Lowercase
            if radiobox.text() == "a" and radiobox.isChecked() is True:
                if name[0].isupper():
                    self._tree.setRowHidden(i, QtCore.QModelIndex(), True)
                else:
                    self._tree.setRowHidden(i, QtCore.QModelIndex(), False)
            
            # Checked
            if radiobox.text() == "Checked" and radiobox.isChecked() is True:
                if self._line.text() in checked_dict:
                    if name in checked_dict[self._line.text()]:
                        self._tree.setRowHidden(i, QtCore.QModelIndex(), False)
                    else:
                        self._tree.setRowHidden(i, QtCore.QModelIndex(), True)
                else:
                    pass

    def onEnumeratePress(self):
        """ Create enumeration """
        line = self._line.text()
        new_line = "list(" + line + ")"
        self._tree._proxy.setName(new_line)

    def onElementNamesPress(self):
        """ Fill element names in combo box """
        element = self._element_names.currentText()
        if element == '--Name--':
            pass
        else:
            old_line = self._line.text()
            new_line = str(old_line + '.getByName("' + element + '")')
            self._line.setText(new_line)
            self._tree._proxy.setName(new_line)
    
    def onElementIndexPress(self):
        """ Fill element index in combo box """
        element = self._element_index.currentText()
        if element == '--Index--':
            pass
        else:
            old_line = self._line.text()
            new_line = str(old_line + '.getByIndex(' + element + ')')
            self._line.setText(new_line)
            self._tree._proxy.setName(new_line)
            
    def onBackToHistory(self):
        """ Back to history """
        new_line = self._history.currentText()
        self._line.setText(new_line)
        self._tree._proxy.setName(new_line)
        
    def onAddToHistory(self, data):
        """ Record history """
        old_list = [self._history.itemText(i) for i in range(self._history.count())]
        # add new to list
        if not data in old_list:
            old_list.append(data)
        # sort
        new_list = sorted(old_list)
        self._history.clear()
        # show
        self._history.addItems(new_list)

    def onForwardPress(self):
        all_items = self._desc_all_items.text()

        row = self._description.currentRow()
        counter = row + 1
        self._description.setCurrentRow(counter)

        if counter == int(all_items):
            self._desc_counter.setText("0")
        else:
            self._desc_counter.setText(str(counter + 1))

    def onBackPress(self):
        all_items = self._desc_all_items.text()

        row = self._description.currentRow()
        counter = row - 1
        self._description.setCurrentRow(counter)

        if self._description.currentRow() < 0:
            self._desc_counter.setText("0")
        else:
            self._desc_counter.setText(str(counter + 1))

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
    
    def onSaveOptionsInConf(self):
        """ Save options in configuration file. """
        
        config.set('GENERAL', 'dash', str(self._dash.isChecked()))
  
        with open(conf_file, 'w') as configfile:
            config.write(configfile)

