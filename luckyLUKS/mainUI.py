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
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QDesktopWidget, QDialog,\
        QSystemTrayIcon, QMessageBox, QMenu, QAction, QLabel, QPushButton, QGridLayout, QStyle
    from PyQt5.QtGui import QIcon
except ImportError:  # py2 or py3 without pyqt5
    from PyQt4.QtCore import Qt
    from PyQt4.QtGui import QApplication, QWidget, QMainWindow, QDesktopWidget, QDialog,\
        QSystemTrayIcon, QMessageBox, QIcon, QMenu, QAction, QLabel, QPushButton, QGridLayout, QStyle

from luckyLUKS import utils, PROJECT_URL
from luckyLUKS.unlockUI import UnlockContainerDialog, UserInputError
from luckyLUKS.utilsUI import show_alert


class MainWindow(QMainWindow):

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
        super(MainWindow, self).__init__()

        self.luks_device_name = device_name
        self.encrypted_container = container_path
        self.key_file = key_file
        self.mount_point = mount_point

        self.worker = None
        self.is_waiting_for_worker = False
        self.is_unlocked = False
        self.is_initialized = False
        self.has_tray = QSystemTrayIcon.isSystemTrayAvailable()

        # L10n: program name - translatable for startmenu titlebar etc
        self.setWindowTitle(_('luckyLUKS'))
        self.setWindowIcon(QIcon.fromTheme('dialog-password', QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)))

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

            if sd.exec_() == QDialog.Accepted:
                self.luks_device_name = sd.get_luks_device_name()
                self.encrypted_container = sd.get_encrypted_container()
                self.mount_point = sd.get_mount_point()
                self.key_file = sd.get_keyfile()

                self.is_unlocked = True  # all checks in setup dialog -> skip initializing state
            else:
                # user closed dialog -> quit program
                QApplication.instance().quit()
                return

        # center window on desktop
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        # widget content
        main_grid = QGridLayout()
        main_grid.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(QIcon.fromTheme('dialog-password', QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)).pixmap(32))
        main_grid.addWidget(icon, 0, 0)
        main_grid.addWidget(QLabel('<b>' + _('Handle encrypted container') + '</b>\n'), 0, 1, alignment=Qt.AlignCenter)

        main_grid.addWidget(QLabel(_('Name:')), 1, 0)
        main_grid.addWidget(QLabel('<b>{dev_name}</b>'.format(dev_name=self.luks_device_name)), 1, 1, alignment=Qt.AlignCenter)

        main_grid.addWidget(QLabel(_('File:')), 2, 0)
        main_grid.addWidget(QLabel(self.encrypted_container), 2, 1, alignment=Qt.AlignCenter)

        if self.key_file is not None:
            main_grid.addWidget(QLabel(_('Key:')), 3, 0)
            main_grid.addWidget(QLabel(self.key_file), 3, 1, alignment=Qt.AlignCenter)

        if self.mount_point is not None:
            main_grid.addWidget(QLabel(_('Mount:')), 4, 0)
            main_grid.addWidget(QLabel(self.mount_point), 4, 1, alignment=Qt.AlignCenter)

        main_grid.addWidget(QLabel(_('Status:')), 5, 0)
        self.label_status = QLabel('')
        main_grid.addWidget(self.label_status, 5, 1, alignment=Qt.AlignCenter)

        self.button_toggle_status = QPushButton('')
        self.button_toggle_status.setMinimumHeight(34)
        self.button_toggle_status.clicked.connect(self.toggle_container_status)
        main_grid.setRowMinimumHeight(6, 10)
        main_grid.addWidget(self.button_toggle_status, 7, 1)

        widget = QWidget()
        widget.setLayout(main_grid)
        widget.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(widget)

        # tray popup menu
        if self.has_tray:
            tray_popup = QMenu(self)
            tray_popup.addAction(QIcon.fromTheme('dialog-password', QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)), self.luks_device_name).setEnabled(False)
            tray_popup.addSeparator()
            self.tray_toggle_action = QAction(QApplication.style().standardIcon(QStyle. SP_DesktopIcon), _('Hide'), self)
            self.tray_toggle_action.triggered.connect(self.toggle_main_window)
            tray_popup.addAction(self.tray_toggle_action)
            quit_action = QAction(QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical), _('Quit'), self)
            quit_action.triggered.connect(self.tray_quit)
            tray_popup.addAction(quit_action)
            # systray
            self.tray = QSystemTrayIcon(self)
            self.tray.setIcon(QIcon.fromTheme('dialog-password', QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)))
            self.tray.setContextMenu(tray_popup)
            self.tray.activated.connect(self.toggle_main_window)
            self.tray.show()

        self.init_status()

    def refresh(self):
        """ Update widgets to reflect current container status. Adds systray icon if needed """
        if self.is_unlocked:
            self.label_status.setText(_('Container is {unlocked_green_bold}').format(
                unlocked_green_bold='<font color="#006400"><b>' + _('unlocked') + '</b></font>'))
            self.button_toggle_status.setText(_('Close Container'))
            if self.has_tray:
                self.tray.setToolTip(_('{device_name} is unlocked').format(device_name=self.luks_device_name))
        else:
            self.label_status.setText(_('Container is {closed_red_bold}').format(
                closed_red_bold='<font color="#b22222"><b>' + _('closed') + '</b></font>'))
            self.button_toggle_status.setText(_('Unlock Container'))
            if self.has_tray:
                self.tray.setToolTip(_('{device_name} is closed').format(device_name=self.luks_device_name))

        self.show()
        self.setFixedSize(self.sizeHint())

    def tray_quit(self):
        """ Triggered by clicking on `quit` in the systray popup: asks to close an unlocked container """
        if not self.is_unlocked:
            QApplication.instance().quit()
        elif not self.is_waiting_for_worker:
            self.show()
            self.confirm_close()

    def toggle_main_window(self, tray_icon_clicked):
        """ Triggered by clicking on the systray icon: show/hide main window """
        if not tray_icon_clicked or tray_icon_clicked == QSystemTrayIcon.Trigger:  # don't activate on rightclick/contextmenu
            if self.isVisible():
                self.hide()
                self.tray_toggle_action.setText(_('Show'))
            else:
                self.show()
                self.tray_toggle_action.setText(_('Hide'))

    def closeEvent(self, event):
        """ Triggered by closing the window: If the container is unlocked, the program won't quit but remain in the systray. """
        if not self.is_waiting_for_worker:
            if self.is_unlocked:
                if self.has_tray:
                    self.hide()
                    self.tray_toggle_action.setText(_('Show'))
                else:
                    self.confirm_close()
                event.ignore()
            else:
                event.accept()

    def confirm_close(self):
        """ Inform about opened container and ask for confirmation to close & quit """
        message = _('<b>{device_name}</b> >> {container_path}\n'
                    'is currently <b>unlocked</b>,\n'
                    'Close Container now and quit?').format(device_name=self.luks_device_name,
                                                            container_path=self.encrypted_container)
        mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Ok | QMessageBox.Cancel, self)
        mb.button(QMessageBox.Ok).setText(_('Quit'))
        if mb.exec_() == QMessageBox.Ok:
            self.do_close_container(shutdown=True)

    def customEvent(self, event):
        """ Receives response from worker and calls supplied callback function """
        event.callback(event.response)

    def toggle_container_status(self):
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
            QApplication.instance().quit()
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
        self.is_initialized = True  # qt event loop can start now

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
        self.button_toggle_status.setEnabled(True)

    def disable_ui(self, reason):
        """ Disable buttons and display waiting message
            :param reason: A waiting message that gets displayed
            :type reason: str/unicode
        """
        self.is_waiting_for_worker = True
        self.button_toggle_status.setText(reason)
        self.button_toggle_status.setEnabled(False)
