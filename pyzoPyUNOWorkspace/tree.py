import configparser
from inspect import getsourcefile
from json import load
import os
import re
import sqlite3
import webbrowser

import pyzo
from pyzo.util.qt import QtCore, QtGui, QtWidgets
from .utils import splitName, splitNameCleaner, joinName

# Constants
WORKSPACE_INIT = os.path.abspath(getsourcefile(lambda: 0))
WORKSPACE_DIR = os.path.dirname(WORKSPACE_INIT)
CONF_FILE = os.path.join(WORKSPACE_DIR, 'config.ini')
UNODOC_DB = os.path.join(WORKSPACE_DIR, 'unoDoc.db')

# Read configuration
config = configparser.ConfigParser()
config.read(CONF_FILE)

FORUM_PATH = config.get('GENERAL', 'forum_path')
FORUM_SUFIX = config.get('GENERAL', 'forum_sufix')
SNIPPET_PATH = config.get('GENERAL', 'snippet_path')
SNIPPET_SUFIX = config.get('GENERAL', 'snippet_sufix')

# connect documentation database
conn = sqlite3.connect(UNODOC_DB)

# JSON serialization paths
RESULTFILE = 'result.txt'
RESULT = os.path.join(WORKSPACE_DIR, RESULTFILE)

# Checked items
checked_dict = {}


def formatReference(signature, description, fnd=None, getfnd=None):
    #
    signature = signature.replace('&newline&', '\n')

    if getfnd:
        signature = re.sub(r'\b' + getfnd + r'\b', "<strong>{}</strong>".format(getfnd), signature)
        signature = re.sub(r'\b' + getfnd + '()' + r'\b', "<strong>{}</strong>".format(getfnd), signature)

    if fnd:
        signature = re.sub(r'\b' + fnd + r'\b', "<strong>{}</strong>".format(fnd), signature)

    signature = signature.replace('set raises',
                                  '<span style="font-weight:bold;color:red">{}</span>'.format('set raises'))
    signature = signature.replace('get raises',
                                  '<span style="font-weight:bold;color:red">{}</span>'.format('get raises'))
    signature = signature.replace('raises', '<span style="font-weight:bold;color:red">{}</span>'.format('raises'))
    #
    description = description.replace('&newline&&newline&', '<p></p>')
    description = description.replace('&newline&', '<p></p>')
    description = re.sub(r'\b{}\b'.format('Parameters'), "<p style='font-weight:bold'>{}</p>".format('Parameters'),
                         description)
    description = re.sub(r'\b{}\b'.format('Exceptions'), "<p style='font-weight:bold'>{}</p>".format('Exceptions'),
                         description)
    description = re.sub(r'\b{}\b'.format('See also'), "<p style='font-weight:bold'>{}</p>".format('See also'),
                         description)
    description = re.sub(r'\b{}\b'.format('Returns'), "<p style='font-weight:bold'>{}</p>".format('Returns'),
                         description)
    #
    description = description.replace('Attention',
                                      '<span style="font-weight:bold;color:red">{}</span>'.format('Attention'))
    description = description.replace('Deprecated',
                                      '<span style="font-weight:bold;color:red">{}</span>'.format('Deprecated'))

    return signature, description


class PyUNOWorkspaceItem(QtWidgets.QTreeWidgetItem):
    def __lt__(self, otherItem):
        column = self.treeWidget().sortColumn()
        try:
            return float(self.text(column).strip('[]')) > float(otherItem.text(column).strip('[]'))
        except ValueError:
            return self.text(column) > otherItem.text(column)


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
        with open(RESULT) as resultf:
            self._uno_dict = load(resultf)
        self.haveNewData.emit()


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

        # # JSON serialization file
        if not os.path.isfile(RESULT):
            with open(RESULT, 'w') as fl:
                fl.write('{}')

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
        self.clicked.connect(self.onItemClicked)

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
            url = FORUM_PATH + search + FORUM_SUFIX
            webbrowser.open(url)

        elif 'Search in snippets' in req:
            # Search in forum snippets
            url = SNIPPET_PATH + search + SNIPPET_SUFIX
            webbrowser.open(url)

        elif 'Check' in req:
            # Check item
            if ob in checked_dict:
                if search not in checked_dict[ob]:
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

        # ------- End PyUNO ----------------

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
        self.parent()._impl_name.setText("")

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
                self.parent()._impl_name.setText(impl_name)

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
        # self._proxy._uno_dic = {}

    def onItemClicked(self):
        """ onItemClicked()
        If item clicked in the workspace tree show help
        """

        self.parent()._description.clear()

        index = self.currentIndex()
        find = index.model().data(index)
        if find.startswith('get'):
            getfind = find.replace('get', '')
        else:
            getfind = 'get' + find

        cur = conn.cursor()
        cur.execute("SELECT signature, description FROM UNOtable WHERE name=? OR name =?", (find, getfind))
        rows = cur.fetchall()
        self.parent()._desc_all_items.setText(str(len(rows)))
        self.parent()._desc_counter.setText("0")

        try:
            n = 0
            txt = ""
            ok_counter = 0
            for sig, desc in rows:
                print('***************')
                sig, desc = formatReference(sig, desc,find, getfind)
                print('-------------------')
                # parameters
                try:
                    find_param = len(self._proxy._uno_dict[find]['param'])
                except:
                    find_param = None
                
                try:
                    get_param = len(self._proxy._uno_dict[getfind]['param'])
                except:
                    get_param = None
                
                # signature color    
                if len(rows) == 1:
                    # ok
                    sig = "<p style = 'background-color: palegreen'>{}</p>".format(sig)
                    ok_counter += 1
                
                elif find_param:
                    t = 0
                    for i in self._proxy._uno_dict[find]['param']:
                        print(i)
                        if i in sig:
                            t = t + 1
                    print(str(t))
                    if t == find_param:
                        sig = "<p style = 'background-color: palegreen'>{}</p>".format(sig)
                        ok_counter += 1
                    else:
                        sig = "<p style = 'background-color: lightgray'>{}</p>".format(sig)
                        
                elif  get_param:
                    t = 0
                    for i in self._proxy._uno_dict[getfind]['param']:
                        print(i)
                        if i in sig:
                            t = t + 1
                    print(str(t))
                    if t == get_param:
                        sig = "<p style = 'background-color: palegreen'>{}</p>".format(sig)
                        ok_counter += 1
                    else:
                        sig = "<p style = 'background-color: lightgray'>{}</p>".format(sig)
                      
                else:
                    sig = "<p style = 'background-color: lightgray'>{}</p>".format(sig)
                
                res = sig + desc
                txt = txt + res
                # set font size
                font = self.parent()._description.font()
                font.setPointSize(self._config.fontSize)
                self.parent()._description.setFont(QtGui.QFont(font))
                
                n += 1
            self.parent()._description.setText(txt)
            self.parent()._desc_counter.setText(str(ok_counter))    
        except:
            pass
