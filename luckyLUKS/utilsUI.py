"""
UI helper/classes for luckyLUKS

luckyLUKS Copyright (c) 2014,2015 Jasper van Hoorn (muzius@gmail.com)
QExpander Copyright (c) 2012 Canonical Ltd.
modified, originally from https://launchpad.net/ubuntu-sso-client (GPL v3+)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""

try:
    from PyQt5.QtCore import pyqtSignal, Qt
    from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QVBoxLayout,\
        QWidget, QDialogButtonBox, QLabel, QLayout, QStyle, QStyleOption
    from PyQt5.QtGui import QIcon, QPainter
except ImportError:  # py2 or py3 without pyqt5
    from PyQt4.QtCore import pyqtSignal, Qt
    from PyQt4.QtGui import QApplication, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QVBoxLayout,\
        QWidget, QDialogButtonBox, QLabel, QLayout, QIcon, QPainter, QStyle, QStyleOption

from luckyLUKS import PROJECT_URL


class HelpDialog(QDialog):

    """ Displays a help dialog that consists of
        a help icon and a header/title
        a main text
        an iniatially hidden secondary help text that can be expanded
        followed by a footer
    """

    def __init__(self, parent, header_text, basic_text, advanced_text):
        """ Create a new instance
            :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`PyQt4.QtGui.QWidget`
            :param header_text: Displayed in the top of the dialog next to the help icon
            :type header_text: str/unicode
            :param basic_text: Displayed in the middle of the help dialog
            :type basic_text: str/unicode
            :param advanced_text: Displayed below the basic text, initially hidden
            :type advanced_text: str/unicode
        """
        super(HelpDialog, self).__init__(parent, Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.setWindowTitle(_('Help'))
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        layout.setSpacing(10)
        # icon and header
        header = QHBoxLayout()
        header.setSpacing(50)
        header.setAlignment(Qt.AlignLeft)
        icon = QLabel()
        icon.setPixmap(QApplication.style().standardIcon(QStyle.SP_DialogHelpButton).pixmap(48))
        header.addWidget(icon)
        header.addWidget(QLabel(header_text))
        layout.addLayout(header)
        # main help text
        basic_text = QLabel(basic_text)
        layout.addWidget(basic_text)
        # expand advanced help
        expander = QExpander(_('Advanced'), self, False)
        layout.addWidget(expander)
        advanced_text = QLabel(advanced_text)
        layout.addWidget(advanced_text)
        expander.addWidgets([advanced_text])
        # footer
        layout.addStretch()
        footer = QLabel(_('For more information, visit\n'
                          '<a href="{project_url}">{project_url}</a>').format(project_url=PROJECT_URL))
        footer.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(footer)
        # button
        ok_button = QDialogButtonBox(QDialogButtonBox.Ok, parent=self)
        ok_button.accepted.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)


def show_info(parent, message, title=''):
    """ Helper to show info message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`PyQt4.QtGui.QWidget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param title: Displayed in the dialogs titlebar
        :type title: str/unicode
    """
    show_message(parent, message, title, QMessageBox.Information)


def show_alert(parent, message, critical=False):
    """ Helper to show error message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`PyQt4.QtGui.QWidget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param critical: If critical, quit application (default=False)
        :type critical: bool
    """
    show_message(parent, message, _('Error'), QMessageBox.Critical if critical else QMessageBox.Warning)
    if critical:
        QApplication.instance().quit()


def show_message(parent, message, title, message_type):
    """ Generic helper to show message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`PyQt4.QtGui.QWidget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param title: Displayed in the dialogs titlebar
        :type title: str/unicode
        :param message_type: Type of message box to be used
        :type message_type: :class:`QMessageBox.Icon`
    """
    if message != '':
        mb = QMessageBox(message_type, title, message, QMessageBox.Ok, parent)
        mb.exec_()


class QExpander(QWidget):

    """A Qt implementation similar to GtkExpander."""

    def __init__(self, label, parent, expanded=False):
        """Create a new instance."""
        super(QExpander, self).__init__(parent)
        self.parent = parent
        self.label = QExpanderLabel(label, self)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)
        self._widgets = []
        self.label.clicked.connect(self._on_label_clicked)
        self.setExpanded(expanded)

    def _on_label_clicked(self):
        """The expander widget was clicked."""
        self._expanded = not self._expanded
        self.setExpanded(self._expanded)

    def addWidgets(self, widgets):
        """Add widgets to the expander.
        """
        self._widgets += widgets
        self.setExpanded(self._expanded)

    def expanded(self):
        """Return if widget is expanded."""
        return self._expanded

    def setExpanded(self, is_expanded):
        """Expand the widget or not."""
        self._expanded = is_expanded
        if self._expanded:
            self.label.arrow.direction = QArrow.DOWN
        else:
            self.label.arrow.direction = QArrow.RIGHT
        for widget in self._widgets:
            widget.setVisible(self._expanded)
        self.parent.adjustSize()


class QExpanderLabel(QWidget):

    """Widget used to show/modify the label of a QExpander."""

    clicked = pyqtSignal()

    def __init__(self, label, parent):
        """Create a new instance."""
        super(QExpanderLabel, self).__init__(parent)
        self.arrow = QArrow(QArrow.RIGHT)
        self.label = QLabel(label)
        layout = QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.arrow)
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        """Mouse clicked."""
        if self.arrow.direction == QArrow.DOWN:
            self.arrow.direction = QArrow.RIGHT
        else:
            self.arrow.direction = QArrow.DOWN
        self.clicked.emit()


class QArrow(QWidget):

    """Custom widget, arrow image that can be pointed in 4 different directions"""

    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3

    def __init__(self, direction, parent=None):
        """Create a new instance."""
        super(QArrow, self).__init__(parent)
        self._set_direction(direction)
        self.setFixedWidth(10)

    def paintEvent(self, event):
        """Paint the widget."""
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        if self._direction == QArrow.UP:
            primitive = QStyle.PE_IndicatorArrowUp
        elif self._direction == QArrow.DOWN:
            primitive = QStyle.PE_IndicatorArrowDown
        elif self._direction == QArrow.LEFT:
            primitive = QStyle.PE_IndicatorArrowLeft
        else:
            primitive = QStyle.PE_IndicatorArrowRight
        painter.setViewTransformEnabled(True)
        self.style().drawPrimitive(primitive, opt, painter, self)

    def _get_direction(self):
        """Return the direction used."""
        return self._direction

    def _set_direction(self, direction):
        """Set the direction."""
        if direction not in (QArrow.UP, QArrow.DOWN,
                             QArrow.LEFT, QArrow.RIGHT):
            raise ValueError('Wrong arrow direction.')
        self._direction = direction
        self.repaint()

    direction = property(_get_direction, _set_direction)
