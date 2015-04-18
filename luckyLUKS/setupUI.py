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
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox, QGridLayout, QLabel, QStackedWidget,\
        QMessageBox, QLineEdit, QPushButton, QSpinBox, QComboBox, QFileDialog, QWidget, QStyle, QApplication, QProgressBar, QLayout
except ImportError:  # py2 or py3 without pyqt5
    from PyQt4.QtCore import QTimer, Qt
    from PyQt4.QtGui import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox, QGridLayout, QLabel, QStackedWidget,\
        QMessageBox, QLineEdit, QPushButton, QSpinBox, QComboBox, QFileDialog, QWidget, QStyle, QApplication, QProgressBar, QLayout

from luckyLUKS.unlockUI import FormatContainerDialog, UnlockContainerDialog, UserInputError
from luckyLUKS.utilsUI import QExpander, HelpDialog, show_info, show_alert
from luckyLUKS.utils import is_installed


class SetupDialog(QDialog):

    """ This dialog consists of two parts/tabs: The first one is supposed to help choosing
        container, device name and mount point to unlock an existing container.
        The second tab assists in creating a new encrypted LUKS container.
    """

    def __init__(self, parent):
        """ :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`PyQt4.QtGui.QWidget`
        """
        super(SetupDialog, self).__init__(parent, Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.setWindowTitle(_('luckyLUKS'))

        self.worker = parent.worker
        self.is_busy = False

        # build ui
        self.layout = QVBoxLayout()
        self.layout.setSizeConstraint(QLayout.SetFixedSize)
        style = QApplication.style()
        # set up stacked layout: initially only the main tab pane (unlock/create)
        self.main_pane = QStackedWidget()
        self.tab_pane = QTabWidget()
        self.main_pane.addWidget(self.tab_pane)
        self.layout.addWidget(self.main_pane)
        self.create_pane = None  # init in on_create_container()

        # Unlock Tab
        unlock_grid = QGridLayout()
        unlock_grid.setColumnMinimumWidth(1, 220)
        uheader = QLabel(_('<b>Unlock an encrypted container</b>\n') +
                         _('Please select container file and name'))
        uheader.setContentsMargins(0, 10, 0, 10)
        unlock_grid.addWidget(uheader, 0, 0, 1, 3, Qt.AlignCenter)

        label = QLabel(_('container file'))
        label.setIndent(5)
        unlock_grid.addWidget(label, 1, 0)
        self.unlock_container_file = QLineEdit()
        unlock_grid.addWidget(self.unlock_container_file, 1, 1)
        button_choose_file = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '', self)
        button_choose_file.setToolTip(_('choose file'))
        unlock_grid.addWidget(button_choose_file, 1, 2)
        button_choose_file.clicked.connect(self.on_select_container_clicked)

        label = QLabel(_('device name'))
        label.setIndent(5)
        unlock_grid.addWidget(label, 2, 0)
        self.unlock_device_name = QLineEdit()
        unlock_grid.addWidget(self.unlock_device_name, 2, 1)
        # advanced settings
        a_settings = QExpander(_('Advanced'), self, False)
        unlock_grid.addWidget(a_settings, 3, 0, 1, 3)

        label = QLabel(_('key file'))
        label.setIndent(5)
        unlock_grid.addWidget(label, 4, 0)
        self.unlock_keyfile = QLineEdit()
        unlock_grid.addWidget(self.unlock_keyfile, 4, 1)
        button_choose_uKeyfile = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_uKeyfile.setToolTip(_('choose keyfile'))
        unlock_grid.addWidget(button_choose_uKeyfile, 4, 2)
        button_choose_uKeyfile.clicked.connect(lambda: self.on_select_keyfile_clicked('Unlock'))
        a_settings.addWidgets([unlock_grid.itemAtPosition(4, column).widget() for column in range(0, 3)])

        label = QLabel(_('mount point'))
        label.setIndent(5)
        unlock_grid.addWidget(label, 5, 0)
        self.unlock_mountpoint = QLineEdit()
        unlock_grid.addWidget(self.unlock_mountpoint, 5, 1)
        button_choose_mountpoint = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_mountpoint.setToolTip(_('choose folder'))
        unlock_grid.addWidget(button_choose_mountpoint, 5, 2)
        button_choose_mountpoint.clicked.connect(self.on_select_mountpoint_clicked)
        a_settings.addWidgets([unlock_grid.itemAtPosition(5, column).widget() for column in range(0, 3)])

        unlock_grid.setRowStretch(6, 1)
        unlock_grid.setRowMinimumHeight(6, 10)
        button_help_unlock = QPushButton(style.standardIcon(QStyle.SP_DialogHelpButton), _('Help'))
        button_help_unlock.clicked.connect(self.show_help_unlock)
        unlock_grid.addWidget(button_help_unlock, 7, 2)

        unlock_tab = QWidget()
        unlock_tab.setLayout(unlock_grid)
        self.tab_pane.addTab(unlock_tab, _('Unlock Container'))

        # Create Tab
        create_grid = QGridLayout()
        cheader = QLabel(_('<b>Create a new encrypted container</b>\n') +
                         _('Please choose container file, name and size'))
        cheader.setContentsMargins(0, 10, 0, 10)
        create_grid.addWidget(cheader, 0, 0, 1, 3, Qt.AlignCenter)

        label = QLabel(_('container file'))
        label.setIndent(5)
        create_grid.addWidget(label, 1, 0)
        self.create_container_file = QLineEdit()
        create_grid.addWidget(self.create_container_file, 1, 1)
        button_choose_file = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_file.setToolTip(_('set file'))
        create_grid.addWidget(button_choose_file, 1, 2)
        button_choose_file.clicked.connect(self.on_save_container_clicked)

        label = QLabel(_('device name'))
        label.setIndent(5)
        create_grid.addWidget(label, 2, 0)
        self.create_device_name = QLineEdit()
        create_grid.addWidget(self.create_device_name, 2, 1)

        label = QLabel(_('container size'))
        label.setIndent(5)
        create_grid.addWidget(label, 3, 0)
        self.create_container_size = QSpinBox()
        self.create_container_size.setRange(1, 1000000000)
        self.create_container_size.setValue(1)
        create_grid.addWidget(self.create_container_size, 3, 1)

        self.create_size_unit = QComboBox()
        self.create_size_unit.addItems(['MB', 'GB'])
        self.create_size_unit.setCurrentIndex(1)
        create_grid.addWidget(self.create_size_unit, 3, 2)
        # advanced settings
        a_settings = QExpander(_('Advanced'), self, False)
        create_grid.addWidget(a_settings, 4, 0, 1, 3)

        label = QLabel(_('key file'))
        label.setIndent(5)
        create_grid.addWidget(label, 5, 0)
        self.create_keyfile = QLineEdit()
        create_grid.addWidget(self.create_keyfile, 5, 1)
        button_choose_cKeyfile = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_cKeyfile.setToolTip(_('choose keyfile'))
        create_grid.addWidget(button_choose_cKeyfile, 5, 2)
        button_choose_cKeyfile.clicked.connect(lambda: self.on_select_keyfile_clicked('Create'))
        a_settings.addWidgets([create_grid.itemAtPosition(5, column).widget() for column in range(0, 3)])

        button_create_keyfile = QPushButton(_('Create key file'))
        button_create_keyfile.clicked.connect(self.on_create_keyfile)
        create_grid.addWidget(button_create_keyfile, 6, 1)
        a_settings.addWidgets([button_create_keyfile])

        label = QLabel(_('format'))
        label.setIndent(5)
        create_grid.addWidget(label, 7, 0)
        self.create_encryption_format = QComboBox()
        self.create_encryption_format.addItem('LUKS')
        self.create_encryption_format.addItem('TrueCrypt')
        if not is_installed('tcplay'):
            self.create_encryption_format.setEnabled(False)
        self.create_encryption_format.setCurrentIndex(0)
        create_grid.addWidget(self.create_encryption_format, 7, 1)
        a_settings.addWidgets([create_grid.itemAtPosition(7, column).widget() for column in range(0, 2)])

        label = QLabel(_('filesystem'))
        label.setIndent(5)
        create_grid.addWidget(label, 8, 0)
        filesystems = ['ext4', 'ext2', 'ntfs']
        self.create_filesystem_type = QComboBox()
        for filesystem in filesystems:
            if is_installed('mkfs.' + filesystem):
                self.create_filesystem_type.addItem(filesystem)
        self.create_filesystem_type.setCurrentIndex(0)
        create_grid.addWidget(self.create_filesystem_type, 8, 1)
        a_settings.addWidgets([create_grid.itemAtPosition(8, column).widget() for column in range(0, 2)])

        create_grid.setRowStretch(9, 1)
        create_grid.setRowMinimumHeight(9, 10)
        button_help_create = QPushButton(style.standardIcon(QStyle.SP_DialogHelpButton), _('Help'))
        button_help_create.clicked.connect(self.show_help_create)
        create_grid.addWidget(button_help_create, 10, 2)

        create_tab = QWidget()
        create_tab.setLayout(create_grid)
        self.tab_pane.addTab(create_tab, _('Create New Container'))
        self.tab_pane.currentChanged.connect(self.on_switchpage_event)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))
        self.buttons.accepted.connect(self.on_accepted)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # ui built, add to widget
        self.setLayout(self.layout)

    def on_create_container(self):
        """ Triggered by clicking create.
            Hides the unlock/create pane and switches to a status pane
            where the progress in creating the new container can be followed step by step.
            This shows the header and the first step:
            Initializing the container file with random data
        """
        self.init_create_pane()

        header = QLabel(_('<b>Creating new container</b>\n') +
                        _('patience .. this might take a while'))
        header.setContentsMargins(0, 10, 0, 10)
        self.create_status_grid.addWidget(header, 0, 0, 1, 3, Qt.AlignCenter)

        self.create_status_grid.addWidget(QLabel('<b>' + _('Step') + ' 1/3</b>'), 1, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Container File')), 1, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[0].setRange(0, 100)
        self.create_status_grid.addWidget(self.create_progressbars[0], 2, 0, 1, 3)
        self.create_status_grid.setRowStretch(7, 1)  # top align
        # add to stack widget and switch display
        self.main_pane.addWidget(self.create_pane)
        self.main_pane.setCurrentIndex(1)

        # calculate designated container size for worker and progress indicator
        size = self.create_container_size.value()
        size = size * (1024 * 1024 * 1024 if self.create_size_unit.currentIndex() == 1 else 1024 * 1024)  # GB vs MB
        location = self.encode_qt_output(self.create_container_file.text())
        # start timer for progressbar updates during container creation
        self.create_timer.timeout.connect(lambda: self.display_progress_percent(location, size))
        self.create_timer.start(500)

        self.worker.execute(command={'type': 'request',
                                     'msg': 'create',
                                     'device_name': self.encode_qt_output(self.create_device_name.text()),
                                     'container_path': location,
                                     'container_size': size,
                                     'key_file': self.encode_qt_output(self.create_keyfile.text()) if self.create_keyfile.text() != '' else None,
                                     'filesystem_type': str(self.create_filesystem_type.currentText()),
                                     'encryption_format': str(self.create_encryption_format.currentText()),
                                     },
                            success_callback=self.on_luksFormat_prompt,
                            error_callback=lambda msg: self.display_create_failed(msg, stop_timer=True))

    def on_luksFormat_prompt(self, msg):
        """ Triggered after the container file is created on disk
            Shows information about the next step and asks the user
            for the passphrase to be used with the new container
        """
        self.set_progress_done(self.create_timer, self.create_progressbars[0])

        self.create_status_grid.addWidget(QLabel('<b>' + _('Step') + ' 2/3</b>'), 3, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Encryption')), 3, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[1].setRange(0, 0)
        self.create_status_grid.addWidget(self.create_progressbars[1], 4, 0, 1, 3)

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
        self.set_progress_done(progressbar=self.create_progressbars[1])

        self.create_status_grid.addWidget(QLabel('<b>' + _('Step') + ' 3/3</b>'), 5, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Filesystem')), 5, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[2].setRange(0, 0)
        self.create_status_grid.addWidget(self.create_progressbars[2], 6, 0, 1, 3)

        self.worker.execute(command={'type': 'response', 'msg': ''},
                            success_callback=self.display_create_success,
                            error_callback=self.display_create_failed)

    def display_create_success(self, msg):
        """ Triggered after successful creation of a new container """
        self.set_progress_done(progressbar=self.create_progressbars[2])
        # copy values of newly created container to unlock dlg und reset create values
        self.unlock_container_file.setText(self.create_container_file.text())
        self.unlock_device_name.setText(self.create_device_name.text())
        self.unlock_keyfile.setText(self.create_keyfile.text())
        show_info(self, _('<b>{device_name}\nsuccessfully created!</b>\nClick on unlock to use the new container')
                  .format(device_name=self.encode_qt_output(self.create_device_name.text())), _('Success'))
        # reset create ui and switch to unlock tab
        self.create_container_file.setText('')
        self.create_device_name.setText('')
        self.create_container_size.setValue(1)
        self.create_size_unit.setCurrentIndex(1)
        self.create_keyfile.setText('')
        self.create_filesystem_type.setCurrentIndex(0)
        self.display_create_done()
        self.tab_pane.setCurrentIndex(0)

    def display_create_failed(self, errormessage, stop_timer=False):
        """ Triggered when an error happend during the create process
            :param errormessage: errormessage to be shown
            :type errormessage: str
            :param stop_timer: stop a progress indicator?
            :type stop_timer: bool
        """
        if stop_timer:
            self.set_progress_done(self.create_timer)
        show_alert(self, errormessage)
        self.display_create_done()

    def display_create_done(self):
        """ Helper to hide the create process informations and show the unlock/create pane """
        self.is_busy = False
        self.main_pane.setCurrentIndex(0)
        self.buttons.setEnabled(True)

    def set_progress_done(self, timeout=None, progressbar=None):
        """ Helper to end stop the progress indicator
            :param timeout: Timer to stop
            :type timeout: QTimer or None
            :param progressbar: progressbar widget to set to 'Done'
            :type progressbar: :class:`QProgressBar` or None
        """
        if timeout is not None:
            timeout.stop()
        if progressbar is not None:
            if not progressbar.maximum():
                progressbar.setRange(0, 100)
            progressbar.setValue(100)
            progressbar.setFormat(_('Done'))

    def on_accepted(self):
        """ Event handler for response:
            Start unlock or create action
        """
        try:
            if self.tab_pane.currentIndex() == 1:

                self.on_create_container()

            else:
                UnlockContainerDialog(self,
                                      self.worker,
                                      self.get_luks_device_name(),
                                      self.get_encrypted_container(),
                                      self.get_keyfile(),
                                      self.get_mount_point()
                                      ).communicate()  # blocks

                # optionally create startmenu entry
                self.show_create_startmenu_entry()
                # all good, now switch to main window
                self.accept()

        except UserInputError as error:
            show_alert(self, format_exception(error))

    def init_create_pane(self):
        """ Helper that initializes the ui for the progress indicators shown while creating containers or keyfiles """
        self.is_busy = True
        self.create_progressbars = []
        self.create_timer = QTimer(self)

        self.buttons.setEnabled(False)

        if self.main_pane.count() > 1:  # remove previous create display if any
            self.main_pane.removeWidget(self.create_pane)

        # built ui
        self.create_pane = QWidget()
        self.create_status_grid = QGridLayout()
        self.create_pane.setLayout(self.create_status_grid)
        self.create_status_grid.setVerticalSpacing(5)

    def on_create_keyfile(self):
        """ Triggered by clicking the `create key file` button below the key file text field (create)
            Asks for key file location if not already provided, creates the progress ui and starts a create-thread
        """
        if self.create_keyfile.text() == '':
            key_file = self.encode_qt_output(self.on_save_file(_('new_keyfile.bin')))
        else:
            key_file = self.encode_qt_output(self.create_keyfile.text())

        self.init_create_pane()

        header = QLabel(_('<b>Creating key file</b>'))
        self.create_status_grid.addWidget(header, 1, 0, 1, 3, Qt.AlignCenter)
        header.setContentsMargins(0, 30, 0, 10)

        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[0].setRange(0, 100)
        self.create_status_grid.addWidget(self.create_progressbars[0], 2, 0, 1, 3)
        info = QLabel(_('This might take a while. Since computers are deterministic machines\n'
                        'it is quite a challenge to generate real random data for the key.\n'
                        '\n'
                        'You can speed up the process by typing, moving the mouse\n'
                        'and generally use the computer while the key gets generated.'))
        info.setContentsMargins(0, 10, 0, 10)
        self.create_status_grid.addWidget(info, 3, 0, 1, 3, Qt.AlignCenter)

        self.create_status_grid.setRowStretch(4, 2)  # vertical align
        # add to stack widget and switch display
        self.main_pane.addWidget(self.create_pane)
        self.main_pane.setCurrentIndex(1)

        # start timer for progressbar updates during keyfile creation
        self.create_timer.timeout.connect(lambda: self.display_progress_percent(key_file, 1024))
        self.create_timer.start(500)

        # run QThread with keyfile creation
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
        self.create_keyfile.setText(key_file_path)

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
        mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Ok | QMessageBox.Cancel, self)
        mb.button(QMessageBox.Ok).setText(_('Create shortcut'))
        mb.button(QMessageBox.Cancel).setText(_('No, thanks'))
        if mb.exec_() == QMessageBox.Ok:
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
        filename = _('luckyLUKS') + '-' + ''.join(i for i in self.get_luks_device_name() if i not in ' \/:*?<>|')  # xdg-desktop-menu has problems with some special chars
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
                show_alert(self, format_exception(cpe.output))
                show_info(self, _('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=home_dir_path))
        else:
            show_info(self, _('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=desktop_file_path))

    def reject(self):
        """ Event handler cancel: Ask for confirmation while creating container """
        if self.confirm_close():
            super(SetupDialog, self).reject()

    def closeEvent(self, event):
        """ Event handler close: ask for confirmation while creating container """
        if not self.confirm_close():
            event.ignore()

    def confirm_close(self):
        """ Displays a confirmation dialog if currently busy creating container or keyfile
            :returns: The users decision or True if no create process running
            :rtype: bool
        """
        if self.is_busy:
            message = _('Currently processing your request!\nDo you really want to quit?')
            mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Ok | QMessageBox.Cancel, self)
            mb.button(QMessageBox.Ok).setText(_('Quit'))
            return mb.exec_() == QMessageBox.Ok
        else:
            return True

    def on_switchpage_event(self, index):
        """ Event handler for tab switch: change text on OK button (Unlock/Create) """
        new_ok_label = _('Unlock')
        if index == 1:  # create
            if self.create_filesystem_type.currentText() == '':
                show_alert(self, _('No tools to format the filesystem found\n'
                                   'Please install, eg for Debian/Ubuntu\n'
                                   '`apt-get install e2fslibs ntfs-3g`'))
            new_ok_label = _('Create')
        self.buttons.button(QDialogButtonBox.Ok).setText(new_ok_label)

    def on_select_container_clicked(self):
        """ Triggered by clicking the select button next to container file (unlock) """
        file_path = QFileDialog.getOpenFileName(self, _('Please choose a container file'), os.getenv("HOME"))
        if isinstance(file_path, tuple):  # qt5 returns tuple path/selected filter
            file_path = file_path[0]
        self.unlock_container_file.setText(file_path)
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))

    def on_select_mountpoint_clicked(self):
        """ Triggered by clicking the select button next to mount point """
        self.unlock_mountpoint.setText(QFileDialog.getExistingDirectory(self, _('Please choose a folder as mountpoint'), os.getenv("HOME")))
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))

    def on_select_keyfile_clicked(self, tab):
        """ Triggered by clicking the select button next to key file (both unlock and create tab) """
        file_path = QFileDialog.getOpenFileName(self, _('Please choose a key file'), os.getenv("HOME"))
        if isinstance(file_path, tuple):  # qt5 returns tuple path/selected filter
            file_path = file_path[0]
        if tab == 'Unlock':
            self.unlock_keyfile.setText(file_path)
        elif tab == 'Create':
            self.create_keyfile.setText(file_path)
        self.buttons.button(QDialogButtonBox.Ok).setText(_(tab))

    def on_save_container_clicked(self):
        """ Triggered by clicking the select button next to container file (create)
            Uses a file dialog to set the path of the container file to be created
        """
        self.create_container_file.setText(self.on_save_file(_('new_container.bin')))

    def on_save_file(self, default_filename):
        """ Opens a native file dialog and returns the chosen path of the file to be saved
            The dialog does not allow overwriting existing files - to get this behaviour
            while using native dialogs the QFileDialog has to be reopened on overwrite.
            A bit weird but enables visual consistency with the other file choose dialogs
            :param default_filename: The default filename to be used in the Qt file dialog
            :type default_filename: str/unicode
            :returns: The designated key file path
            :rtype: str/unicode
        """
        def_path = os.path.join(os.getenv("HOME"), default_filename)

        while True:
            save_path = QFileDialog.getSaveFileName(self,
                                                    _('Please create a new file'),
                                                    def_path,
                                                    options=QFileDialog.DontConfirmOverwrite)

            save_path = self.encode_qt_output(save_path[0]) if isinstance(save_path, tuple) else self.encode_qt_output(save_path)
            self.buttons.button(QDialogButtonBox.Ok).setText(_('Create'))  # qt keeps changing this..

            if os.path.exists(save_path):
                show_alert(self, _('File already exists:\n{filename}\n\n'
                                   '<b>Please create a new file!</b>').format(filename=save_path))
                def_path = os.path.join(os.path.basename(save_path), default_filename)
            else:
                return save_path

    def display_progress_percent(self, location, size):
        """ Update value on the container creation progress bar
            :param location: The path of the container file currently being created
            :type location: str
            :param size: The final size the new container in bytes
            :type size: int
        """
        try:
            new_value = int(os.path.getsize(location) / size * 100)
        except Exception:
            new_value = 0
        self.create_progressbars[0].setValue(new_value)

    def get_encrypted_container(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The container file path
            :rtype: str/unicode
        """
        return self.encode_qt_output(self.unlock_container_file.text())

    def get_luks_device_name(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The device name
            :rtype: str/unicode
        """
        return self.encode_qt_output(self.unlock_device_name.text())

    def get_keyfile(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The mount point path
            :rtype: str/unicode or None
        """
        kf = self.encode_qt_output(self.unlock_keyfile.text())
        return kf if kf != '' else None

    def get_mount_point(self):
        """ Getter for QLineEdit text returns python unicode (instead of QString in py2)
            :returns: The mount point path
            :rtype: str/unicode or None
        """
        mp = self.encode_qt_output(self.unlock_mountpoint.text())
        return mp if mp != '' else None

    def encode_qt_output(self, qstring_or_str):
        """ Normalize output from QLineEdit
            :param qstring_or_str: Output from QLineEdit.text()
            :type qstring_or_str: str/QString
            :returns: python unicode (instead of QString in py2)
            :rtype: str/unicode
        """
        try:
            return qstring_or_str.strip()
        except AttributeError:  # py2: 'QString' object has no attribute strip
            return unicode(qstring_or_str.trimmed().toUtf8(), encoding="UTF-8")

    def show_help_create(self):
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
                       '<a href="https://www.google.com/search?q=keychain+usb+drive&tbm=isch">small USB drive</a> '
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
        hd.exec_()

    def show_help_unlock(self):
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
                       '<a href="https://www.google.com/search?q=keychain+usb+drive&tbm=isch">small USB drive</a> '
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
        hd.exec_()
