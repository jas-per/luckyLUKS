"""
If the main program gets called without arguments, this GUI will be shown first.

luckyLUKS Copyright (c) 2014, Jasper van Hoorn (muzius@gmail.com)

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

from PyQt4.QtCore import QTimer, Qt
from PyQt4.QtGui import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox, QGridLayout, QLabel, QStackedWidget,\
QMessageBox, QLineEdit, QPushButton, QSpinBox, QComboBox, QFileDialog, QWidget, QStyle, QApplication, QProgressBar

from luckyLUKS import PROJECT_URL
from luckyLUKS.unlockUI import FormatContainerDialog, UnlockContainerDialog
from luckyLUKS.util import UserInputError, is_installed


class SetupDialog(QDialog):
    """ This dialog consists of two parts/tabs: The first one is supposed to help choosing
        container, device name and mount point to unlock an existing container.
        The second tab assists in creating a new encrypted LUKS container.
    """
    
    def __init__(self, parent):
        """ :param parent: The parent window/dialog used to enable modal behaviour 
            :type parent: :class:`QWidget`
        """
        super(SetupDialog, self).__init__(parent)
        self.setWindowTitle(_('luckyLUKS'))

        self.worker = parent.worker
        self.is_creating_countainer = False

        #build ui
        self.layout = QVBoxLayout()
        style = QApplication.style()
        #set up stacked layout: initially only the main tab pane (unlock/create), gets switched when create process started
        self.main_pane = QStackedWidget()
        self.tab_pane = QTabWidget()
        self.main_pane.addWidget(self.tab_pane)
        self.layout.addWidget(self.main_pane)
        
        #Unlock Tab
        unlock_grid = QGridLayout()
        unlock_grid.setColumnMinimumWidth(1,200)
        uheader = QLabel(_('<b>Unlock encrypted LUKS container</b>\n' + 
                           'Please select container file and name\n' + 
                           'and optionally a mount point'))
        uheader.setContentsMargins(0,10,0,10)
        unlock_grid.addWidget(uheader, 0, 0, 1, 3, Qt.AlignCenter)
        
        unlock_grid.addWidget(QLabel(_('container file')), 1,0)
        self.unlock_container_file = QLineEdit()
        unlock_grid.addWidget(self.unlock_container_file, 1,1)
        button_choose_file = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '', self)
        button_choose_file.setToolTip(_('choose file'))
        unlock_grid.addWidget(button_choose_file, 1,2)
        button_choose_file.clicked.connect(self.on_select_file_clicked)
        
        unlock_grid.addWidget(QLabel(_('device name')), 2,0)
        self.unlock_device_name = QLineEdit()
        unlock_grid.addWidget(self.unlock_device_name, 2,1)

        unlock_grid.addWidget(QLabel(_('[mount point]')), 3,0)
        self.unlock_mountpoint = QLineEdit()
        unlock_grid.addWidget(self.unlock_mountpoint, 3,1)
        button_choose_mountpoint = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_mountpoint.setToolTip(_('choose folder'))
        unlock_grid.addWidget(button_choose_mountpoint, 3,2)
        button_choose_mountpoint.clicked.connect(self.on_select_mountpoint_clicked)

        unlock_grid.setRowStretch(4,1)
        button_help_unlock = QPushButton(style.standardIcon(QStyle.SP_DialogHelpButton), _('Help'))
        button_help_unlock.clicked.connect(self.show_help_unlock)
        unlock_grid.addWidget(button_help_unlock, 5,2)

        unlock_tab = QWidget()
        unlock_tab.setLayout(unlock_grid) 
        self.tab_pane.addTab(unlock_tab, _('Unlock Container'))

        #Create Tab
        create_grid = QGridLayout()
        cheader = QLabel(_('<b>Create new encrypted LUKS container</b>\n' + 
                           'Please choose container file and name\n' + 
                           'and select filesystem and size'))
        cheader.setContentsMargins(0,10,0,10)
        create_grid.addWidget(cheader, 0,0,1,3, Qt.AlignCenter)

        create_grid.addWidget(QLabel(_('container file')), 1,0)
        self.create_container_file = QLineEdit()
        create_grid.addWidget(self.create_container_file, 1,1)
        button_choose_file = QPushButton(style.standardIcon(QStyle.SP_DialogOpenButton), '')
        button_choose_file.setToolTip(_('set file'))
        create_grid.addWidget(button_choose_file, 1,2)
        button_choose_file.clicked.connect(self.on_save_file_clicked)

        create_grid.addWidget(QLabel(_('device name')), 2,0)
        self.create_device_name = QLineEdit()
        create_grid.addWidget(self.create_device_name, 2,1)

        create_grid.addWidget(QLabel(_('container size')), 3,0)
        self.create_container_size = QSpinBox()
        self.create_container_size.setRange(1, 1000000000)
        self.create_container_size.setValue(1)
        create_grid.addWidget(self.create_container_size, 3,1)
        
        self.create_size_unit = QComboBox()
        self.create_size_unit.addItems(['MB','GB'])
        self.create_size_unit.setCurrentIndex(1)
        create_grid.addWidget(self.create_size_unit, 3,2)
        
        create_grid.addWidget(QLabel(_('filesystem')), 4,0)
        filesystems = ['ext4', 'ext2', 'ntfs']
        self.create_filesystem_type = QComboBox()
        for filesystem in filesystems:
            if is_installed('mkfs.' + filesystem):
                self.create_filesystem_type.addItem(filesystem)
        self.create_filesystem_type.setCurrentIndex(0)
        create_grid.addWidget(self.create_filesystem_type, 4,1)

        create_grid.setRowStretch(5,1)
        button_help_create = QPushButton(style.standardIcon(QStyle.SP_DialogHelpButton), _('Help'))
        button_help_create.clicked.connect(self.show_help_create)
        create_grid.addWidget(button_help_create, 6,2)

        create_tab = QWidget()
        create_tab.setLayout(create_grid) 
        self.tab_pane.addTab(create_tab, _('Create New Container'))
        self.tab_pane.currentChanged.connect(self.on_switchpage_event)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox( QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent = self)
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))
        self.buttons.accepted.connect(self.on_accepted)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        #ui built, add to widget
        self.setLayout(self.layout)


    def on_create_container(self):
        """ Triggered by clicking create.
            Hides the unlock/create pane and switches to a status pane
            where to progress creating the new container can be followed step by step.
            This shows the header and the first step:
            Initializing the container file with random data
        """
        self.is_creating_countainer = True
        self.create_progressbars = []
        self.create_timer = QTimer(self)
        
        self.buttons.setEnabled(False)

        if self.main_pane.count() > 1:#remove previous create disply if any
            self.main_pane.removeWidget(self.create_pane)
        
        # built ui
        self.create_pane = QWidget()
        self.create_status_grid = QGridLayout()
        self.create_pane.setLayout(self.create_status_grid)
        self.create_status_grid.setVerticalSpacing(5)

        header = QLabel(_('<b>Creating new LUKS container</b>\n' + 
                          'patience .. this might take a while'))
        header.setContentsMargins(0,10,0,10)
        self.create_status_grid.addWidget(header, 0, 0, 1, 3, Qt.AlignCenter)
                 
        self.create_status_grid.addWidget(QLabel('<b>' + _('Step') + ' 1/3</b>'), 1, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Container File')), 1, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[0].setRange (0, 100)
        self.create_status_grid.addWidget(self.create_progressbars[0], 2, 0, 1, 3)
        self.create_status_grid.setRowStretch(7,1)#top align
        # add to stack widget and switch display
        self.main_pane.addWidget(self.create_pane)
        self.main_pane.setCurrentIndex(1)
 
        # calculate designated container size for worker and progress indicator
        size = self.create_container_size.value()
        size = size * (1024*1024*1024 if self.create_size_unit.currentIndex() == 1 else 1024*1024)#GB vs MB
        location = self.encode_qt_output(self.create_container_file.text())
        # start timer for progressbar updates during container creation
        self.create_timer.timeout.connect(lambda: self.display_progress_percent(location, size))
        self.create_timer.start(500)
        
        self.worker.execute(command = {'type': 'request',
                                       'msg': 'create',
                                       'device_name': self.encode_qt_output(self.create_device_name.text()),
                                       'container_path': location,
                                       'container_size': size,
                                       'filesystem_type': str(self.create_filesystem_type.currentText())
                                       },
                            success_callback = self.on_luksFormat_prompt,
                            error_callback = lambda msg: self.display_create_failed(msg, stop_timer = True))
 
 
    def on_luksFormat_prompt(self, msg):
        """ Triggered after the container file is created on disk
            Shows information about the next step and asks the user
            for the passphrase to be used with the new container
        """
        self.set_progress_done(self.create_timer, self.create_progressbars[0])
         
        self.create_status_grid.addWidget(QLabel('<b>' +_('Step') + ' 2/3</b>'), 3, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Encryption')), 3, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[1].setRange (0, 0)
        self.create_status_grid.addWidget(self.create_progressbars[1], 4, 0, 1, 3)
        
        try:
            self.worker.execute(command = {'type': 'response',
                                            'msg': FormatContainerDialog(self).get_password()
                                           }, 
                                success_callback = self.on_creating_filesystem,
                                error_callback = self.display_create_failed)
        except UserInputError:#user cancelled dlg
            self.worker.execute({'type': 'abort','msg': ''}, None, None) #notify worker process
            self.display_create_failed(_('Initialize LUKS aborted'), step=2)
         

    def on_creating_filesystem(self, msg):
        """ Triggered after LUKS encryption got initialized.
            Shows information about the last step
        """
        self.set_progress_done(progressbar=self.create_progressbars[1])
         
        self.create_status_grid.addWidget(QLabel('<b>' +_('Step') + ' 3/3</b>'), 5, 0)
        self.create_status_grid.addWidget(QLabel(_('Initializing Filesystem')), 5, 1)
        self.create_progressbars.append(QProgressBar())
        self.create_progressbars[2].setRange (0, 0)
        self.create_status_grid.addWidget(self.create_progressbars[2], 6, 0, 1, 3)
 
        self.worker.execute(command = {'type': 'response','msg': ''}, 
                            success_callback = self.display_create_success,
                            error_callback = self.display_create_failed )
 
 
    def display_create_success(self, msg):
        """ Triggered after successful creation of a new container """
        self.set_progress_done(progressbar=self.create_progressbars[2])
        #copy values of newly created container to unlock dlg und reset create values
        self.unlock_container_file.setText(self.create_container_file.text())
        self.unlock_device_name.setText(self.create_device_name.text())
        self.show_info(_('<b>{device_name}\nsuccessfully created!</b>\nClick on unlock to use the new container')
                       .format(device_name = self.encode_qt_output(self.create_device_name.text())), _('Success'))
        # reset create ui and switch to unlock tab
        self.create_container_file.setText('')
        self.create_device_name.setText('')
        self.create_container_size.setValue(1)
        self.create_size_unit.setCurrentIndex(1)
        self.create_filesystem_type.setCurrentIndex(0)
        self.display_create_done()
        self.tab_pane.setCurrentIndex(0)

    
    def display_create_failed(self, errormessage, stop_timer = False):
        """ Triggered when an error happend during the create process 
            :param errormessage: errormessage to be shown
            :type errormessage: str
            :param stop_timer: stop a progress indicator?
            :type stop_timer: bool
        """
        if stop_timer:
            self.set_progress_done(self.create_timer)
        self.show_alert(errormessage)
        self.display_create_done()
 
 
    def display_create_done(self):
        """ Helper to hide the create process informations and show the unlock/create pane """
        self.is_creating_countainer = False
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
                progressbar.setRange(0,100)
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
 
                UnlockContainerDialog( self,
                                       self.worker,
                                       self.get_luks_device_name(),
                                       self.get_encrypted_container(),
                                       self.get_mount_point()
                                       ).communicate()#blocks
                                       
                #optionally create startmenu entry
                self.show_create_startmenu_entry()
                #all good, now switch to main window
                self.accept()
                
        except UserInputError as error:
            self.show_alert(format_exception(error))


    def show_create_startmenu_entry(self):
        """ Shown after successfull unlock with setup dialog -> ask for shortcut creation """
        message =   (_('<b>Successfully unlocked!</b>\n\n'
                       'Do you want to create\n' +
                       'a startup menu entry for <b>{device_name}</b>?\n\n' +
                       '-> Your password will NOT be saved!\n' +
                       '   This just creates a shortcut,\n' +
                       '   to the unlock container dialog.\n').format(
                        device_name = self.get_luks_device_name())
                     )
        mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Ok | QMessageBox.Cancel, self)
        mb.setButtonText(QMessageBox.Ok, _('Create shortcut'))
        mb.setButtonText(QMessageBox.Cancel, _('No, thanks'))
        if mb.exec_() == QMessageBox.Ok:
            self.create_startmenu_entry()


    def create_startmenu_entry(self):
        """ Creates a startmenu entry that lets the user skip the setup dialog and go directly to the main UI """
        # command to be saved in shortcut: calling the script with the arguments entered in the dialog
        # put all arguments in single quotes and escape those in the strings (shell escape ' -> '\'')
        cmd = os.path.abspath(sys.argv[0])
        cmd += " -c '" + self.get_encrypted_container().replace("'","'\\'''") + "'"
        cmd += " -n '" + self.get_luks_device_name().replace("'","'\\'''") + "'"
        if self.get_mount_point() is not None:
            cmd += " -m '" + self.get_mount_point().replace("'","'\\'''") + "'"
             
        #create .desktop-file
        if is_installed('xdg-desktop-menu'):#create in tmp and add freedesktop menu entry
            desktop_file_path = '/tmp'            
        else:#or create in users home dir
            desktop_file_path = os.path.expanduser('~')
        desktop_file_path = os.path.join(desktop_file_path, _('luckyLUKS') + '-' + self.get_luks_device_name() + '.desktop')
             
        desktop_file = codecs.open(desktop_file_path, 'w', 'utf-8') 

        entry_name = _('Unlock {device_name}').format(device_name = self.get_luks_device_name())
        desktop_file.write("[Desktop Entry]\n")
        desktop_file.write("Comment=" + self.get_luks_device_name() + " " + _('Encrypted Container Tool') + "\n")
        desktop_file.write("Categories=Utility;\n")
        desktop_file.write("Exec=" + cmd + "\n")
        desktop_file.write("GenericName=" + _('Encrypted Container') + "\n")
        desktop_file.write("Icon=dialog-password\n")
        desktop_file.write("Name=" + entry_name + "\n")
        desktop_file.write("NoDisplay=false\n")
        desktop_file.write("Path[$e]=\n")
        desktop_file.write("StartupNotify=false\n")
        desktop_file.write("Terminal=0\n")
        desktop_file.write("TerminalOptions=\n")
        desktop_file.write("Type=Application\n\n")
        desktop_file.close()
         
        os.chmod(desktop_file_path, 0o600)

        if is_installed('xdg-desktop-menu'):
            try:
                subprocess.check_output(['xdg-desktop-menu', 'installs', '--novendor', desktop_file_path], stderr=subprocess.STDOUT, universal_newlines=True)
                os.remove(desktop_file_path)# remove from tmp
                self.show_info(_('<b>` {name} `</b>\nadded to start menu').format(name = entry_name), _('Success'))
            except subprocess.CalledProcessError as cpe:
                home_dir_path = os.path.join(os.path.expanduser('~'), os.path.basename(desktop_file_path))
                #move to homedir instead
                from shutil import move
                move(desktop_file_path, home_dir_path)
                self.show_alert(format_exception(cpe.output))
                self.show_info(_('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=home_dir_path), '')
        else:
            self.show_info(_('Adding to start menu not possible,\nplease place your shortcut manually.\n\nDesktop file saved to\n{location}').format(location=desktop_file_path), '')
        

    def reject(self):
        """ Event handler cancel: Ask for confirmation while creating container """
        if self.confirm_close():
            super(SetupDialog, self).reject()
        
        
    def closeEvent(self, event):
        """ Event handler close: ask for confirmation while creating container """
        if not self.confirm_close():
            event.ignore()

            
    def confirm_close(self):
        """ Displays a confirmation dialog if currently creating container 
            :returns: The users decision or True if no create process running
            :rtype: bool
        """
        if self.is_creating_countainer:
            message = _('Currently creating new container!\nDo you really want to quit?')
            mb = QMessageBox(QMessageBox.Question, '', message, QMessageBox.Ok | QMessageBox.Cancel, self)
            mb.setButtonText(QMessageBox.Ok, _('Quit'))
            return mb.exec_() == QMessageBox.Ok
        else:
            return True


    def on_switchpage_event(self, index):
        """ Event handler for tab switch: change text on OK button (Unlock/Create) """
        new_ok_label = _('Unlock')
        if index == 1:#create
            if self.create_filesystem_type.currentText() == '':
                self.show_alert(_('No tools to format the filesystem found\n' + 
                                  'Please install, eg for Debian/Ubuntu\n' +
                                  '`apt-get install e2fslibs ntfs-3g`'))
            new_ok_label = _('Create')
        self.buttons.button(QDialogButtonBox.Ok).setText(new_ok_label)


    def on_select_file_clicked(self):
        """ Triggered by clicking the select button next to container file (unlock) """
        self.unlock_container_file.setText(QFileDialog.getOpenFileName(self,_('Please choose a container file'), os.getenv("HOME")))
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))


    def on_select_mountpoint_clicked(self):
        """ Triggered by clicking the select button next to mount point """
        self.unlock_mountpoint.setText(QFileDialog.getExistingDirectory(self, _('Please choose a folder as mountpoint'), os.getenv("HOME")))
        self.buttons.button(QDialogButtonBox.Ok).setText(_('Unlock'))


    def on_save_file_clicked(self):
        """ Triggered by clicking the select button next to container file (create) 
            The dialog does not allow overwriting existing files - to get this behaviour
            while using native dialogs the QFileDialog has to be reopened on overwrite.
            A bit weird but enables visual consistency with the other file choose dialogs
        """
        def_path = os.path.join(os.getenv("HOME"), _('new_container.bin'))
        
        while True:
            save_path = self.encode_qt_output(QFileDialog.getSaveFileName(self,
                                                                          _('Please create a container file'),
                                                                          def_path,
                                                                          options = QFileDialog.DontConfirmOverwrite))
            self.buttons.button(QDialogButtonBox.Ok).setText(_('Create'))
    
            if os.path.exists(save_path):
                self.show_alert(_('File already exists:\n{filename}\n\n' + 
                                  '<b>Please create container\n' +
                                  'as a new file!</b>').format(filename = save_path))
                def_path = os.path.join(os.path.basename(save_path), _('new_container.bin'))
            else:
                self.create_container_file.setText(save_path)
                break


    def display_progress_percent(self, location, size):
        """ Update value on the container creation progress bar
            :param location: The path of the container file currently being created
            :type location: str
            :param size: The final size the new container in KB
            :type size: int
        """
        try:
            new_value = int( os.path.getsize(location) / size * 100)
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
        except AttributeError:#py2: 'QString' object has no attribute strip
            return unicode(qstring_or_str.trimmed().toUtf8(), encoding="UTF-8")
        

    def show_info(self, message, title):
        """ Helper to show info message 
            :param message: The message that gets displayed in a modal dialog
            :type message: str/unicode
            :param title: Displayed in the dialogs titlebar
            :type title: str/unicode
        """
        self.show_message(message, title, QMessageBox.Information)


    def show_alert(self, message):
        """ Helper to show error message
            :param message: The message that gets displayed in a modal dialog
            :type message: str/unicode
        """
        if message != '':
            self.show_message(message, _('Error'), QMessageBox.Warning)


    def show_message(self, message, title, message_type):
        """ Generic helper to show message
            :param message: The message that gets displayed in a modal dialog
            :type message: str/unicode
            :param title: Displayed in the dialogs titlebar
            :type title: str/unicode
            :param message_type: Type of message box to be used
            :type message_type: :class:`QMessageBox.Icon`
        """
        if message != '':
            mb = QMessageBox(message_type, title, message, QMessageBox.Ok, self)
            mb.exec_()
            

    def show_help_create(self):
        """ Triggered by clicking the help button (create tab) """
        message = _('''<b>Create a new encrypted LUKS container</b>:

Enter the path of the <b>new container file</b> in the textbox
or click the button for a graphical create file dialog.

The <b>device name</b> will be used to identify
the unlocked container. It can be any name
up to 16 characters, as long as it is unique.

Enter the <b>size</b> of the container in GB or MB.

The choice of <b>filesystem</b> is mostly relevant, if you 
want to access your encrypted data from MS Windows as well
(otherwise just use the default)

ext4 -> supported by all recent GNU/Linux distributions (default)
ext2 -> older GNU/Linux filesystem (standard until ~2009)
ntfs -> standard MS Windows filesystem, encrypted data
        can be accessed with BOTH Linux and Windows
        (use `FreeOFTE` or `doxbox` on Windows)

Since access permissions cannot be mapped
from ntfs to Linux, access to ntfs devices
is usually not restricted -> take care 
when using unlocked ntfs devices in a multiuser environment!

For more information, visit
<a href="{project_url}">{project_url}</a>
''').format(project_url=PROJECT_URL)
        self.show_info(message, _('Help'))


    def show_help_unlock(self):
        """ Triggered by clicking the help button (unlock tab) """
        message = _('''<b>Unlock an encrypted container file</b>:
        
Select the encrypted <b>container file</b>
by clicking the button next to the textbox.
Supports LUKS and Truecrypt container!

The <b>device name</b> will be used
to identify the unlocked container.
It can be any name up to 16 characters, as long as it is unique.
-> you can't give two unlocked containers the same name

The last argument is optional. The <b>mount point</b> is
the folder, where you can access the files inside the container
after unlocking.
If automatic mounting is configured on your system,
explicitly setting a mountpoint is usually not needed
(but still possible).

For more information, visit
<a href="{project_url}">{project_url}</a>
''').format(project_url=PROJECT_URL)
        self.show_info(message, _('Help'))