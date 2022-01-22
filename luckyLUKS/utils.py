"""
Helper to establish a root-worker process and ipc handler.

luckyLUKS Copyright (c) 2014,2015,2022 Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""

import os
import select
import fcntl
import subprocess
import sys
import json
import traceback

from PyQt5.QtCore import QThread, QEvent
from PyQt5.QtWidgets import QApplication

from luckyLUKS.unlockUI import PasswordDialog, SudoDialog, UserInputError
from luckyLUKS.utilsUI import show_alert, show_info


class SudoException(Exception):
    """ Errors while establishing a worker process with elevated privileges using sudo"""


class WorkerMonitor(QThread):

    """ Establishes an asynchronous communication channel with the worker process:
        Since the worker executes only one task at a time queueing/sophisticated ipc are not needed.
        After execute is called with command and callbacks, further commands will get blocked
        until an answer from the worker arrives. The answer will get injected into the UI-loop
        -> the UI stays responsive, and thus has to disable buttons etc to prevent the user from
           sending additional commands
    """

    def __init__(self, parent):
        """ :param parent: The parent widget to be passed to modal dialogs
            :type parent: :class:`PyQt5.QtGui.QWidget`
            :raises: SudoException
        """
        super().__init__()
        self.parent = parent
        self.success_callback, self.error_callback = None, None
        self.modify_sudoers = False
        self.worker = None
        self._spawn_worker()

        if self.modify_sudoers:  # adding user/program to /etc/sudoers.d/ requested
            self.execute({'type': 'request', 'msg': 'authorize'}, None, None)
            response = json.loads(self.worker.stdout.readline().strip())  # blocks
            if response['type'] == 'error':
                show_alert(self.parent, response['msg'])
            else:
                message = _('Permanent `sudo` authorization for\n'
                            '{program}\n'
                            'has been successfully added for user `{username}` to \n'
                            '/etc/sudoers.d/lucky-luks\n').format(
                    program=os.path.abspath(sys.argv[0]),
                    username=os.getenv("USER"))
                show_info(self.parent, message, _('Success'))

    def _spawn_worker(self):
        """ Init worker subprocess with sudo && setup ipc handler
            :raises: SudoException
        """
        # using poll to wait for feedback from sudo
        self.pipe_events = select.poll()
        self._connect_to_sudo()
        dlg_message = _('luckyLUKS needs administrative privileges.\nPlease enter your password:')
        incorrent_pw_entered = False

        try:
            while True:
                __, event = self.pipe_events.poll()[0]  # blocking
                # sudo process wrote to pipe -> read message
                msg = self.worker.stdout.read()

                if event & select.POLLIN:
                    if 'ESTABLISHED' in msg:
                        # Helper process initialized, from here on all com-messages on the pipe
                        # will be terminated with newline -> switch back to blocking IO
                        fl = fcntl.fcntl(self.worker.stdout.fileno(), fcntl.F_GETFL)
                        fcntl.fcntl(self.worker.stdout.fileno(), fcntl.F_SETFL, fl & (~os.O_NONBLOCK))
                        break

                    if 'SUDO_PASSWD_PROMPT' in msg:
                        if incorrent_pw_entered:
                            dlg_msg = _('<b>Sorry, incorrect password.</b>\n') + dlg_message
                        else:
                            dlg_msg = dlg_message
                        self.worker.stdin.write(
                            SudoDialog(parent=self.parent,
                                       message=dlg_msg,
                                       toggle_function=lambda val: setattr(self, 'modify_sudoers', val)
                                       ).get_password() + '\n')
                        self.worker.stdin.flush()
                        incorrent_pw_entered = True

                    elif 'incorrect password attempts' in msg:
                        # max password attempts reached -> restart sudo process and continue
                        self._connect_to_sudo()

                    elif 'not allowed to execute' in msg or 'not in the sudoers file' in msg:
                        dlg_su_message = _('You are not allowed to execute this script with `sudo`.\n'
                                           'If you want to modify your `sudo` configuration,\n'
                                           'please enter the <b>root/administrator</b> password.\n')
                        incorrent_pw_entered = False
                        while True:
                            master, slave = os.openpty()  # su has to be run from a terminal
                            p = subprocess.Popen(
                                "su -c '" + sys.argv[0] + " --ishelperprocess --sudouser " + str(os.getuid()) + "'",
                                shell=True, stdin=slave, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                universal_newlines=True, close_fds=True
                            )
                            if incorrent_pw_entered:
                                dlg_msg = _('<b>Sorry, incorrect password.</b>\n') + dlg_su_message
                            else:
                                dlg_msg = dlg_su_message
                            os.write(master, (PasswordDialog(parent=self.parent,
                                                             message=dlg_msg
                                                             ).get_password() + '\n').encode('UTF-8'))
                            p.wait()

                            if p.returncode == 0:
                                show_info(
                                    self.parent,
                                    _('`sudo` configuration successfully modified, now\n'
                                      'you can use luckyLUKS with your user password.\n\n'
                                      'If you want to grant permanent administrative rights\n'
                                      'just tick the checkbox in the following dialog.\n'),
                                    _('Success')
                                )
                                incorrent_pw_entered = False
                                self._connect_to_sudo()
                                break
                            if p.returncode == 1:
                                incorrent_pw_entered = True
                            else:
                                # worker prints exceptions to stdout
                                # to keep them separated from 'su: Authentication failure'
                                raise SudoException(p.stdout.read())

                elif event & select.POLLERR or event & select.POLLHUP:
                    raise SudoException(msg)

        except SudoException:  # don't touch
            raise
        except UserInputError as e:  # user cancelled dlg -> quit without msg
            raise SudoException() from e
        except Exception as e:  # catch ANY other exception to show via gui
            raise SudoException(
                _('Communication with sudo process failed\n{error}')
                .format(error=''.join(traceback.format_exception(*sys.exc_info())))
            ) from e
        finally:
            try:
                self.pipe_events.unregister(self.worker.stdout.fileno())
            except KeyError:
                pass  # fd might already gone (IOError etc)
            del self.pipe_events

    def _connect_to_sudo(self):
        """ Calls worker process with sudo and initializes pipes for communication """
        if self.worker is not None:
            # disconnect event listener and wait for process termination
            self.pipe_events.unregister(self.worker.stdout.fileno())
            self.worker.wait()
        # since output from sudo gets parsed, it needs to be run without localization
        # saving original language settings / LC-environment to pass to the worker process
        original_language = os.getenv("LANGUAGE", "")
        env_lang_cleared = {prop: os.environ[prop] for prop in os.environ if prop[0:3] == 'LC_' or prop == 'LANG'}
        env_lang_cleared['LANGUAGE'] = 'C'
        cmd = ['sudo', '-S', '-p', 'SUDO_PASSWD_PROMPT',
               'LANGUAGE=' + original_language,
               os.path.abspath(sys.argv[0]),
               '--ishelperprocess']
        self.worker = subprocess.Popen(cmd,
                                       stdin=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       stdout=subprocess.PIPE, universal_newlines=True, env=env_lang_cleared)
        # switch pipe to non-blocking IO
        fd = self.worker.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        # connect event listener
        self.pipe_events.register(self.worker.stdout.fileno(), select.POLLIN)

    def run(self):
        """ Listens on workers stdout and executes callbacks when answers arrive """
        while True:
            try:
                buf = self.worker.stdout.readline()  # blocks
                if buf:  # check if worker output pipe closed
                    response = json.loads(buf.strip())
                else:
                    return
                assert('type' in response and 'msg' in response)
                # there should be somebody waiting for an answer!
                assert(self.success_callback is not None and self.error_callback is not None)
                # valid response received
                if response['type'] == 'error':
                    QApplication.postEvent(self.parent, WorkerEvent(self.error_callback, response['msg']))
                else:
                    QApplication.postEvent(self.parent, WorkerEvent(self.success_callback, response['msg']))
                # reset callbacks
                self.success_callback, self.error_callback = None, None

            except ValueError:
                # worker didn't return json -> probably crashed, show everything printed to stdout
                os.set_blocking(self.worker.stdout.fileno(), False)
                buf += str(self.worker.stdout.readlines())
                QApplication.postEvent(
                    self.parent,
                    WorkerEvent(callback=lambda msg: show_alert(self.parent, msg, critical=True),
                                response=_('Error in communication:\n{error}').format(error=_(buf)))
                )
                return

            except (IOError, AssertionError) as communication_error:
                QApplication.postEvent(
                    self.parent,
                    WorkerEvent(callback=lambda msg: show_alert(self.parent, msg, critical=True),
                                response=_('Error in communication:\n{error}').format(error=str(communication_error)))
                )
                return

    def execute(self, command, success_callback, error_callback):
        """ Writes command to workers stdin and sets callbacks for listener thread
            :param command: The function to be done by the worker is in command[`msg`]
                            the arguments are passed as named properties command[`device_name`] etc.
            :type command: dict
            :param success_callback: The function to be called if the worker finished successfully
            :type success_callback: function
            :param error_callback: The function to be called if the worker returns an error
            :type error_callback: function
        """
        try:
            # valid command obj?
            assert('type' in command and 'msg' in command)
            # channel clear? (no qeue neccessary for the backend process)
            assert(self.success_callback is None and self.error_callback is None)
            self.success_callback = success_callback
            self.error_callback = error_callback
            self.worker.stdin.write(json.dumps(command) + '\n')
            self.worker.stdin.flush()
        except (IOError, AssertionError) as communication_error:
            QApplication.postEvent(
                self.parent,
                WorkerEvent(callback=lambda msg: show_alert(self.parent, msg, critical=True),
                            response=_('Error in communication:\n{error}').format(error=str(communication_error)))
            )


class WorkerEvent(QEvent):

    """ thread-safe callback execution by raising
        these custom events in the main ui loop
    """
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, callback, response):
        """ A WorkerEvent encapsulates a function to be called in the main ui loop and its argument
            :param callback: The function to be called when the event gets processed
            :type callback: function
            :param response: Response message from the worker, passed as argument to the callback function
            :type response: str
        """
        QEvent.__init__(self, WorkerEvent.EVENT_TYPE)
        self.callback = callback
        self.response = response


class KeyfileCreator(QThread):

    """ Create a 1KByte key file with random data
        Worker thread to avoid blocking the ui loop
    """

    def __init__(self, parent, path):
        """ :param parent: The parent widget to be passed to modal dialogs
            :type parent: :class:`PyQt5.QtGui.QWidget`
            :param path: The designated key file path
            :type path: str
        """
        super().__init__()
        self.parent = parent
        self.path = path
        self.process = None

    def run(self):
        """ Spawns child process and passes a WorkerEvent to the main event loop when finished """
        try:
            output_file = str(self.path)
        except UnicodeEncodeError:
            output_file = self.path.encode('utf-8')  # assume uft8 encoding for shell - see worker
        # oflag=excl -> fail if the output file already exists
        cmd = ['dd', 'if=/dev/random', 'of=' + output_file, 'bs=1', 'count=1024', 'conv=excl']
        with open(os.devnull) as DEVNULL:
            self.process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=DEVNULL,
                                            universal_newlines=True, close_fds=True)
            __, errors = self.process.communicate()
        if self.process.returncode != 0:
            QApplication.postEvent(
                self.parent.parent(),
                WorkerEvent(callback=lambda msg: self.parent.display_create_failed(msg, stop_timer=True),
                            response=_('Error while creating key file:\n{error}').format(error=errors))
            )
        else:
            QApplication.postEvent(
                self.parent.parent(),
                WorkerEvent(callback=lambda msg: self.parent.on_keyfile_created(msg),
                            response=self.path)
            )

    def terminate(self):
        """ kill dd process """
        self.process.kill()


def is_installed(executable):
    """ Checks if executable is present
        Because the executables will be run by the privileged worker process,
        the usual root path gets added to the users environment path.
        Note: an executable at a custom user path will only be used by the worker process,
        if it is also present in the root path -> therefore this check might not be 100% accurate,
        but almost always sufficient. Checking the real root path would require calling
        the worker process, this way in rare cases the worker might throw an error on startup
        :param executable: executable to search for
        :type executable: str
        :returns: True if executable found
        :rtype: bool
    """
    return any([os.path.exists(os.path.join(p, executable))
                for p in os.environ["PATH"].split(os.pathsep) + ['/sbin', '/usr/sbin']
                ])
