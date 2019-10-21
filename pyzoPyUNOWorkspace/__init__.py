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
import os, sys
import pyzo
from pyzo.util.qt import QtCore, QtGui, QtWidgets
from .tree import (
    PyUNOWorkspaceTree,
    PyUNOWorkspaceProxy,
    writeHistory,
    readHistory,
    getHistoryFilePath,
    createResultFile,
    createHistoryFile,
)

tool_name = pyzo.translate("pyzoPyUNOWorkspace", "PyUNO Workspace")
tool_summary = (
    "Lists Python and PyUNO variables in the current shell's namespace."
)


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
        if not hasattr(self._config, "hideTypes"):
            self._config.hideTypes = []
        #
        if not hasattr(self._config, "fontSizeTree"):
            if sys.platform == "darwin":
                self._config.fontSizeTree = 12
            else:
                self._config.fontSizeTree = 10
        if not hasattr(self._config, "fontSizeHelp"):
            if sys.platform == "darwin":
                self._config.fontSizeHelp = 12
            else:
                self._config.fontSizeHelp = 10
        #
        if not hasattr(self._config, "historyMaximum"):
            self._config.historyMaximum = 10
        # if not hasattr(self._config, "historyFreeze"):
        #     self._config.historyFreeze = 0
        if not hasattr(self._config, "historyClearOnStartup"):
            self._config.historyClearOnStartup = 1

        style = QtWidgets.qApp.style()
        #
        self.initText = "<p>{}</p>".format(
            "Click an item in the list for Help information."
        )

        # Create empty label
        self._empty = QtWidgets.QLabel(self)
        self._empty.setText("")

        # ----- Layout 1 -----

        # Create Home tool button
        self._home = QtWidgets.QToolButton(self)
        self._home.setIcon(style.standardIcon(style.SP_ArrowUp))
        self._home.setIconSize(QtCore.QSize(16, 16))
        self._home.setToolTip("Home - return to the beginninig.")

        # Create Refresh tool button
        self._refresh = QtWidgets.QToolButton(self)
        self._refresh.setIcon(style.standardIcon(style.SP_BrowserReload))
        self._refresh.setIconSize(QtCore.QSize(16, 16))
        self._refresh.setToolTip("Reload the current command.")

        # Create Go back tool button
        self.back = QtWidgets.QToolButton(self)
        self.back.setIcon(style.standardIcon(style.SP_ArrowLeft))
        self.back.setIconSize(QtCore.QSize(16, 16))
        self.back.setToolTip("Go back to the previous command.")

        # Create "path" line edit
        self._line = QtWidgets.QLineEdit(self)
        self._line.setReadOnly(True)
        self._line.setStyleSheet("QLineEdit { background:#ddd; }")
        self._line.setFocusPolicy(QtCore.Qt.NoFocus)

        # Create selection tool button
        self._selection = QtWidgets.QToolButton(self)
        self._selection.setIcon(pyzo.icons.layout)
        self._selection.setIconSize(QtCore.QSize(16, 16))
        self._selection.setToolTip("Get selected  objects in the document.")
        self._selection.setEnabled(False)

        # Create "insert_code" button
        self._insert_code = QtWidgets.QToolButton(self)
        self._insert_code.setIcon(
            style.standardIcon(style.SP_FileDialogDetailedView)
        )
        self._insert_code.setToolTip(
            "Insert code in the script at the cursor position"
        )

        # ----- Layout 2 -----

        # Create element_index combo box
        self._element_index = QtWidgets.QComboBox(self)
        self._element_index.setToolTip("Set the argument for getByIndex method.")
        self._element_index.setEnabled(False)

        # Create element_names combo box
        self._element_names = QtWidgets.QComboBox(self)
        self._element_names.setToolTip("Get by name")
        self._element_names.setEnabled(False)

        # Create enumerate combo box
        self._enumerate_index = QtWidgets.QComboBox(self)
        self._enumerate_index.setToolTip("Objects enumerated by createEnumeration method")
        self._enumerate_index.setEnabled(False)

        # Create history combo box
        self._history = QtWidgets.QComboBox(self)
        self._history.setToolTip("Show the command history")
        self._history.setEnabled(True)

        # Create options menu
        self._options = QtWidgets.QToolButton(self)
        self._options.setToolTip("Tool configuration.")
        self._options.setIcon(pyzo.icons.filter)
        self._options.setIconSize(QtCore.QSize(16, 16))
        self._options.setPopupMode(self._options.InstantPopup)
        self._options.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        # main menu
        self._options._menu = pyzo.core.menu.Menu(self, "Main menu")  # QtWidgets.QMenu()
        # submenus
        self._show_hide_menu = pyzo.core.menu.Menu(None, "Show/Hide")
        #
        self._font_size_menu = pyzo.core.menu.Menu(None, "Font size")
        self._font_size_tree_menu = pyzo.core.menu.Menu(None, "Workspace")
        self._font_size_help_menu = pyzo.core.menu.Menu(None, "Help")
        #
        self._history_menu = pyzo.core.menu.Menu(None, "History")

        # create menu
        self._options.setMenu(self._options._menu)
        self.onOptionsPress()

        # Show/hide Help button
        self._btn_toggle = QtWidgets.QToolButton(self)
        self._btn_toggle.setToolTip("Show/hide help")
        self._btn_toggle.setIcon(style.standardIcon(style.SP_DialogHelpButton))
        self._btn_toggle.setIconSize(QtCore.QSize(16, 16))
        self._btn_toggle.setCheckable(True)
        self._btn_toggle.setChecked(False)

        # ----- Layout 3 -----

        # Create tree
        self._tree = PyUNOWorkspaceTree(self)

        # Create message for when tree is empty
        self._initText = QtWidgets.QLabel(
            pyzo.translate(
                "pyzoWorkspace",
                """Lists the variables in the current shell's namespace.
        Currently, there are none. Some of them may be hidden because of the filters you configured.""",
            ),
            self,
        )

        self._initText.setVisible(False)
        self._initText.setWordWrap(True)

        # ----- Layout 4 -----
        # Create description widget

        self._description = QtWidgets.QTextBrowser(self)
        self._description.setText(self.initText)

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
        self._search_line.setToolTip("Search")
        self._search_line.setPlaceholderText("UNO API Search...")
        #
        self._match = QtWidgets.QCheckBox(self)
        self._match.setText("Match")
        self._match.setChecked(True)
        self._match.setToolTip("Match")
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

        # ------ Set layouts

        # Layout 1: Object and insert code layout
        layout_1 = QtWidgets.QHBoxLayout()
        layout_1.addWidget(self._home, 0)
        layout_1.addWidget(self._refresh, 0)
        layout_1.addWidget(self.back, 0)
        layout_1.addWidget(self._line, 1)
        layout_1.addWidget(self._selection, 0)
        layout_1.addWidget(self._insert_code, 0)

        # Layout 2: Display, arguments, history and option layout
        layout_2 = QtWidgets.QHBoxLayout()
        layout_2.addWidget(self._element_index, 0)
        layout_2.addWidget(self._element_names, 0)
        layout_2.addWidget(self._enumerate_index, 0)
        layout_2.addWidget(self._history, 1)
        layout_2.addWidget(self._options, 0)
        layout_2.addWidget(self._btn_toggle, 0)

        # Layout 3: Tree layout
        layout_3 = QtWidgets.QVBoxLayout()
        layout_3.addWidget(self._tree, 0)

        # Layout 5: Hidden help layout
        self._description_widget = QtWidgets.QWidget(self)
        self._description_widget.setVisible(False)

        layout_5 = QtWidgets.QVBoxLayout()
        layout_5.setSpacing(0)
        layout_5.setContentsMargins(0, 0, 0, 0)

        # Layout 6: Search layout
        layout_6 = QtWidgets.QHBoxLayout()
        layout_6.addWidget(self._desc_counter, 0)
        layout_6.addWidget(self._desc_of, 0)
        layout_6.addWidget(self._desc_all_items, 0)
        layout_6.addWidget(self._empty, 0)
        layout_6.addWidget(self._search_line, 0)
        layout_6.addWidget(self._empty, 0)
        layout_6.addWidget(self._match, 0)
        layout_6.addWidget(self._search, 0)
        layout_6.addWidget(self._clear, 0)

        # Layout 7: Help description layout
        layout_7 = QtWidgets.QVBoxLayout()
        layout_7.addWidget(self._description, 0)
        layout_5.addLayout(layout_7, 0)
        layout_5.addLayout(layout_6, 0)
        layout_7.setSpacing(0)
        layout_7.setContentsMargins(0, 0, 0, 0)

        # Main Layout
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.addLayout(layout_1, 0)
        mainLayout.addLayout(layout_2, 0)
        mainLayout.addLayout(layout_3, 0)
        # add hidden widget
        mainLayout.addWidget(self._description_widget)
        self._description_widget.setLayout(layout_5)

        # set margins
        mainLayout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(mainLayout)

        # ------ Bind events
        self._home.pressed.connect(self.onHomePress)
        self._refresh.pressed.connect(self.onRefreshPress)
        self.back.pressed.connect(self.onBackPress)
        #
        self._selection.pressed.connect(self.onCurrentSelectionPress)
        self._insert_code.pressed.connect(self.onInsertCodeInEditorPress)
        #
        self._element_names.activated[str].connect(self.onElementNamesPress)
        self._element_index.activated[str].connect(self.onElementIndexPress)
        self._enumerate_index.activated[str].connect(self.onEnumerateIndexPress)
        self._history.activated[str].connect(self.onHistoryPress)
        #
        self._options.pressed.connect(self.onOptionsPress)
        #
        self._show_hide_menu.triggered.connect(self.onShowHideMenuTiggered)
        self._font_size_help_menu.triggered.connect(
            self.onFontHelpOptionMenuTiggered
        )
        self._font_size_tree_menu.triggered.connect(
            self.onFontTreeOptionMenuTiggered
        )
        self._history_menu.triggered.connect(self.onHistoryOptionMenuTiggered)
        #
        self._btn_toggle.toggled.connect(self.onHelpTogglePress)
        #
        self._search.pressed.connect(self.onSearchPress)
        self._clear.pressed.connect(self.onClearHelpPress)

        # Create json result file
        createResultFile(),

        # Load History
        if self._config.historyClearOnStartup:
            #self._config.historyFreeze = 0
            createHistoryFile()
        self.loadHistory()

    # ----------------------------
    #           EVENTS
    # ----------------------------

    @staticmethod
    def createCodeSnippet(data):
        """ Create code snippet
         Split string by '.'
        """
        data = data.split(".")
        target = "initial_target"
        code = ""

        for index in range(0, len(data)):
            try:
                if index == 0:
                    code = (
                        target
                        + " = "
                        + data[index]
                        + "."
                        + data[index + 1]
                        + "\n    "
                    )
                else:
                    first_item = target
                    try:
                        if data[index + 1].startswith("getByIndex") or data[
                            index + 1
                        ].startswith("getByName"):
                            target = "item"
                        else:
                            words = re.findall("[A-Z][^A-Z]*", data[index + 1])
                            second = words[len(words) - 1].lower()
                            second = second.split("(")
                            target = second[0]
                        code = (
                            code
                            + target
                            + " = "
                            + first_item
                            + "."
                            + data[index + 1]
                            + "\n    "
                        )
                    except:
                        pass
            except:
                pass
        new_code = code
        return new_code

    # Layout 1
    def onHomePress(self):
        """ Back to start """

        self.onClearHelpPress()
        self._tree._proxy.setName("")

    def onRefreshPress(self):
        """ Refresh """
        self.onClearHelpPress()
        line = self._line.text()
        self._tree._proxy.setName(line)

    def onBackPress(self):
        """ Go back """
        self.onClearHelpPress()
        line = self._line.text()
        if line:
            self._tree._proxy.goUp()
        else:
            self._tree._proxy.setName("")

    def onCurrentSelectionPress(self):
        """ Get selected object """
        line = self._line.text()
        new_line = line + ".getCurrentSelection()"
        self._tree._proxy.setName(new_line)

    def onInsertCodeInEditorPress(self):
        """ Insert code snippet in the editor. """
        line = str(self._line.text())
        # data = line.split(".")
        code = self.createCodeSnippet(line)
        # code = self.getCodeSnippet()
        editor = pyzo.editors.getCurrentEditor()
        editor.insertPlainText(code)

    # Layout 2
    def onElementIndexPress(self):
        """ Fill element index in combo box """
        element = self._element_index.currentText()
        if not element == "--Index--":
            old_line = self._line.text()
            new_line = str(old_line + ".getByIndex(" + element + ")")
            self._line.setText(new_line)
            self._tree._proxy.setName(new_line)

    def onElementNamesPress(self):
        """ Fill element names in combo box """
        element = self._element_names.currentText()
        if not element == "--Name--":
            old_line = self._line.text()
            new_line = str(old_line + '.getByName("' + element + '")')
            self._line.setText(new_line)
            self._tree._proxy.setName(new_line)

    def onEnumerateIndexPress(self):
        """ Create enumeration """
        element = self._enumerate_index.currentText()
        line = self._line.text()
        if element == "All":
            new_line = "list(" + line + ")"
            self._tree._proxy.setName(new_line)
        else:
            new_line = "list(" + str(line + ")[" + element + "]")
            self._line.setText(new_line)
            self._tree._proxy.setName(new_line)

    def onHistoryPress(self):
        """ Back to history """
        new_line = self._history.currentText()
        self._line.setText(new_line)
        self._tree._proxy.setName(new_line)

    def onHelpTogglePress(self):
        """ Open or close new project widget. """

        if self._btn_toggle.isChecked():
            self._description_widget.setVisible(True)
        else:
            self._description_widget.setVisible(False)
            if self._description.toPlainText() == "":
                self._description.setText(self.initText)

    # Layout 5

    def onSearchPress(self):
        """ Search UNO API """
        from .tree import conn, formatReference

        self._description.clear()
        self._desc_counter.setText("0")
        self._desc_all_items.setText("0")

        search = self._search_line.text()
        if search:
            cur = conn.cursor()

            if self._match.isChecked():
                cur.execute(
                    "SELECT signature, description, reference FROM UNOtable WHERE  name=?",
                    [search],
                )
            else:
                cur.execute(
                    "SELECT signature, description, reference FROM UNOtable WHERE  name like ?",
                    ("%" + search + "%",),
                )
            rows = cur.fetchall()
            res = ""
            n = 0
            self._desc_all_items.setText(str(n))
            for sig, desc, ref in rows:
                desc = desc + "&newline&Reference &newline&" + ref
                sig, desc = formatReference(sig, desc, bold=[search])
                sig = "<p style = 'background-color: lightgray'>{}</p>".format(
                    sig
                )
                res = res + sig + desc
                n += 1

            self._description.setText(res)
            self._desc_all_items.setText(str(n))

    def onClearHelpPress(self):
        """ Remove results """
        self._description.setText(self.initText)
        self._search_line.setText("")
        self._desc_counter.setText("0")
        self._desc_all_items.setText("0")

    def onAddToHistory(self, data):
        """ Record history """

        if data:
            #if not self._config.historyFreeze:
            # add new to list
            hist_list = readHistory()
            if data not in hist_list:
                if len(hist_list) > self._config.historyMaximum:
                    hist_list.pop(1)

                hist_list.append(data)
                writeHistory(hist_list)
            # sort
            new_list = sorted(hist_list)
            self._history.clear()
            # show
            self._history.addItems(new_list)

    def displayEmptyWorkspace(self, empty):
        self._tree.setVisible(not empty)
        self._initText.setVisible(empty)

    def onOptionsPress(self):
        """ Create the menu for the button, Do each time to make sure
        the checks are right. """

        # Clear submenus
        self._show_hide_menu.clear()
        self._font_size_menu.clear()
        self._font_size_tree_menu.clear()
        self._font_size_help_menu.clear()
        self._history_menu.clear()

        # Get menu
        menu = self._options._menu
        menu.clear()

        # Always clear the shell screen
        menu.addCheckItem(
            pyzo.translate(
                "pyzoWorkspace",
                "Clear shell ::: Always clear the shell screen after new command.",
            ),
            icon=None,
            callback=self.onClearShell,
            value=None,
            selected=self._config.clearScreenAfter,
        )

        menu.addSeparator()

        # Font size menu
        # tree menu
        currentSize = self._config.fontSizeTree
        for i in range(8, 15):
            action = self._font_size_tree_menu.addAction("font-size: %ipx" % i)
            action.setCheckable(True)
            action.setChecked(i == currentSize)

        self._font_size_menu.addMenu(self._font_size_tree_menu)

        # help menu
        currentSize = self._config.fontSizeHelp
        for i in range(8, 15):
            action = self._font_size_help_menu.addAction("font-size: %ipx" % i)
            action.setCheckable(True)
            action.setChecked(i == currentSize)

        self._font_size_menu.addMenu(self._font_size_help_menu)

        menu.addMenu(self._font_size_menu)

        # History menu
        history_option = [
            (
                "clear",
                pyzo.translate("pyzoWorkspace", "Clear ::: Clear history."),
            ),
            # (
            #     "edit",
            #     pyzo.translate(
            #         "pyzoWorkspace", "Edit ::: First line must be empty!"
            #     ),
            # ),
            (
                "reload",
                pyzo.translate("pyzoWorkspace", "Reload ::: Reload history."),
            ),
        ]

        for type, display in history_option:
            self._history_menu.addItem(
                display,
                icon=None,
                callback=self.onHistoryOptionMenuTiggered,
                value=type,
            )

        self._history_menu.addSeparator()

        # self._history_menu.addCheckItem(
        #     pyzo.translate(
        #         "pyzoWorkspace", "Freeze ::: Turn history in favorites."
        #     ),
        #     icon=None,
        #     callback=self._setHistoryFreeze,
        #     value=None,
        #     selected=self._config.historyFreeze,
        # )
        self._history_menu.addCheckItem(
            pyzo.translate(
                "pyzoWorkspace",
                "Clear on startup ::: Clear history on startup.",
            ),
            icon=None,
            callback=self._setClearHistoryOnStartup,
            value=None,
            selected=self._config.historyClearOnStartup,
        )

        menu.addMenu(self._history_menu)

        # Show/Hide menu
        hideables = [
            ("type", pyzo.translate("pyzoWorkspace", "Hide types")),
            ("function", pyzo.translate("pyzoWorkspace", "Hide functions")),
            ("module", pyzo.translate("pyzoWorkspace", "Hide modules")),
            (
                "private",
                pyzo.translate("pyzoWorkspace", "Hide private identifiers"),
            ),
            (
                "startup",
                pyzo.translate(
                    "pyzoWorkspace", "Hide the shell's startup variables"
                ),
            ),
        ]

        for type, display in hideables:
            checked = type in self._config.hideTypes
            action = self._show_hide_menu.addAction(display)
            action._what = type
            action.setCheckable(True)
            action.setChecked(checked)

        menu.addMenu(self._show_hide_menu)

    def onShowHideMenuTiggered(self, action):
        """  The user decides what to hide in the workspace. """

        # What to show
        type = action._what.lower()

        # Swap
        if type in self._config.hideTypes:
            while type in self._config.hideTypes:
                self._config.hideTypes.remove(type)
        else:
            self._config.hideTypes.append(type)

        # Update
        self._tree.fillWorkspace()

    def onClearShell(self, value):

        self._config.clearScreenAfter = value


    def onFontHelpOptionMenuTiggered(self, action):
        """  The user decides about font size in the Help. """
        # Get text
        text = action.text().lower()

        if "size" in text:
            # Get font size
            size = int(text.split(":", 1)[1][:-2])
            # Update
            self._config.fontSizeHelp = size
            # Set font size
            font = self._description.font()
            font.setPointSize(self._config.fontSizeHelp)
            self._description.setFont(QtGui.QFont(font))

    def onFontTreeOptionMenuTiggered(self, action):
        """  The user decides about font size in the Tree. """
        # Get text
        text = action.text().lower()

        if "size" in text:
            # Get font size
            size = int(text.split(":", 1)[1][:-2])
            # Update
            self._config.fontSizeTree = size
            # Set font size
            font = self._tree.font()
            font.setPointSize(self._config.fontSizeTree)
            self._tree.setFont(QtGui.QFont(font))

        self._tree.updateGeometries()

    def onHistoryOptionMenuTiggered(self, action):
        """  The user decides about history content. """

        # clear
        if action == "clear":
            createHistoryFile()
            self.loadHistory()
        # edit
        # elif action == "edit":
        #     fpath = getHistoryFilePath()
        #     pyzo.editors.loadFile(fpath)
        # reload
        elif action == "reload":
            self.loadHistory()

    def loadHistory(self):
        """  Load history. """
        self._history.clear()
        hl = readHistory()
        self._history.addItems(sorted(hl))

    # def _setHistoryFillOption(self, value):
    #
    #     # if value == "freeze":
    #     #     self._config.historyFreeze = value
    #     if value == "clearonstartup":
    #         self._config.historyFreeze = not value

    # def _setHistoryFreeze(self, value):
    #     """  Turn history in the favorites. """
    #
    #     self._config.historyFreeze = value
    #     self._config.historyClearOnStartup = not value

    def _setClearHistoryOnStartup(self, value):
        """  Create history file on startup. """
        self._config.historyClearOnStartup = value
        #self._config.historyFreeze = not value
