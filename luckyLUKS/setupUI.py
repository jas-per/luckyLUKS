"""
If the main program gets called without arguments, this GUI will be shown first.

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
from __future__ import division

import os
import sys
import codecs
import subprocess

try:
    import pygtk
    pygtk.require('2.0')
except ImportError:# py3
    import gi
    gi.require_version('Gtk', '3.0')
    from gi import pygtkcompat
    pygtkcompat.enable()
    pygtkcompat.enable_gtk(version='3.0')

import gtk
import gobject

try:  # fix for pygtkcompat
    gtk.combo_box_new_text = gtk.ComboBoxText
except AttributeError:
    pass

from luckyLUKS.unlockUI import FormatContainerDialog, UnlockContainerDialog, UserInputError
from luckyLUKS.utilsUI import HelpDialog, show_info, show_alert
from luckyLUKS.utils import is_installed


class SetupDialog(gtk.Dialog):

    """ This dialog consists of two parts/tabs: The first one is supposed to help choosing
        container, device name and mount point to unlock an existing container.
        The second tab assists in creating a new encrypted LUKS container.
    """

    def __init__(self, parent):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
        """
        super(SetupDialog, self).__init__( _('luckyLUKS'), parent, gtk.DIALOG_DESTROY_WITH_PARENT,
                                   (gtk.STOCK_QUIT, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_resizable(False)
        self.set_border_width(10)

        self.worker = parent.worker
        self.is_busy = False

        # build main pane with two tabs .. gets a bit verbose but using glade wouldn't make too much sense for a little interface like this either
        self.main_pane = gtk.Notebook()
        self.get_content_area().add(self.main_pane)

        # Unlock Tab
        unlock_grid = gtk.Table(8,3)
        unlock_grid.set_row_spacings(5)
        label = gtk.Label()
        label.set_markup(_('<b>Unlock an encrypted container</b>\n') +
                         _('Please select container file and name'))
        unlock_grid.attach(label, 0,3,0,1, gtk.FILL, gtk.FILL, 10, 10)

        label = gtk.Label(_('container file'))
        label.set_alignment(0, 0.5)
        unlock_grid.attach(label, 0,1,1,2, gtk.FILL, gtk.FILL, 5, 5)
        self.unlock_container_file = gtk.Entry()
        self.unlock_container_file.set_width_chars(30)
        unlock_grid.attach(self.unlock_container_file, 1,2,1,2, gtk.FILL, gtk.FILL)
        button_choose_file = gtk.Button()
        button_choose_file.set_image(gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON))
        button_choose_file.set_tooltip_text(_('choose file'))
        unlock_grid.attach(button_choose_file,2,3,1,2, gtk.FILL, gtk.FILL)
        button_choose_file.connect('clicked', self.on_select_container_clicked)

        label = gtk.Label(_('device name'))
        label.set_alignment(0, 0.5)
        unlock_grid.attach(label, 0,1,2,3, gtk.FILL, gtk.FILL, 5, 5)
        self.unlock_device_name = gtk.Entry()
        unlock_grid.attach(self.unlock_device_name, 1,2,2,3, gtk.FILL, gtk.FILL)

        # advanced settings
        a_settings_unlock = gtk.Expander()
        a_settings_unlock.set_label(_('Advanced'))
        a_settings_unlock.connect('notify::expanded',self.on_expand_clicked)
        unlock_grid.attach(a_settings_unlock, 0,3,3,4, gtk.FILL, gtk.FILL)

        label = gtk.Label(_('key file'))
        label.set_alignment(0, 0.5)
        unlock_grid.attach(label, 0,1,4,5, gtk.FILL, gtk.FILL, 5, 5)
        self.unlock_keyfile = gtk.Entry()
        unlock_grid.attach(self.unlock_keyfile, 1,2,4,5, gtk.FILL, gtk.FILL)
        button_choose_uKeyfile = gtk.Button()
        button_choose_uKeyfile.set_image(gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON))
        button_choose_uKeyfile.set_tooltip_text(_('choose keyfile'))
        unlock_grid.attach(button_choose_uKeyfile, 2,3,4,5, gtk.FILL, gtk.FILL)
        button_choose_uKeyfile.connect('clicked', lambda widget: self.on_select_keyfile_clicked(widget, 'Unlock'))
        a_settings_unlock.widgets = [label, self.unlock_keyfile, button_choose_uKeyfile]

        label = gtk.Label(_('mount point'))
        label.set_alignment(0, 0.5)
        unlock_grid.attach(label, 0,1,5,6, gtk.FILL, gtk.FILL, 5, 5)
        self.unlock_mountpoint = gtk.Entry()
        unlock_grid.attach(self.unlock_mountpoint, 1,2,5,6, gtk.FILL, gtk.FILL)
        button_choose_mountpoint = gtk.Button()
        button_choose_mountpoint.set_image(gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON))
        button_choose_mountpoint.set_tooltip_text(_('choose folder'))
        unlock_grid.attach(button_choose_mountpoint, 2,3,5,6, gtk.FILL, gtk.FILL)
        button_choose_mountpoint.connect('clicked', self.on_select_mountpoint_clicked)
        a_settings_unlock.widgets += [label, self.unlock_mountpoint, button_choose_mountpoint]

        button_help_unlock = gtk.Button(_('Help'))
        button_help_unlock.set_image(gtk.image_new_from_stock(gtk.STOCK_HELP, gtk.ICON_SIZE_BUTTON))
        button_help_unlock.connect('clicked', self.show_help_unlock)
        align = gtk.Alignment( 1, 1, 1, 0 )
        align.add(button_help_unlock)
        unlock_grid.attach(align, 2,3,6,7, gtk.EXPAND|gtk.FILL, gtk.EXPAND|gtk.FILL)

        self.main_pane.append_page(unlock_grid, gtk.Label(_('Unlock Container')))

        # Create Tab
        create_grid = gtk.Table(11,3)
        create_grid.set_row_spacings(5)
        label = gtk.Label()
        label.set_markup(_('<b>Create a new encrypted container</b>\n') +
                         _('Please choose container file, name and size'))
        create_grid.attach(label, 0,3,0,1, gtk.FILL, gtk.FILL, 10, 10)

        label = gtk.Label(_('container file'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,1,2, gtk.FILL, gtk.FILL, 5, 5)
        self.create_container_file = gtk.Entry()
        self.create_container_file.set_width_chars(30)
        create_grid.attach(self.create_container_file,1,2,1,2, gtk.FILL, gtk.FILL)
        button_choose_file = gtk.Button()
        button_choose_file.set_image(gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON))
        button_choose_file.set_tooltip_text(_('set file'))
        create_grid.attach(button_choose_file,2,3,1,2, gtk.FILL, gtk.FILL)
        button_choose_file.connect('clicked', self.on_save_container_clicked)

        label = gtk.Label(_('device name'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,2,3, gtk.FILL, gtk.FILL, 5, 5)
        self.create_device_name = gtk.Entry()
        create_grid.attach(self.create_device_name, 1,2,2,3, gtk.FILL, gtk.FILL)

        label = gtk.Label(_('container size'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,3,4, gtk.FILL, gtk.FILL, 5, 5)
        size_range = gtk.Adjustment(1, 1, 1000000000, 1, 0, 0)
        self.create_container_size = gtk.SpinButton()
        self.create_container_size.set_adjustment(size_range)
        self.create_container_size.set_numeric(True)
        self.create_container_size.set_value(1)#gets otherwise set to 0 sometimes!?
        
        create_grid.attach(self.create_container_size, 1,2,3,4, gtk.FILL, gtk.FILL)
        self.create_size_unit = gtk.combo_box_new_text()
        self.create_size_unit.append_text('MB')
        self.create_size_unit.append_text('GB')
        self.create_size_unit.set_active(1)
        create_grid.attach(self.create_size_unit,2,3,3,4, gtk.FILL, gtk.FILL)

        # advanced settings
        a_settings_create = gtk.Expander()
        a_settings_create.set_label(_('Advanced'))
        a_settings_create.connect('notify::expanded', self.on_expand_clicked)
        create_grid.attach(a_settings_create, 0,3,4,5, gtk.FILL, gtk.FILL)

        label = gtk.Label(_('key file'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,5,6, gtk.FILL, gtk.FILL, 5, 5)
        self.create_keyfile = gtk.Entry()
        create_grid.attach(self.create_keyfile, 1,2,5,6, gtk.FILL, gtk.FILL)
        button_choose_cKeyfile = gtk.Button()
        button_choose_cKeyfile.set_image(gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON))
        button_choose_cKeyfile.set_tooltip_text(_('choose keyfile'))
        create_grid.attach(button_choose_cKeyfile, 2,3,5,6, gtk.FILL, gtk.FILL)
        button_choose_cKeyfile.connect('clicked', lambda widget: self.on_select_keyfile_clicked(widget, 'Create'))

        button_create_keyfile = gtk.Button(_('Create key file'))
        button_create_keyfile.connect('clicked', self.on_create_keyfile)
        create_grid.attach(button_create_keyfile, 1,2,6,7, gtk.FILL, gtk.FILL)
        a_settings_create.widgets = [label, self.create_keyfile, button_choose_cKeyfile, button_create_keyfile]

        label = gtk.Label(_('format'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,7,8, gtk.FILL, gtk.FILL, 5, 5)
        self.create_encryption_format = gtk.combo_box_new_text()
        self.create_encryption_format.append_text('LUKS')
        self.create_encryption_format.append_text('TrueCrypt')
        if not is_installed('tcplay'):
            self.create_encryption_format.set_sensitive(False)
        self.create_encryption_format.set_active(0)
        create_grid.attach(self.create_encryption_format, 1,2,7,8, gtk.FILL, gtk.FILL)
        a_settings_create.widgets += [label, self.create_encryption_format]

        label = gtk.Label(_('filesystem'))
        label.set_alignment(0, 0.5)
        create_grid.attach(label, 0,1,8,9, gtk.FILL, gtk.FILL, 5, 5)
        filesystems = ['ext4', 'ext2', 'ntfs']
        self.create_filesystem_type = gtk.combo_box_new_text()
        for filesystem in filesystems:
            if is_installed('mkfs.' + filesystem):
                self.create_filesystem_type.append_text(filesystem)
        self.create_filesystem_type.set_active(0)
        create_grid.attach(self.create_filesystem_type, 1,2,8,9, gtk.FILL, gtk.FILL)
        a_settings_create.widgets += [label, self.create_filesystem_type]

        button_help_create = gtk.Button(_('Help'))
        button_help_create.set_image(gtk.image_new_from_stock(gtk.STOCK_HELP, gtk.ICON_SIZE_BUTTON))
        button_help_create.connect('clicked', self.show_help_create)
        align = gtk.Alignment( 1, 1, 1, 0 )
        align.add(button_help_create)
        create_grid.attach(align, 2,3,9,10, gtk.EXPAND|gtk.FILL, gtk.EXPAND|gtk.FILL)

        self.main_pane.append_page(create_grid, gtk.Label(_('Create New Container')))

        # connect event handler
        self.connect('response', self.on_response_check)
        self.connect('delete_event', self.on_delete_event)
        self.main_pane.connect('switch_page', self.on_switchpage_event)
        self.show_all()
        # initiallly hide advanced settings
        for widget in a_settings_unlock.widgets + a_settings_create.widgets:
            widget.hide()

    def on_create_container(self):
        """ Triggered by clicking create.
            Hides the unlock/create pane and switches to a status pane
            where the progress in creating the new container can be followed step by step.
            This shows the header and the first step:
            Initializing the container file with random data
        """
        self.is_busy = True
        self.create_progressbars = []

        self.create_status_grid = gtk.Table(7,3)
        self.create_status_grid.set_row_spacings(5)
        label = gtk.Label()
        label.set_markup(_('<b>Creating new container</b>\n') +
                         _('patience .. this might take a while'))
        self.create_status_grid.attach(label, 0,3,0,1, gtk.FILL, gtk.FILL, 10, 10)
                
        label = gtk.Label()
        label.set_markup('<b>' +_('Step') + ' 1/3</b>')
        self.create_status_grid.attach(label, 0,1,1,2, gtk.FILL, gtk.FILL)
        self.create_status_grid.attach(gtk.Label(_('Initializing Container File')), 1,2,1,2, gtk.EXPAND|gtk.FILL, gtk.FILL)
        self.create_progressbars.append(gtk.ProgressBar())
        self.create_status_grid.attach(self.create_progressbars[0], 0,3,2,3, gtk.FILL, gtk.FILL)

        # set the size of the progress pane to the current size of the main pane to be hidden (needed because auto-resizing gtk.dialog is used)     
        self.create_status_grid.set_size_request(*self.main_pane.size_request())
        self.main_pane.hide()          
        self.get_content_area().add(self.create_status_grid)
        self.create_status_grid.show_all()
        self.get_action_area().set_sensitive(False)#disable buttons

        # calculate designated container size for worker and progress indicator
        size = self.create_container_size.get_value_as_int()
        size = size * (1024 * 1024 * 1024 if self.create_size_unit.get_active_text() == 'GB' else 1024 * 1024)  # GB vs MB
        location = self.create_container_file.get_text()
        if not os.path.dirname(location):
            location = os.path.join(os.path.expanduser('~'), location)
            self.create_container_file.set_text(location)
        # start timer for progressbar updates during container creation
        self.create_timer = gobject.timeout_add(1000, self.display_progress_percent, location, size)

        self.worker.execute(command={'type': 'request',
                                     'msg': 'create',
                                     'device_name': self.create_device_name.get_text(),
                                     'container_path': location,
                                     'container_size': size,
                                     'key_file': self.create_keyfile.get_text() if self.create_keyfile.get_text() != '' else None,
                                     'filesystem_type': self.create_filesystem_type.get_active_text(),
                                     'encryption_format': self.create_encryption_format.get_active_text(),
                                     },
                            success_callback=self.on_luksFormat_prompt,
                            error_callback=self.display_create_failed)

    def on_luksFormat_prompt(self, msg):
        """ Triggered after the container file is created on disk
            Shows information about the next step and asks the user
            for the passphrase to be used with the new container
        """
        self.set_progress_done(self.create_timer, self.create_progressbars[0])

        label = gtk.Label()
        label.set_markup('<b>' +_('Step') + ' 2/3</b>')
        self.create_status_grid.attach(label, 0,1,3,4, gtk.FILL, gtk.FILL)
        self.create_status_grid.attach(gtk.Label(_('Initializing Encryption')), 1,2,3,4, gtk.EXPAND|gtk.FILL, gtk.FILL)
        self.create_progressbars.append(gtk.ProgressBar())
        self.create_status_grid.attach(self.create_progressbars[1], 0,3,4,5, gtk.FILL, gtk.FILL)
        self.create_timer = gobject.timeout_add(200, self.display_progress_pulse, self.create_progressbars[1])
        self.create_status_grid.show_all()

        if msg == 'getPassword':
            try:
                self.worker.execute(command={'type': 'response',
                                             'msg': FormatContainerDialog(self).get_password()
                                             },
                                    success_callback=self.on_creating_filesystem,
                                    error_callback=self.display_create_failed)
            except UserInputError:  # user cancelled dlg
                self.worker.execute({'type': 'abort', 'msg': ''}, None, None)  # notify worker process
                self.display_create_failed(_('Initialize container aborted'))
        else:  # using keyfile
            self.worker.execute(command={'type': 'response', 'msg': ''},
                                success_callback=self.on_creating_filesystem,
                                error_callback=self.display_create_failed)

    def on_creating_filesystem(self, msg):
        """ Triggered after LUKS encryption got initialized.
            Shows information about the last step
        """
        self.set_progress_done(self.create_timer, self.create_progressbars[1])

        label = gtk.Label()
        label.set_markup('<b>' +_('Step') + ' 3/3</b>')
        self.create_status_grid.attach(label, 0,1,5,6, gtk.FILL, gtk.FILL)
        self.create_status_grid.attach(gtk.Label(_('Initializing Filesystem')), 1,2,5,6, gtk.EXPAND|gtk.FILL, gtk.FILL)
        self.create_progressbars.append(gtk.ProgressBar())
        self.create_status_grid.attach(self.create_progressbars[2], 0,3,6,7, gtk.FILL, gtk.FILL)
        self.create_timer = gobject.timeout_add(200, self.display_progress_pulse, self.create_progressbars[2])
        self.create_status_grid.show_all()

        self.worker.execute(command={'type': 'response', 'msg': ''},
                            success_callback=self.display_create_success,
                            error_callback=self.display_create_failed)

    def display_create_success(self, msg):
        """ Triggered after successful creation of a new container """
        self.set_progress_done(self.create_timer, self.create_progressbars[2])
        #copy values of newly created container to unlock dlg und reset create values
        self.unlock_container_file.set_text(self.create_container_file.get_text())
        self.unlock_device_name.set_text(self.create_device_name.get_text())
        self.unlock_keyfile.set_text(self.create_keyfile.get_text())
        show_info(self, _('<b>{device_name}\nsuccessfully created!</b>\nClick on unlock to use the new container')
                        .format(device_name = self.create_device_name.get_text()), _('Success'))
        # reset create ui and switch to unlock tab
        self.create_container_file.set_text('')
        self.create_device_name.set_text('')
        self.create_container_size.set_value(1)
        self.create_size_unit.set_active(1)
        self.create_keyfile.set_text('')
        self.create_encryption_format.set_active(0)
        self.create_filesystem_type.set_active(0)
        self.display_create_done()
        self.main_pane.set_current_page(0)   
        self.get_widget_for_response(gtk.RESPONSE_OK).grab_focus() 
        
    def display_create_failed(self, errormessage):
        """ Triggered when an error happend during the create process 
            :param errormessage: errormessage to be shown
            :type errormessage: str
        """
        self.set_progress_done(self.create_timer)
        show_alert(self, errormessage)
        self.display_create_done()

    def display_create_done(self):
        """ Helper to hide the create process informations and show the unlock/create pane """
        self.create_status_grid.hide()           
        self.get_content_area().remove(self.create_status_grid)
        self.main_pane.show()
        self.get_action_area().set_sensitive(True)
        self.is_busy = False

    def set_progress_done(self, timeout=None, progressbar=None):
        """ Helper to end stop the progress indicator
            :param timeout: Timer to stop
            :type timeout: TimerID or None
            :param progressbar: progressbar widget to set to 'Done'
            :type progressbar: :class:`gtk.ProgressBar` or None
        """
        if timeout is not None:
            gobject.source_remove(timeout)
        if progressbar is not None:
            progressbar.set_fraction(1)
            progressbar.set_show_text(True)        
            progressbar.set_text(_('Done'))

    def on_response_check(self, dialog, response):
        """ Event handler for response:
            Start unlock or create action
            Block while creating countainer (confirmation dialog will be shown)
        """
        if response == gtk.RESPONSE_OK:
            try:
                if self.main_pane.get_current_page() == 1:
                    
                    self.on_create_container()
                    dialog.emit_stop_by_name('response')
                    
                else:
     
                    UnlockContainerDialog(self,
                                          self.worker,
                                          self.get_luks_device_name(),
                                          self.get_encrypted_container(),
                                          self.get_keyfile(),
                                          self.get_mount_point()
                                          ).communicate()#blocks
                    #optionally create startmenu entry
                    self.show_create_startmenu_entry()
                    #all good, now switch to main window
                    
            except UserInputError as error:
                show_alert(self, format_exception(error))
                dialog.emit_stop_by_name('response')

        elif response == gtk.RESPONSE_DELETE_EVENT and self.is_busy:
            dialog.emit_stop_by_name('response')

    def on_expand_clicked(self, expander, param):
        """ A gtk.Expander can only handle one child widget. This event handler shows/hides multiple widgets """
        if expander.get_expanded():
            for widget in expander.widgets:
                widget.show()
        else:
            for widget in expander.widgets:
                widget.hide()

    def on_create_keyfile(self, widget):
        """ Triggered by clicking the `create key file` button below the key file text field (create)
            Asks for key file location if not already provided, creates the progress ui and starts a create-thread
        """
        if self.create_keyfile.get_text() == '':
            key_file = self.on_save_file(_('new_keyfile.bin'))
            if key_file is None:
                return  # user abort
        else:
            key_file = self.create_keyfile.get_text()

        if not os.path.dirname(key_file):
            key_file = os.path.join(os.path.expanduser('~'), key_file)

        self.is_busy = True
        self.create_progressbars = []

        self.create_status_grid = gtk.VBox(spacing=5)
        header = gtk.Label()
        header.set_markup(_('<b>Creating key file</b>'))
        self.create_status_grid.pack_start(header, False, False, 20)

        self.create_progressbars.append(gtk.ProgressBar())
        self.create_status_grid.pack_start(self.create_progressbars[0], False, False, 0)

        info = gtk.Label()
        info.set_markup(_('This might take a while. Since computers are deterministic machines\n'
                          'it is quite a challenge to generate real random data for the key.\n'
                          '\n'
                          'You can speed up the process by typing, moving the mouse\n'
                          'and generally use the computer while the key gets generated.'))
        self.create_status_grid.pack_start(info, False, False, 10)

        # set the size of the progress pane to the current size of the main pane to be hidden (needed because auto-resizing gtk.dialog is used)
        self.create_status_grid.set_size_request(*self.main_pane.size_request())
        self.main_pane.hide()            
        self.get_content_area().add(self.create_status_grid)
        self.create_status_grid.show_all()
        self.get_action_area().set_sensitive(False)#disable buttons

        # start timer for progressbar updates during keyfile creation
        self.create_timer = gobject.timeout_add(500, self.display_progress_percent, key_file, 1024)

        # run thread with keyfile creation
        from luckyLUKS.utils import KeyfileCreator

        self.create_thread = KeyfileCreator(self, key_file)
        self.create_thread.start()

    def on_keyfile_created(self, key_file_path):
        """ Triggered when key file creation was successful. Restores the normal setup ui """
        self.set_progress_done(self.create_timer, progressbar=self.create_progressbars[0])
        show_info(self, _('<b>{key_file}\nsuccessfully created!</b>\n'
                          'You can use this key file now,\n'
                          'to create a new container.').format(key_file=key_file_path), _('Success'))
        self.display_create_done()
        self.create_keyfile.set_text(key_file_path)

    def show_create_startmenu_entry(self):
        """ Shown after successfull unlock with setup dialog -> ask for shortcut creation """
        message = (_('<b>Successfully unlocked!</b>\n\n'
                     'Do you want to create\n'
                     'a startup menu entry for <b>{device_name}</b>?\n\n'
                     '-> Your password will NOT be saved!\n'
                     '   This just creates a shortcut,\n'
                     '   to the unlock container dialog.\n').format(
            device_name=self.get_luks_device_name())
        )
        md = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL)
        # icons have to be re-set manually otherwise theyd disappear when changing the label
        md.get_widget_for_response(gtk.RESPONSE_OK).set_label(_('Create shortcut'))
        md.get_widget_for_response(gtk.RESPONSE_OK).set_image(gtk.image_new_from_stock(gtk.STOCK_OK, gtk.ICON_SIZE_BUTTON))
        md.get_widget_for_response(gtk.RESPONSE_CANCEL).set_label(_('No, thanks'))
        md.get_widget_for_response(gtk.RESPONSE_CANCEL).set_image(gtk.image_new_from_stock(gtk.STOCK_CANCEL, gtk.ICON_SIZE_BUTTON))
        md.set_markup(message)
        response = md.run()
        md.destroy()
        if response == gtk.RESPONSE_OK:
            self.create_startmenu_entry()

    def create_startmenu_entry(self):
        """ Creates a startmenu entry that lets the user skip the setup dialog and go directly to the main UI
            Includes a workaround for the safety net some desktop environments create around the startupmenu
        """
        import random
        import string
        # command to be saved in shortcut: calling the script with the arguments entered in the dialog
        # put all arguments in single quotes and escape those in the strings (shell escape ' -> '\'')
        cmd = os.path.abspath(sys.argv[0])
        cmd += " -c '" + self.get_encrypted_container().replace("'", "'\\'''") + "'"
        cmd += " -n '" + self.get_luks_device_name().replace("'", "'\\'''") + "'"
        if self.get_mount_point() is not None:
            cmd += " -m '" + self.get_mount_point().replace("'", "'\\'''") + "'"
        if self.get_keyfile() is not None:
            cmd += " -k '" + self.get_keyfile().replace("'", "'\\'''") + "'"

        # create .desktop-file
        try:
            filename = _('luckyLUKS') + '-' + ''.join(i for i in self.get_luks_device_name() if i not in ' \/:*?<>|')  # xdg-desktop-menu has problems with some special chars
        except UnicodeDecodeError:  # py2
            filename = _('luckyLUKS') + '-' + ''.join(i for i in unicode(self.get_luks_device_name()) if i not in ' \/:*?<>|')
        if is_installed('xdg-desktop-menu'):  # create in tmp and add freedesktop menu entry
            # some desktop menus dont delete the .desktop files if a user removes items from the menu but keep track of those files instead
            # those items wont be readded later, the random part of the filename works around this behaviour
            desktop_file_path = os.path.join('/tmp', filename + '-' + ''.join(random.choice(string.ascii_letters) for i in range(4)) + '.desktop')
        else:  # or create in users home dir
            desktop_file_path = os.path.join(os.path.expanduser('~'), filename + '.desktop')

        desktop_file = codecs.open(desktop_file_path, 'w', 'utf-8')

        entry_name = _('Unlock {device_name}').format(device_name=self.get_luks_device_name())
        desktop_file.write("[Desktop Entry]\n")
        desktop_file.write("Name=" + entry_name + "\n")
        desktop_file.write("Comment=" + self.get_luks_device_name() + " " + _('Encrypted Container Tool') + "\n")
        desktop_file.write("GenericName=" + _('Encrypted Container') + "\n")
        desktop_file.write("Categories=Utility;\n")
        desktop_file.write("Exec=" + cmd + "\n")
        desktop_file.write("Icon=dialog-password\n")
        desktop_file.write("NoDisplay=false\n")
        desktop_file.write("StartupNotify=false\n")
        desktop_file.write("Terminal=0\n")
        desktop_file.write("TerminalOptions=\n")
        desktop_file.write("Type=Application\n\n")
        desktop_file.close()

        os.chmod(desktop_file_path, 0o700)  # some distros need the xbit to trust the desktop file

        if is_installed('xdg-desktop-menu'):
            # safest way to ensure updates: explicit uninstall followed by installing a new desktop file with different random part
            import glob
            for desktopfile in glob.glob(os.path.expanduser('~') + '/.local/share/applications/' + filename + '-*.desktop'):
                with open(os.devnull) as DEVNULL:
                    subprocess.call(['xdg-desktop-menu', 'uninstall', desktopfile], stdout=DEVNULL, stderr=subprocess.STDOUT)
            try:
                subprocess.check_output(['xdg-desktop-menu', 'install', '--novendor', desktop_file_path], stderr=subprocess.STDOUT, universal_newlines=True)
                os.remove(desktop_file_path)  # remove from tmp
                show_info(self, _('<b>` {name} `</b>\nadded to start menu').format(name=entry_name), _('Success'))
            except subprocess.CalledProcessError as cpe:
                home_dir_path = os.path.join(os.path.expanduser('~'), os.path.basename(desktop_file_path))
                # move to homedir instead
                from shutil import move
                move(desktop_file_path, home_dir_path)
                show_alert(self, cpe.output)
                show_info(self, _('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=home_dir_path))
        else:
            show_info(self, _('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=desktop_file_path))

    def on_delete_event(self, widget, event):
        """ Event handler for delete: ask for confirmation while creating container """
        if self.is_busy:
            md = gtk.MessageDialog(self, 
              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
              gtk.MESSAGE_WARNING,
              gtk.BUTTONS_CANCEL
            )
            md.set_markup(_('Currently processing your request!\nDo you really want to quit?'))
            md.add_button(gtk.STOCK_QUIT, gtk.RESPONSE_OK)
            response = md.run()
            md.destroy()
            if response != gtk.RESPONSE_OK:
                return True#block close!
        return False

    def on_switchpage_event(self, notebook, widget, page_num, data=None):
        """ Event handler for tab switch: change text on OK button (Unlock/Create) """
        new_ok_label = _('Unlock')
        if page_num == 1:  # create
            if self.create_filesystem_type.get_active_text() == '':
                show_alert(self, _('No tools to format the filesystem found\n'
                                   'Please install, eg for Debian/Ubuntu\n'
                                   '`apt-get install e2fslibs ntfs-3g`'))
            new_ok_label = _('Create')
        # change label on stock button removes icon -> re-set
        self.get_widget_for_response(gtk.RESPONSE_OK).set_label(new_ok_label)
        self.get_widget_for_response(gtk.RESPONSE_OK).set_image(gtk.image_new_from_stock(gtk.STOCK_OK, gtk.ICON_SIZE_BUTTON))

    def on_select_container_clicked(self, widget):
        """ Triggered by clicking the select button next to container file (unlock) """
        dialog = gtk.FileChooserDialog(_('Please choose a container file'), self,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.unlock_container_file.set_text(dialog.get_filename())
        dialog.destroy()

    def on_select_mountpoint_clicked(self, widget):
        """ Triggered by clicking the select button next to mount point """
        dialog = gtk.FileChooserDialog(_('Please choose a folder as mountpoint'), self,
                                       gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_APPLY, gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.unlock_mountpoint.set_text(dialog.get_filename())
        dialog.destroy()

    def on_select_keyfile_clicked(self, widget, tab):
        """ Triggered by clicking the select button next to key file (both unlock and create tab) """
        dialog = gtk.FileChooserDialog(_('Please choose a key file'), self,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            if tab == 'Unlock':
                self.unlock_keyfile.set_text(dialog.get_filename())
            elif tab == 'Create':
                self.create_keyfile.set_text(dialog.get_filename())
        dialog.destroy()

    def on_save_container_clicked(self, widget):
        """ Triggered by clicking the select button next to container file (create)
            Uses a file dialog to set the path of the container file to be created
        """
        new_val = self.on_save_file(_('new_container.bin'))
        if new_val is not None:
            self.create_container_file.set_text(new_val)

    def on_save_file(self, default_filename):
        """ Opens a native file dialog and returns the chosen path of the file to be saved
            The dialog does not allow overwriting existing files - to get this behaviour
            while using native dialogs the QFileDialog has to be reopened on overwrite.
            A bit weird but enables visual consistency with the other file choose dialogs
            :param default_filename: The default filename to be used in the file dialog
            :type default_filename: str/unicode
            :returns: The designated key file path
            :rtype: str/unicode
        """
        dialog = gtk.FileChooserDialog(_('Please create a container file'), self,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dialog.set_current_name(default_filename)
        dialog.set_do_overwrite_confirmation(True)
        dialog.connect('confirm-overwrite', self.show_dont_overwrite)
        response = dialog.run()
        ret = dialog.get_filename() if response == gtk.RESPONSE_OK else None
        dialog.destroy()
        return ret
            
    def show_dont_overwrite(self, file_chooser, data=None):
        """ Triggered by selecting an already existing file in the container filechooser (create) """
        show_alert(file_chooser, _('File already exists:\n{filename}\n\n'
                                   '<b>Please create a new file!</b>').format(filename = file_chooser.get_filename()))
        return gtk.FILE_CHOOSER_CONFIRMATION_SELECT_AGAIN

    def display_progress_percent(self, location, size):
        """ Update value on the container creation progress bar
            :param location: The path of the container file currently being created
            :type location: str
            :param size: The final size the new container in bytes
            :type size: int
        """
        try:
            new_value = float( os.path.getsize(location) / size)
        except Exception:
            new_value = 0
        self.create_progressbars[0].set_fraction(new_value)
        self.create_progressbars[0].set_text('{0:.0f}%'.format(new_value*100))
        return True#continue

    def display_progress_pulse(self, progressbar):
        """ Pulse progress bar 
            :param progressbar: progressbar widget to pulse
            :type progressbar: :class:`gtk.ProgressBar`
        """
        progressbar.pulse()
        return True#continue

    def get_encrypted_container(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The container file path
            :rtype: str/unicode
        """
        return self.unlock_container_file.get_text().strip()

    def get_luks_device_name(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The device name
            :rtype: str/unicode
        """
        return self.unlock_device_name.get_text().strip()

    def get_keyfile(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The mount point path
            :rtype: str/unicode or None
        """
        return self.unlock_keyfile.get_text().strip() if self.unlock_keyfile.get_text().strip() != '' else None

    def get_mount_point(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The mount point path
            :rtype: str/unicode or None
        """
        return self.unlock_mountpoint.get_text().strip() if self.unlock_mountpoint.get_text().strip() != '' else None

    def show_help_create(self, widget):
        """ Triggered by clicking the help button (create tab) """
        header_text = _('<b>Create a new encrypted container</b>\n')
        basic_help = _('Enter the path of the <b>new container file</b> in the textbox '
                       'or click the button next to the box for a graphical create file dialog.'
                       '\n\n'
                       'The <b>device name</b> will be used to identify the unlocked container. '
                       'It can be any name up to 16 unicode characters, as long as it is unique.'
                       '\n\n'
                       'The <b>size</b> of the container can be provided in GB or MB. The container '
                       'will get initialized with random data, this can take quite a while - '
                       '1 hour for a 10GB container on an external drive is nothing unusual.')
        advanced_topics = [
            {'head': _('key file'),
             'text': _('A key file can be used to allow access to an encrypted container instead of a password. '
                       'Using a key file resembles unlocking a door with a key in the real world - anyone with '
                       'access to the key file can open your encrypted container. Make sure to store it at a '
                       'protected location. Its okay to store it on your computer if you are using an already '
                       'encrypted harddrive or a digital keystore. Having the key file on a '
                       '<a href="https://www.google.com/search?q=keychain+usb+drive&amp;tbm=isch">small USB drive</a> '
                       'attached to your real chain of keys would be an option as well.\n'
                       'Since you dont have to enter a password, using a key file can be a convenient way to '
                       'access your encrypted container. Just make sure you dont lose the key (file) ;)') +
                       _('\n\n'
                         'Although basically any file could be used as a key file, a file with predictable content '
                         'leads to similar problems as using weak passwords. Audio files or pictures are a good choice. '
                         'If unsure use the `create key file` button to generate a small key file filled with random data.')},
            {'head': _('encryption format'),
             'text': _('The standard disk encryption format on Linux is called LUKS. '
                       'With <a href="https://github.com/t-d-k/doxbox">doxbox</a> you can use LUKS containers on Windows as well. '
                       'The TrueCrypt format is quite popular on Windows/Mac, and can be created '
                       'on Linux if `tcplay` is installed. Please note, that "hidden" TrueCrypt '
                       'partitions are not supported by luckyLUKS!')},
            {'head': _('filesystem'),
             'text': _('Choose the ntfs filesystem to be able to access your data from Linux, '
                       'Windows and Mac OSX. Since access permissions cannot be mapped from '
                       'ntfs to Linux, access to ntfs devices is usually not restricted '
                       '-> take care when using unlocked ntfs devices in a multiuser environment!')}
        ]
        hd = HelpDialog(self, header_text, basic_help, advanced_topics)
        hd.run()
        hd.destroy()

    def show_help_unlock(self, widget):
        """ Triggered by clicking the help button (unlock tab) """
        header_text = _('<b>Unlock an encrypted container</b>\n')
        basic_help = _('Select the encrypted <b>container file</b> by clicking the button next to '
                       'the textbox. Both LUKS and Truecrypt containers are supported!'
                       '\n\n'
                       'The <b>device name</b> will be used to identify the unlocked container. '
                       'It can be any name up to 16 unicode characters, as long as it is unique '
                       '-> you cannot give two unlocked containers the same name')
        advanced_topics = [
            {'head': _('key file'),
             'text': _('A key file can be used to allow access to an encrypted container instead of a password. '
                       'Using a key file resembles unlocking a door with a key in the real world - anyone with '
                       'access to the key file can open your encrypted container. Make sure to store it at a '
                       'protected location. Its okay to store it on your computer if you are using an already '
                       'encrypted harddrive or a digital keystore. Having the key file on a '
                       '<a href="https://www.google.com/search?q=keychain+usb+drive&amp;tbm=isch">small USB drive</a> '
                       'attached to your real chain of keys would be an option as well.\n'
                       'Since you dont have to enter a password, using a key file can be a convenient way to '
                       'access your encrypted container. Just make sure you dont lose the key (file) ;)')},
            {'head': _('mount point'),
             'text': _('The mount point is the folder on your computer, where you can '
                       'access the files inside the container after unlocking. '
                       'If automatic mounting is configured on your system (eg with udisks), '
                       'explicitly setting a mountpoint is not neccessary (but still possible).')}
        ]
        hd = HelpDialog(self, header_text, basic_help, advanced_topics)
        hd.run()
        hd.destroy()
        
