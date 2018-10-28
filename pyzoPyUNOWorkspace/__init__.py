# -*- coding: utf-8 -*-
# Copyright (C) 2013, the Pyzo development team
#
# Pyzo is distributed under the terms of the (new) BSD License.
# The full license can be found in 'license.txt'.
#
# PyUNO Workspace is a modified version of Pyzo's Workspace tool,
# designed for Python and PyUNO introspection.
# Author: Sasa Kelecevic, 2017

import re
import sys
import pyzo
from pyzo.util.qt import QtCore, QtGui, QtWidgets
from .tree import PyUNOWorkspaceTree, PyUNOWorkspaceProxy

tool_name = pyzo.translate("pyzoPyUNOWorkspace", "PyUNO Workspace")
tool_summary = "Lists Python and PyUNO variables in the current shell's namespace."


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
        # Set config
        if not hasattr(self._config, 'hideTypes'):
            self._config.hideTypes = []
        if not hasattr(self._config, 'fontSize'):
            if sys.platform == 'darwin':
                self._config.fontSize = 12
            else:
                self._config.fontSize = 10    
        
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
        
        # ----- Layout 4 -----
        
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
        # self._option_label = QtWidgets.QLabel(self)
        # self._option_label.setText(" Options: ")
        # #
        # self._option_save = QtWidgets.QToolButton(self)
        # self._option_save.setText("Save")
        # self._option_save.setToolTip("Save all options")

        # ----- Layout 5 -----

        # Create counter
        self._desc_counter = QtWidgets.QLabel(self)
        self._desc_counter.setText("0")
        # Label
        self._desc_of = QtWidgets.QLabel(self)
        self._desc_of.setText(" of ")
        # Create all items counter
        self._desc_all_items = QtWidgets.QLabel(self)
        self._desc_all_items.setText("0")
        #
        self._search_line = QtWidgets.QLineEdit(self)
        self._search_line.setReadOnly(False)
        self._search_line.setToolTip('Search')
        #
        self._search = QtWidgets.QToolButton(self)
        self._search.setIconSize(QtCore.QSize(16, 16))
        self._search.setText("Search")
        self._search.setToolTip("Search")
        #
        self._clear = QtWidgets.QToolButton(self)
        self._clear.setIconSize(QtCore.QSize(16, 16))
        self._clear.setText("Clear")
        self._clear.setToolTip("Clear")
        
        # Create font options menu
        self._font_options = QtWidgets.QToolButton(self)
        self._font_options.setIcon(pyzo.icons.wrench)
        self._font_options.setIconSize(QtCore.QSize(16,16))
        self._font_options.setPopupMode(self._options.InstantPopup)
        self._font_options.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._font_options._menu = QtWidgets.QMenu()
        self._font_options.setMenu(self._font_options._menu)
        self.onFontOptionsPress()  # create menu now
        
        # ----- Layout 6 -----

        self._description = QtWidgets.QTextBrowser(self)
        initText =  """
        Clik on property or method to show UNO API reference.
        """
        self._description.setText(initText)
        
        # ------ Set layouts
        
        # Layout 1: Object and insert code layout
        layout_1 = QtWidgets.QHBoxLayout()
        layout_1.addWidget(self._home, 0)
        layout_1.addWidget(self._refresh, 0)
        layout_1.addWidget(self._up, 0)
        layout_1.addWidget(self._line, 1)
        layout_1.addWidget(self._enumerate, 0)
        layout_1.addWidget(self._insert_code, 0)
        
        # Layout 2: Display, arguments, history and option layout
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
        # layout_4.addWidget(self._option_label, 0)
        # layout_4.addWidget(self._option_save, 0)

        # Layout 5: Help navigation layout
        layout_5 = QtWidgets.QHBoxLayout()
        layout_5.addWidget(self._desc_counter, 0)
        layout_5.addWidget(self._desc_of, 0)
        layout_5.addWidget(self._desc_all_items, 1)
        layout_5.addWidget(self._search_line, 1)
        layout_5.addWidget(self._search, 0)
        layout_5.addWidget(self._clear, 0)
        layout_5.addWidget(self._font_options, 0)

        # Layout 6: Help description layout
        layout_6 = QtWidgets.QVBoxLayout()
        layout_6.addWidget(self._description, 0)

        # Main Layout
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.addLayout(layout_1, 0)
        mainLayout.addLayout(layout_2, 0)
        mainLayout.addLayout(layout_3, 0)
        mainLayout.addLayout(layout_5, 0)
        mainLayout.addLayout(layout_6, 0)
        mainLayout.addLayout(layout_4, 0)
        mainLayout.setSpacing(2)
        mainLayout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(mainLayout)

        # ------ Bind events
        self._home.pressed.connect(self.onHomePress)
        self._refresh.pressed.connect(self.onRefreshPress)
        self._up.pressed.connect(self._tree._proxy.goUp) # Go back
        self._up.pressed.connect(self.onClearPress)
        self._enumerate.pressed.connect(self.onEnumeratePress)
        self._insert_code.pressed.connect(self.onInsertCodeInEditor)
        #
        self._all.toggled.connect(lambda: self.onRadioChangeState(self._all))
        self._only_p.toggled.connect(lambda: self.onRadioChangeState(self._only_p))
        self._only_m.toggled.connect(lambda: self.onRadioChangeState(self._only_m))
        self._only_star.toggled.connect(lambda: self.onRadioChangeState(self._only_star))
        #
        self._element_names.activated[str].connect(self.onElementNamesPress)
        self._element_index.activated[str].connect(self.onElementIndexPress)
        self._history.activated[str].connect(self.onBackToHistory)
        self._options.pressed.connect(self.onOptionsPress)
        self._options._menu.triggered.connect(self.onOptionMenuTiggered)
        #
        # self._option_save.pressed.connect(self.onSaveOptionsInConf)
        #
        self._search.pressed.connect(self.onSearchPress)
        self._clear.pressed.connect(self.onClearPress)
        
        self._font_options.pressed.connect(self.onFontOptionsPress)
        self._font_options._menu.triggered.connect(self.onFontOptionMenuTiggered)

    # ---------------------------- 
    #           EVENTS
    # ----------------------------
    
    def onClearPress(self):
        """ Remove results """
        self._description.clear()
        self._search_line.setText('')
        self._desc_counter.setText("0")
        self._desc_all_items.setText("0")
    
    def onSearchPress(self):
        """ Search UNO API """
        from .tree import conn, formatReference
        self._description.clear()
        
        search = self._search_line.text()
        if search:
            cur = conn.cursor()
            cur.execute("SELECT signature, description FROM UNOtable WHERE  name like ?", ('%'+search+'%',))
            rows = cur.fetchall()
            for sig, desc in rows:
                sig, desc = formatReference(sig, desc, bold=[search])
                sig = "<p style = 'background-color: lightgray'>{}</p>".format(sig)
                res = sig + desc
    
            self._description.setText(res)

    def onHomePress(self):
        """ Back to start """
        new_line = ''
        self._line.setText(new_line)
        self._tree._proxy.setName(new_line)
        self.onClearPress()
        
    def onRefreshPress(self):
        """ Refresh """
        # item = self._tree.currentItem()
        line = self._line.text()
        self._tree._proxy.setName(line)
        self.onClearPress()
    
    def getCodeSnippet(self):
        """
        """
        line = str(self._line.text())
        data = line.split('.')
        return self.createCodeSnippet(data)
    
    @staticmethod
    def createCodeSnippet(data):
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
        if data not in old_list:
            old_list.append(data)
        # sort
        new_list = sorted(old_list)
        self._history.clear()
        # show
        self._history.addItems(new_list)

    def onOptionsPress(self):
        """ Create the menu for the button, Do each time to make sure
        the checks are right. """

        # Get menu
        menu = self._options._menu
        menu.clear()

        for typ in ['type', 'function', 'module', 'private']:
            checked = typ in self._config.hideTypes
            action = menu.addAction('Hide %s' % typ)
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
        
    def onFontOptionsPress(self):
        """ Create the menu for the button, Do each time to make sure
        the checks are right. """
        
        # Get menu
        menu = self._font_options._menu
        menu.clear()
        
        # Add font size options
        currentSize = self._config.fontSize
        for i in range(8,15):
            action = menu.addAction('font-size: %ipx' % i)
            action.setCheckable(True)
            action.setChecked(i==currentSize)
    
    
    def onFontOptionMenuTiggered(self, action):
        """  The user decides what to show in the structure. """
        # Get text
        text = action.text().lower()
        
        if 'size' in text:
            # Get font size
            size = int( text.split(':',1)[1][:-2] )
            # Update
            self._config.fontSize = size
            # Set font size
            font = self._description.font()
            font.setPointSize(self._config.fontSize)
            self._description.setFont(QtGui.QFont(font))
            
        self._description.updateGeometries()
    
    # def onSaveOptionsInConf(self):
    #     """ Save options in configuration file. """
    #
    #     config.set('GENERAL', 'dash', str(self._dash.isChecked()))
    #
    #     with open(conf_file, 'w') as configfile:
    #         config.write(configfile)

