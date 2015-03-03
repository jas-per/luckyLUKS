"""
Helper to establish a root-worker process and ipc handler.

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
import os
import select
import fcntl
import subprocess
import sys
import json
import traceback

try:
    from PyQt5.QtCore import QThread, QEvent
    from PyQt5.QtWidgets import QApplication
except ImportError:  # py2 or py3 without pyqt5
    from PyQt4.QtCore import QThread, QEvent
    from PyQt4.QtWidgets import QApplication

from luckyLUKS.unlockUI import PasswordDialog, SudoDialog, UserInputError
from luckyLUKS.utilsUI import show_alert, show_info


class SudoException(Exception):

    """ Errors while establishing a worker process with elevated privileges using sudo"""
    pass


class WorkerMonitor(QThread):

    """ Establishes an asynchronous communication channel with the worker process:
        Since the worker executes only one task at a time queueing/sophisticated ipc are not needed.
        After execute is called with command and callbacks, further commands will get blocked
        until an answer from the worker arrives. The answer will get injected into the UI-loop
        -> the UI stays responsive, and thus has to disable buttons etc to prevent the user from
           sending additional commands
    """

    def __init__(self, parent):
        """ Daemon thread - because of blocking readline()
            :param parent: The parent widget to be passed to modal dialogs
            :type parent: :class:`PyQt4.QtGui.QWidget`
            :raises: SudoException
        """
        super(WorkerMonitor, self).__init__()
        self.daemon = True  # forced kill needed
        self.parent = parent
        self.success_callback, self.error_callback = None, None
        self.modify_sudoers = False
        self.worker = None
        self._spawn_worker()

        if self.modify_sudoers:  # adding user/program to /etc/sudoers.d/ requested
            self.execute({'type': 'request', 'msg': 'authorize'}, None, None)
            response = json.loads(self.worker.stdout.readline().strip(), encoding='utf-8')  # blocks
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
        sudo_prompt = '[sudo] password for ' + os.getenv('USER')
        dlg_message = _('luckyLUKS needs administrative privileges.\nPlease enter your password:')
        incorrent_pw_entered = False

        try:
            while True:
                __, event = self.pipe_events.poll()[0]  # blocking
                # sudo process wrote to pipe -> read message
                msg = self.worker.stdout.read()

                if event & select.POLLIN:
                    if 'ESTABLISHED' in msg:
                        # Helper process initialized
                        # from here on all com-messages on the pipe will be terminated with newline -> switch back to blocking IO
                        fl = fcntl.fcntl(self.worker.stdout.fileno(), fcntl.F_GETFL)
                        fcntl.fcntl(self.worker.stdout.fileno(), fcntl.F_SETFL, fl & (~os.O_NONBLOCK))
                        break

                    elif sudo_prompt in msg:
                        self.worker.stdin.write(SudoDialog(parent=self.parent,
                                                           message=_('<b>Sorry, incorrect password.</b>\n') + dlg_message if incorrent_pw_entered else dlg_message,
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
                            p = subprocess.Popen("su -c '" + sys.argv[0] + " --ishelperprocess --sudouser " + str(os.getuid()) + "'", shell=True, stdin=slave, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, close_fds=True)
                            os.write(master, PasswordDialog(parent=self.parent,
                                                            message=_('<b>Sorry, incorrect password.</b>\n') + dlg_su_message if incorrent_pw_entered else dlg_su_message
                                                            ).get_password() + '\n')
                            p.wait()

                            if p.returncode == 0:
                                show_info(self.parent, _('`sudo` configuration successfully modified, now\n'
                                                         'you can use luckyLUKS with your user password.\n\n'
                                                         'If you want to grant permanent administrative rights\n'
                                                         'just tick the checkbox in the following dialog.\n'), _('Success'))
                                incorrent_pw_entered = False
                                self._connect_to_sudo()
                                break
                            elif p.returncode == 1:
                                incorrent_pw_entered = True
                            else:
                                raise SudoException(p.stdout.read())  # worker prints exceptions to stdout to keep them seperated from su: Authentication failure

                elif event & select.POLLERR or event & select.POLLHUP:
                    raise SudoException(msg)

        except SudoException:  # don't touch
            raise
        except UserInputError:  # user cancelled dlg -> quit without msg
            raise SudoException()
        except Exception:  # catch ANY other exception to show via gui
            raise SudoException(_('Communication with sudo process failed\n{error}').format(error=''.join(traceback.format_exception(*sys.exc_info()))))
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
        # saving original language settings to pass to the worker process
        # TODO: this way, sanitizing env is handled by sudo - strip/recreate env here instead of copy?
        original_language = os.getenv("LANGUAGE", "")
        env_lang_cleared = os.environ.copy()
        env_lang_cleared['LANGUAGE'] = 'C'
        cmd = ['sudo', '-S', 'LANGUAGE=' + original_language, sys.argv[0], '--ishelperprocess']
        self.worker = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, env=env_lang_cleared)
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
                    response = json.loads(buf.strip(), encoding='utf-8')
                else:
                    return
                assert('type' in response and 'msg' in response)
                assert(self.success_callback is not None and self.error_callback is not None)  # there should be somebody waiting for an answer!
                # valid response received
                if response['type'] == 'error':
                    QApplication.postEvent(self.parent, WorkerEvent(self.error_callback, response['msg']))
                else:
                    QApplication.postEvent(self.parent, WorkerEvent(self.success_callback, response['msg']))
                # reset callbacks
                self.success_callback, self.error_callback = None, None

            except (IOError, ValueError, AssertionError) as communication_error:
                QApplication.postEvent(self.parent, WorkerEvent(callback=lambda msg: show_alert(self.parent, msg, critical=True),
                                                                response=_('Error in communication:\n{error}').format(error=format_exception(communication_error))))
                return

    def execute(self, command, success_callback, error_callback):
        """ Writes command to workers stdin and sets callbacks for listener thread
            :param command: The function to be done by the worker is in command[`msg`] the arguments are passed as named properties command[`device_name`] etc.
            :type command: dict
            :param success_callback: The function to be called if the worker finished successfully
            :type success_callback: function
            :param error_callback: The function to be called if the worker returns an error
            :type error_callback: function
        """
        try:
            assert('type' in command and 'msg' in command)  # valid command obj?
            assert(self.success_callback is None and self.error_callback is None)  # channel clear? (no qeue neccessary for the backend process)
            self.success_callback = success_callback
            self.error_callback = error_callback
            self.worker.stdin.write(json.dumps(command) + '\n')
            self.worker.stdin.flush()
        except (IOError, AssertionError) as communication_error:
            QApplication.postEvent(self.parent, WorkerEvent(callback=lambda msg: show_alert(self.parent, msg, critical=True),
                                                            response=_('Error in communication:\n{error}').format(error=format_exception(communication_error))))


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


def is_installed(executable):
    """ Checks if executable is present
        Because the executables will be run by the priviledged worker process,
        the usual root path gets added to the users environment path.
        :param executable: executable to search for
        :type executable: str
        :returns: True if executable found
        :rtype: bool
    """
    return any([os.path.exists(os.path.join(p, executable)) for p in os.environ["PATH"].split(os.pathsep) + ['/sbin', '/usr/sbin']])
