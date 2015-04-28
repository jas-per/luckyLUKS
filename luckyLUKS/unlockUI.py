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

try:
    import pygtk
    pygtk.require('2.0')
except ImportError:  # py3
    import gi
    gi.require_version('Gtk', '3.0')
    from gi import pygtkcompat
    pygtkcompat.enable()
    pygtkcompat.enable_gtk(version='3.0')

import gtk


class UserInputError(Exception):

    """ Raised if user cancels a password dialog """
    pass


class PasswordDialog(gtk.Dialog):

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
        super(PasswordDialog, self).__init__(title, parent,
                                             gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
             (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
              gtk.STOCK_OK, gtk.RESPONSE_OK)
        )
        self.set_resizable(False)
        self.set_border_width(10)
        # default response will be triggered by pressing enter as well
        self.set_default_response(gtk.RESPONSE_OK)
        # connect buttons
        self.connect('response', self.on_response_check)

        # create icon and label
        self.header_text = gtk.Label()
        self.header_text.set_markup(message)
        self.header_box = gtk.HBox(spacing=10)
        self.header_box.pack_start(gtk.image_new_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION, gtk.ICON_SIZE_DIALOG), False, False, 10)
        self.header_box.pack_start(self.header_text, True, True, 0)
        self.get_content_area().add(self.header_box)

        # create the text input field
        self.pw_box = gtk.Entry()
        # password will not be shown on screen
        self.pw_box.set_visibility(False)
        # allow the user to press enter to do ok
        self.pw_box.set_activates_default(True)
        # add the entry field with top/bottom margins
        align_box = gtk.Alignment(0, 0.5, 1, 0.25)
        align_box.add(self.pw_box)
        align_box.set_size_request(-1, 60)
        self.get_content_area().add(align_box)

        self.pw_box.grab_focus()
        self.show_all()

    def on_response_check(self, dialog, response):
        """ Event handler for response: block when input field empty """
        if response == gtk.RESPONSE_OK and self.pw_box.get_text() == '':
            self.pw_box.grab_focus()
            dialog.emit_stop_by_name('response')

    def get_password(self):
        """ Dialog runs itself and returns the password/-phrase entered
            or throws an exception if the user cancelled/closed the dialog
            :returns: The entered password/-phrase
            :rtype: str
            :raises: UserInputError
        """
        try:
            response = self.run()
            if response == gtk.RESPONSE_OK:
                return self.pw_box.get_text()
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
        self.store_cb = gtk.CheckButton(_('Always allow luckyLUKS to be run\nwith administrative privileges'))
        self.store_cb.connect("toggled", self.on_cb_toggled)
        self.toggle_function(False)  # allowing permanent access has to be confirmed explicitly
        align_box = gtk.Alignment(0, 0, 1, 0.25)
        align_box.add(self.store_cb)
        align_box.set_size_request(-1, 50)
        self.get_content_area().add(align_box)
        self.get_content_area().show_all()

    def on_cb_toggled(self, checkbox):
        """ Event handler for checkbox toggle: propagate new value """
        self.toggle_function(checkbox.get_active())


class FormatContainerDialog(PasswordDialog):

    """ Modified PasswordDialog that shows the input on screen and requests confirmation for close/cancel """

    def __init__(self, parent):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
        """
        super(FormatContainerDialog, self).__init__(parent,
                                                    message=_('Please choose a passphrase\nto encrypt the new container:\n'),
                                                    title=_('Enter new Passphrase'))

        self.connect("delete_event", self.on_close_dialog)
        # display passphrase checkbox and set default to show input
        self.show_cb = gtk.CheckButton(_('Display passphrase'))
        self.show_cb.connect("toggled", self.on_cb_toggled)
        self.show_cb.set_active(True)
        self.get_content_area().add(self.show_cb)
        self.get_content_area().show_all()

    def on_cb_toggled(self, checkbox):
        """ Event handler for checkbox toggle: show/hide passphrase input on screen """
        self.pw_box.set_visibility(checkbox.get_active())

    def on_response_check(self, dialog, response):
        """ Event handler for response: block when input field empty and confirm close/cancel """
        # dont allow empty password
        if response == gtk.RESPONSE_OK and self.pw_box.get_text() == '':
            self.pw_box.grab_focus()
            dialog.emit_stop_by_name('response')
        # confirm cancel
        elif response != gtk.RESPONSE_OK:
            md = gtk.MessageDialog(self,
                                   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_WARNING,
                                   gtk.BUTTONS_CANCEL,
                                   _('Currently creating new container!\nDo you really want to quit?')
                                   )
            md.add_button(gtk.STOCK_QUIT, gtk.RESPONSE_OK)
            response = md.run()
            md.destroy()
            if response != gtk.RESPONSE_OK:
                self.pw_box.grab_focus()
                dialog.emit_stop_by_name('response')

    def on_close_dialog(self, widget, event):
        """ Event handler for delete: pass response handler """
        return True


class UnlockContainerDialog(PasswordDialog):

    """ Modified PasswordDialog that communicates with the worker process to unlock an encrypted container """

    def __init__(self, parent, worker, luks_device_name, encrypted_container, key_file=None, mount_point=None):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
            :param worker: Communication handler with the worker process
            :type worker: :class:`helper.WorkerMonitor`
            :param luks_device_name: The device mapper name
            :type luks_device_name: str/unicode
            :param encrypted_container: The path of the container file
            :type encrypted_container: str/unicode
            :param key_file: The path of an optional key file
            :type key_file: str/unicode or None
            :param mount_point: The path of an optional mount point
            :type mount_point: str/unicode or None
        """
        super(UnlockContainerDialog, self).__init__(parent, _('Initializing ..'), luks_device_name)

        self.worker = worker
        self.error_message = ''
        self.waiting_for_response = True
        # disable input until worker initialized
        self.get_action_area().set_sensitive(False)

        if key_file is not None:
            self.header_text.set_markup(_('<b>Using keyfile</b>\n{keyfile}\nto open container.\n\nPlease wait ..').format(keyfile=key_file))
            self.pw_box.hide()
        else:
            # change label on stock button removes icon -> reset
            self.get_widget_for_response(gtk.RESPONSE_OK).set_label(_('Unlock'))
            self.get_widget_for_response(gtk.RESPONSE_OK).set_image(gtk.image_new_from_stock(gtk.STOCK_OK, gtk.ICON_SIZE_BUTTON))
            self.pw_box.set_sensitive(False)
        self.connect("delete_event", self.on_close_dialog)
        # call worker
        self.worker.execute(command={'type': 'request',
                                     'msg': 'unlock',
                                     'device_name': luks_device_name,
                                     'container_path': encrypted_container,
                                     'mount_point': mount_point,
                                     'key_file': key_file
                                     },
                            success_callback=self.on_worker_reply,
                            error_callback=self.on_error)

    def on_error(self, error_message):
        """ Error-Callback: set errormessage and trigger Cancel """
        self.error_message = error_message
        self.waiting_for_response = False
        self.response(gtk.RESPONSE_CANCEL)

    def on_worker_reply(self, message):
        """ Success-Callback: trigger OK when unlocked, reset dialog if not """
        self.waiting_for_response = False
        if message == 'success':
            self.error_message = 'UNLOCK_SUCCESSFUL'  # (mis-)using errormessage to avoid the need for another state var
            self.response(gtk.RESPONSE_OK)
        else:
            if self.pw_box.get_text() == '':  # init
                self.header_text.set_markup(_('Please enter\ncontainer passphrase:'))
            else:  # at least one previous pw attempt
                self.header_text.set_markup(_('Wrong passphrase, please retry!\nEnter container passphrase:'))
            self.pw_box.set_text('')
            self.pw_box.set_sensitive(True)
            self.get_action_area().set_sensitive(True)
            self.pw_box.grab_focus()

    def on_response_check(self, dialog, response):
        """ Event handler for response:
            send password/-phrase to worker on OK,
            send abort message on close/cancel
            and block while waiting for worker
        """
# worker is waiting: send request on OK, send abort on cancel
        if response == gtk.RESPONSE_OK and self.error_message == 'UNLOCK_SUCCESSFUL':
            return  # close dialog
        if not self.waiting_for_response:
            # sending pw to worker
            if response == gtk.RESPONSE_OK:
                # dont send empty password
                if self.pw_box.get_text() == '':
                    self.pw_box.grab_focus()
                else:
                    self.waiting_for_response = True
                    self.pw_box.set_sensitive(False)
                    self.get_action_area().set_sensitive(False)
                    self.header_text.set_markup(_('Checking passphrase ..'))
                    self.worker.execute(command={'type': 'response',
                                                 'msg': self.pw_box.get_text()
                                                 },
                                        success_callback=self.on_worker_reply,
                                        error_callback=self.on_error)
                dialog.emit_stop_by_name('response')
            # CANCEL/DELETE_EVENT -> abort worker
            else:
                self.worker.execute({'type': 'abort', 'msg': ''}, None, None)
        # always block signal if waiting for worker
        else:
            dialog.emit_stop_by_name('response')

    def communicate(self):
        """ Dialog runs itself and throws an exception if the container wasn't unlocked
            :raises: UserInputError
        """
        try:
            response = self.run()
            if response != gtk.RESPONSE_OK:
                raise UserInputError(self.error_message)  # is empty string in case of cancel/delete -> won't get displayed
        finally:
            self.destroy()

    def on_close_dialog(self, widget, event):
        """ Event handler for delete: block while waiting for worker """
        if self.waiting_for_response:
            return True
