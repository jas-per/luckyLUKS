"""
This module contains 3 different graphical modal dialogs to ask a user for password/-phrase.
Each is based on a common password dialog and offers a method to use the dialog
in a synchronous way ie to run itself and return a result or perform an action,
or throw an exception if this fails

luckyLUKS Copyright (c) 2014,2015 Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""
from __future__ import unicode_literals

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QMessageBox, QDialogButtonBox, \
    QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox
from PyQt5.QtGui import QIcon


class UserInputError(Exception):

    """ Raised if user cancels a password dialog """
    pass


class PasswordDialog(QDialog):

    """ Basic dialog with a textbox input field for the password/-phrase and OK/Cancel buttons """

    def __init__(self, parent, message, title='Enter Password'):
        """
            :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
            :param message: The message that gets displayed above the textbox
            :type message: str
            :param title: Displayed in the dialogs titlebar
            :type title: str or None
        """
        super(PasswordDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.layout = QVBoxLayout()
        self.layout.setSpacing(10)

        # create icon and label
        self.header_box = QHBoxLayout()
        self.header_box.setSpacing(10)
        self.header_box.setAlignment(Qt.AlignLeft)
        self.header_text = QLabel(message)
        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme('dialog-password').pixmap(32))
        self.header_box.addWidget(icon)
        self.header_box.addWidget(self.header_text)
        self.layout.addLayout(self.header_box)

        # create the text input field
        self.pw_box = QLineEdit()
        self.pw_box.setMinimumSize(0, 25)
        # password will not be shown on screen
        self.pw_box.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.pw_box)
        self.layout.addSpacing(10)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.buttons.accepted.connect(self.on_accepted)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        self.setLayout(self.layout)
        self.pw_box.setFocus()

    def on_accepted(self):
        """ Event handler for accept signal: block when input field empty """
        if self.pw_box.text() != '':
            self.accept()
        else:
            self.pw_box.setFocus()

    def get_password(self):
        """ Dialog runs itself and returns the password/-phrase entered
            or throws an exception if the user cancelled/closed the dialog
            :returns: The entered password/-phrase
            :rtype: str
            :raises: UserInputError
        """
        try:
            if self.exec_():
                return self.pw_box.text()
            else:
                raise UserInputError()
        finally:
            self.destroy()


class SudoDialog(PasswordDialog):

    """ Modified PasswordDialog that adds a checkbox asking for permanent sudo access permission"""

    def __init__(self, parent, message, toggle_function):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
            :param message: The message that gets displayed above the textbox
            :type message: str
            :param toggle_function: A function that accepts a boolean value, used to propagate the current state of the checkbox
            :type toggle_function: function(boolean)
        """
        super(SudoDialog, self).__init__(parent,
                                         message=message,
                                         title=_('luckyLUKS'))

        # add checkbox to dialog
        self.toggle_function = toggle_function
        self.store_cb = QCheckBox('')  # QCheckBox supports only string labels ..
        cb_label = QLabel(_('Always allow luckyLUKS to be run\nwith administrative privileges'))  # .. QLabel because markup is needed for linebreak
        # connect clicked on QLabel to fully emulate QCheckbox behaviour
        cb_label.mouseReleaseEvent = self.toggle_cb
        self.store_cb.stateChanged.connect(self.on_cb_toggled)
        self.toggle_function(False)  # allowing permanent access has to be confirmed explicitly

        self.sudo_box = QHBoxLayout()
        self.sudo_box.setSpacing(5)
        self.sudo_box.addWidget(self.store_cb)
        self.sudo_box.addWidget(cb_label)
        self.sudo_box.addStretch()
        self.layout.insertLayout(2, self.sudo_box)

    def toggle_cb(self, event):
        """ Slot for QCheckbox behaviour emulation: toggles checkbox """
        self.store_cb.setChecked(not self.store_cb.isChecked())

    def on_cb_toggled(self, state):
        """ Event handler for checkbox toggle: propagate new value to parent """
        self.toggle_function(self.store_cb.isChecked())


class FormatContainerDialog(PasswordDialog):

    """ Modified PasswordDialog that shows the input on screen and requests confirmation for close/cancel """

    def __init__(self, parent):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
        """
        super(FormatContainerDialog, self).__init__(parent,
                                                    message=_('Please choose a passphrase\nto encrypt the new container:\nAttention, the passphrase\nwill be SHOWN on screen'),
                                                    title=_('Enter new Passphrase'))
        # show input on screen
        self.pw_box.setEchoMode(QLineEdit.Normal)

    def closeEvent(self, event):
        """ Event handler confirm close """
        if not self.confirm_close_cancel():
            event.ignore()

    def reject(self):
        """ Event handler confirm cancel """
        if self.confirm_close_cancel():
            super(FormatContainerDialog, self).reject()
        else:
            self.pw_box.setFocus()

    def confirm_close_cancel(self):
        """ Display dialog for close/cancel confirmation
            :returns: The users decision
            :rtype: bool
        """
        message = _('Currently creating new container!\nDo you really want to quit?')
        mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Cancel, self)
        mb.addButton( _('Quit'), QMessageBox.AcceptRole)
        mb.setDefaultButton(QMessageBox.Cancel)
        return mb.exec_() == QMessageBox.AcceptRole


class UnlockContainerDialog(PasswordDialog):

    """ Modified PasswordDialog that communicates with the worker process to unlock an encrypted container """

    def __init__(self, parent, worker, luks_device_name, encrypted_container, mount_point=None):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
            :param worker: Communication handler with the worker process
            :type worker: :class:`helper.WorkerMonitor`
            :param luks_device_name: The device mapper name
            :type luks_device_name: str/unicode
            :param encrypted_container: The path of the container file
            :type encrypted_container: str/unicode
            :param mount_point: The path of an optional mount point
            :type mount_point: str/unicode or None
        """
        super(UnlockContainerDialog, self).__init__(parent, _('Initializing ..'), luks_device_name)

        self.worker = worker
        self.error_message = ''

        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))
        # disable input until worker initialized
        self.waiting_for_response = True
        self.pw_box.setEnabled(False)
        self.buttons.setEnabled(False)

        # init worker
        self.worker.execute(command={'type': 'request',
                                     'msg': 'unlock',
                                     'device_name': luks_device_name,
                                     'container_path': encrypted_container,
                                     'mount_point': mount_point
                                     },
                            success_callback=self.on_worker_reply,
                            error_callback=self.on_error)

    def on_accepted(self):
        """ Event handler send password/-phrase if worker ready """
        # dont send empty password
        if self.pw_box.text() == '':
            self.pw_box.setFocus()
        elif not self.waiting_for_response:
            # worker is ready, send request
            self.waiting_for_response = True
            self.pw_box.setEnabled(False)
            self.buttons.setEnabled(False)
            self.header_text.setText(_('Checking passphrase ..'))
            self.worker.execute(command={'type': 'response',
                                         'msg': self.pw_box.text()
                                         },
                                success_callback=self.on_worker_reply,
                                error_callback=self.on_error)

    def reject(self):
        """ Event handler cancel:
            Block while waiting for response or notify worker with abort message
        """
        if not self.waiting_for_response:
            self.worker.execute({'type': 'abort', 'msg': ''}, None, None)
            super(UnlockContainerDialog, self).reject()

    def on_error(self, error_message):
        """ Error-Callback: set errormessage and trigger Cancel """
        self.error_message = error_message
        super(UnlockContainerDialog, self).reject()

    def on_worker_reply(self, message):
        """ Success-Callback: trigger OK when unlocked, reset dialog if not """
        if message == 'success':
            self.accept()
        else:
            if self.pw_box.text() == '':  # init
                self.header_text.setText(_('Please enter\ncontainer passphrase:'))
            else:  # at least one previous pw attempt
                self.header_text.setText(_('Wrong passphrase, please retry!\nEnter container passphrase:'))
            self.buttons.setEnabled(True)
            self.pw_box.setText('')
            self.pw_box.setEnabled(True)
            self.pw_box.setFocus()
            self.waiting_for_response = False

    def closeEvent(self, event):
        """ Event handler close: block while waiting for response or notify worker with abort message """
        if self.waiting_for_response:
            event.ignore()
        else:
            self.worker.execute({'type': 'abort', 'msg': ''}, None, None)

    def communicate(self):
        """ Dialog runs itself and throws an exception if the container wasn't unlocked
            :raises: UserInputError
        """
        try:
            if not self.exec_():
                raise UserInputError(self.error_message)  # is empty string in case of cancel/delete -> won't get displayed
        finally:
            self.destroy()
