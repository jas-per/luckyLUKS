"""
This module contains the main window of the application

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

import sys
import os.path

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
try:  # missing in older pygtkcompat
    gtk.status_icon_position_menu = gtk.StatusIcon.position_menu
except AttributeError:
    pass

from luckyLUKS import utils, PROJECT_URL
from luckyLUKS.unlockUI import UnlockContainerDialog, UserInputError
from luckyLUKS.utilsUI import show_alert


class MainWindow(gtk.Window):

    """ A window that shows the current status of the encrypted container
        and a button to unlock/close it. Open containers
        leave an icon in the systray as a reminder to close them eventually.
    """

    def __init__(self, device_name=None, container_path=None, key_file=None, mount_point=None):
        """ Command line arguments checks are done here to be able to display a graphical dialog with error messages .
            If no arguments were supplied on the command line a setup dialog will be shown.
            All commands will be executed from a separate worker process with administrator privileges that gets initialized here.
            :param device_name: The device mapper name
            :type device_name: str/unicode or None
            :param container_path: The path of the container file
            :type container_path: str/unicode or None
            :param key_file: The path of an optional key file
            :type key_file: str/unicode or None
            :param mount_point: The path of an optional mount point
            :type mount_point: str/unicode or None
        """
        super(MainWindow, self).__init__(gtk.WINDOW_TOPLEVEL)
        self.set_resizable(False)

        self.luks_device_name = device_name
        self.encrypted_container = container_path
        self.key_file = key_file
        self.mount_point = mount_point

        self.worker = None
        self.is_waiting_for_worker = False
        self.is_unlocked = False
        self.has_tray = True  # gtk.StatusIcon.is_embedded() has to be checked after init

        # L10n: program name - translatable for startmenu titlebar etc
        self.set_title(_('luckyLUKS'))
        gtk.window_set_default_icon(gtk.icon_theme_get_default().load_icon(gtk.STOCK_DIALOG_AUTHENTICATION, 64, 0))
        self.connect('delete_event', self.on_close_app)

        # check if cryptsetup and sudo are installed
        not_installed_msg = _('{program_name} executable not found!\nPlease install, eg for Debian/Ubuntu\n`apt-get install {program_name}`')
        if not utils.is_installed('cryptsetup'):
            show_alert(self, not_installed_msg.format(program_name='cryptsetup'), critical=True)
        if not utils.is_installed('sudo'):
            show_alert(self, not_installed_msg.format(program_name='sudo'), critical=True)
        # quick sanity checks before asking for passwd
        if os.getuid() == 0:
            show_alert(self, _('Graphical programs should not be run as root!\nPlease call as normal user.'), critical=True)
        if self.encrypted_container and not os.path.exists(self.encrypted_container):
            show_alert(self, _('Container file not accessible\nor path does not exist:\n\n{file_path}').format(file_path=self.encrypted_container), critical=True)

        # only either encrypted_container or luks_device_name supplied
        if bool(self.encrypted_container) != bool(self.luks_device_name):
            show_alert(self, _('Invalid arguments:\n'
                               'Please call without any arguments\n'
                               'or supply both container and name.\n\n'
                               '<b>{executable} -c CONTAINER -n NAME [-m MOUNTPOINT]</b>\n\n'
                               'CONTAINER = Path of the encrypted container file\n'
                               'NAME = A (unique) name to identify the unlocked container\n'
                               'Optional: MOUNTPOINT = where to mount the encrypted filesystem\n\n'
                               'If automatic mounting is configured on your system,\n'
                               'explicitly setting a mountpoint is not required\n\n'
                               'For more information, visit\n'
                               '<a href="{project_url}">{project_url}</a>'
                               ).format(executable=os.path.basename(sys.argv[0]),
                                        project_url=PROJECT_URL), critical=True)

        # spawn worker process with root privileges
        try:
            self.worker = utils.WorkerMonitor(self)
            # start communication thread
            self.worker.start()
        except utils.SudoException as se:
            show_alert(self, format_exception(se), critical=True)
            return

        # if no arguments supplied, display dialog to gather this information
        if self.encrypted_container is None and self.luks_device_name is None:

            from luckyLUKS.setupUI import SetupDialog
            sd = SetupDialog(self)

            response = sd.run()
            if response == gtk.RESPONSE_OK:
                self.luks_device_name = sd.get_luks_device_name()
                self.encrypted_container = sd.get_encrypted_container()
                self.mount_point = sd.get_mount_point()
                self.key_file = sd.get_keyfile()
                sd.destroy()

                self.is_unlocked = True  # all checks in setup dialog -> skip initializing state
            else:
                # user closed dialog -> quit program
                # and check if a keyfile create thread has to be stopped
                # the worker process terminates itself when its parent dies
                if hasattr(sd, 'create_thread') and sd.create_thread.isAlive():
                    sd.create_thread.terminate()
                sys.exit()

        # center window on desktop
        self.set_position(gtk.WIN_POS_CENTER_ALWAYS)

        # widget content
        main_grid = gtk.Table(7, 2)
        main_grid.set_row_spacings(5)
        self.set_border_width(10)

        main_grid.attach(gtk.image_new_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION, gtk.ICON_SIZE_DIALOG), 0, 1, 0, 1, gtk.FILL, gtk.FILL)
        label = gtk.Label()
        label.set_markup('<b>' + _('Handle encrypted container') + '</b>\n')
        main_grid.attach(label, 1, 2, 0, 1, gtk.FILL, gtk.FILL, 10, 10)

        label = gtk.Alignment()
        label.add(gtk.Label(_('Name:')))
        main_grid.attach(label, 0, 1, 1, 2, gtk.FILL, gtk.FILL)
        label = gtk.Label()
        label.set_markup('<b>{dev_name}</b>'.format(dev_name=self.luks_device_name))
        main_grid.attach(label, 1, 2, 1, 2, gtk.FILL, gtk.FILL)

        label = gtk.Alignment()
        label.add(gtk.Label(_('File:')))
        main_grid.attach(label, 0, 1, 2, 3, gtk.FILL, gtk.FILL)
        main_grid.attach(gtk.Label(self.encrypted_container), 1, 2, 2, 3, gtk.FILL, gtk.FILL)

        if self.key_file is not None:
            label = gtk.Alignment()
            label.add(gtk.Label(_('Key:')))
            main_grid.attach(label, 0, 1, 3, 4, gtk.FILL, gtk.FILL)
            main_grid.attach(gtk.Label(self.key_file), 1, 2, 3, 4, gtk.FILL, gtk.FILL)

        if self.mount_point is not None:
            label = gtk.Alignment()
            label.add(gtk.Label(_('Mount:')))
            main_grid.attach(label, 0, 1, 4, 5, gtk.FILL, gtk.FILL)
            main_grid.attach(gtk.Label(self.mount_point), 1, 2, 4, 5, gtk.FILL, gtk.FILL)

        label = gtk.Alignment()
        label.add(gtk.Label(_('Status:')))
        main_grid.attach(label, 0, 1, 5, 6, gtk.FILL, gtk.FILL)
        self.label_status = gtk.Label('')
        main_grid.attach(self.label_status, 1, 2, 5, 6, gtk.FILL, gtk.FILL)
        main_grid.set_row_spacing(5, 10)

        self.button_toggle_status = gtk.Button('')
        self.button_toggle_status.set_size_request(-1, 40)
        self.button_toggle_status.connect('clicked', self.toggle_container_status)
        main_grid.attach(self.button_toggle_status, 1, 2, 6, 7, gtk.FILL, gtk.FILL)

        self.add(main_grid)

        # tray with popup menu
        self.tray = gtk.StatusIcon()
        self.tray.set_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION)
        self.tray.connect("activate", self.toggle_main_window)
        self.tray.set_visible(True)

        self.menu = gtk.Menu()
        menuitem_label = gtk.ImageMenuItem()
        menuitem_label.set_image(gtk.image_new_from_stock(gtk.STOCK_DIALOG_AUTHENTICATION, gtk.ICON_SIZE_MENU))
        menuitem_label.set_label(self.luks_device_name)
        menuitem_label.set_sensitive(False)
        self.menu.append(menuitem_label)
        self.menu.append(gtk.SeparatorMenuItem())

        self.tray_toggle_action = gtk.ImageMenuItem()
        self.tray_toggle_action.set_image(gtk.image_new_from_stock(gtk.STOCK_FULLSCREEN, gtk.ICON_SIZE_MENU))
        self.tray_toggle_action.set_label(_('Hide'))
        self.tray_toggle_action.connect('activate', self.toggle_main_window)
        self.menu.append(self.tray_toggle_action)

        menuitem_quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        menuitem_quit.set_label(_('Quit'))
        menuitem_quit.connect('activate', self.tray_quit)
        self.menu.append(menuitem_quit)

        self.tray.connect("popup_menu", self.tray_popup)

        self.init_status()

    def refresh(self):
        """ Update widgets to reflect current container status. """
        if self.is_unlocked:
            self.label_status.set_markup(_('Container is {unlocked_green_bold}').format(
                unlocked_green_bold='<span foreground="#006400" weight="bold">' + _('unlocked') + '</span>'))
            self.button_toggle_status.set_label(_('Close Container'))
            self.tray.set_tooltip_text(_('{device_name} is unlocked').format(device_name=self.luks_device_name))
        else:
            self.label_status.set_markup(_('Container is {closed_red_bold}').format(
                closed_red_bold='<span foreground="#b22222" weight="bold">' + _('closed') + '</span>'))
            self.button_toggle_status.set_label(_('Unlock Container'))
            self.tray.set_tooltip_text(_('{device_name} is closed').format(device_name=self.luks_device_name))

        self.show_all()

    def tray_popup(self, widget, button, time, data=None):
        """ Triggered by right click on the systray icon: Helper to show a popup menu """

        self.menu.show_all()
        try:
            self.menu.popup(None, None, gtk.status_icon_position_menu, button, time, self.tray)
        except TypeError:  # gtk3
            self.menu.popup(None, None, lambda w, x: self.tray.position_menu(self.menu, self.tray), self.tray, 3, time)

    def tray_quit(self, widget, data=None):
        """ Triggered by clicking on `quit` in the systray popup: asks to close an unlocked container """
        if not self.is_unlocked:
            gtk.main_quit()
        elif not self.is_waiting_for_worker:
            self.show_all()
            self.confirm_close()

    def toggle_main_window(self, widget, data=None):
        """ Triggered by clicking on the systray icon: show/hide main window """
        if self.get_visible():
            self.hide()
            self.tray_toggle_action.set_label(_('Show'))
        else:
            self.show_all()
            self.tray_toggle_action.set_label(_('Hide'))

    def on_close_app(self, widget, data=None):
        """ Triggered by closing the window: If the container is unlocked, the program won't quit but remain in the systray. """
        if not self.is_waiting_for_worker:
            if self.is_unlocked:
                if self.tray.is_embedded():  # since gtk-tray gets initialized a bit randomly its easier to check if present every time here
                    self.hide()
                    self.tray_toggle_action.set_label(_('Show'))
                else:
                    self.confirm_close()
            else:
                gtk.main_quit()
        return True  # block event

    def confirm_close(self):
        """ Inform about opened container and ask for confirmation to close & quit """
        message = _('<b>{device_name}</b> >> {container_path}\n'
                    'is currently <b>unlocked</b>,\n'
                    'Close Container now and quit?').format(device_name=self.luks_device_name,
                                                            container_path=self.encrypted_container)

        md = gtk.MessageDialog(self,
                               gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                               gtk.MESSAGE_QUESTION,
                               gtk.BUTTONS_CANCEL)
        md.add_button(gtk.STOCK_QUIT, gtk.RESPONSE_OK)
        md.set_markup(message)
        response = md.run()
        md.destroy()
        if response == gtk.RESPONSE_OK:
            self.do_close_container(shutdown=True)

    def toggle_container_status(self, widget, data=None):
        """ Unlock or close container """
        if self.is_unlocked:
            self.do_close_container()
        else:
            try:
                UnlockContainerDialog(self, self.worker, self.luks_device_name, self.encrypted_container, self.key_file, self.mount_point).communicate()
                self.is_unlocked = True
            except UserInputError as uie:
                show_alert(self, format_exception(uie))
                self.is_unlocked = False
            self.refresh()

    def do_close_container(self, shutdown=False):
        """ Send close command to worker and supply callbacks
            :param shutdown: Quit application after container successfully closed? (default=False)
            :type shutdown: bool
        """
        self.disable_ui(_('Closing Container ..'))
        self.worker.execute(command={'type': 'request',
                                     'msg': 'close',
                                     'device_name': self.luks_device_name,
                                     'container_path': self.encrypted_container
                                     },
                            success_callback=lambda msg: self.on_container_closed(msg, error=False, shutdown=shutdown),
                            error_callback=lambda msg: self.on_container_closed(msg, error=True, shutdown=shutdown))

    def on_container_closed(self, message, error, shutdown):
        """ Callback after worker closed container
            :param message: Contains an error description if error=True, otherwise the current state of the container (unlocked/closed)
            :type message: str
            :param error: Error during closing of container
            :type error: bool
            :param shutdown: Quit application after container successfully closed?
            :type shutdown: bool
        """
        if error:
            show_alert(self, message)
        else:
            self.is_unlocked = False
        if not error and shutdown:  # automatic shutdown only if container successfully closed
            gtk.main_quit()
        else:
            self.enable_ui()

    def init_status(self):
        """ Request current status of container from worker if needed """
        if not self.is_unlocked:
            self.disable_ui(_('Initializing ..'))
            self.worker.execute(command={'type': 'request',
                                         'msg': 'status',
                                         'device_name': self.luks_device_name,
                                         'container_path': self.encrypted_container,
                                         'key_file': self.key_file,
                                         'mount_point': self.mount_point
                                         },
                                success_callback=self.on_initialized,
                                error_callback=lambda msg: self.on_initialized(msg, error=True))
        else:  # unlocked by setup-dialog -> just refresh UI
            self.enable_ui()

    def on_initialized(self, message, error=False):
        """ Callback after worker send current state of container
            :param message: Contains an error description if error=True, otherwise the current state of the container (unlocked/closed)
            :type message: str
            :param critical: Error during initialization (default=False)
            :type critical: bool
        """
        if error:
            show_alert(self, message, critical=True)
        else:
            self.is_unlocked = (True if message == 'unlocked' else False)
            self.enable_ui()

    def enable_ui(self):
        """ Enable buttons and refresh state """
        self.refresh()
        self.is_waiting_for_worker = False
        self.button_toggle_status.set_sensitive(True)

    def disable_ui(self, reason):
        """ Disable buttons and display waiting message
            :param reason: A waiting message that gets displayed
            :type reason: str/unicode
        """
        self.is_waiting_for_worker = True
        self.button_toggle_status.set_label(reason)
        self.button_toggle_status.set_sensitive(False)
