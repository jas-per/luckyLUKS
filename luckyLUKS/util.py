"""
Helper to establish a root-worker process and ipc handler.

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
import os
import select
import fcntl
import subprocess
import sys
import json
from PyQt4.QtCore import QThread, QEvent
from PyQt4.QtGui import QApplication


class SudoException(Exception):
    """ Errors while establishing a worker process with elevated privileges using sudo"""
    pass


class UserInputError(Exception):
    """ Used to handle problems arising from unsuitable user input """
    pass


def spawn_worker(passwordUI):
    """ Init worker subprocess with sudo && setup ipc handler
        :param passwordUI: A UI dialog that lets the user enter the password
        :type passwordUI: :class:`unlockUI.PasswordDialog`
        :returns: An initialized Python subprocess object running the worker process with elevated privileges
        :rtype: :class:`subprocess.Popen`
        :raises: SudoException
    """
    #using epoll to wait for feedback from sudo
    pipe_events = select.epoll()
    worker_process = _connect_to_sudo()
    pipe_events.register(worker_process.stdout.fileno(), select.EPOLLIN)
    sudo_prompt = '[sudo] password for ' + os.getenv('USER')
    incorrent_pw_entered = False
    try:
        while True:
            __, event = pipe_events.poll()[0]#blocking
            if event & select.EPOLLIN:
                #sudo process wrote to pipe
                msg = worker_process.stdout.read()
                if 'ESTABLISHED' in msg:
                    #Helper process initialized
                    #from here on all com-messages on the pipe will be terminated with newline -> switch back to blocking IO
                    fl = fcntl.fcntl(worker_process.stdout.fileno(), fcntl.F_GETFL)
                    fcntl.fcntl(worker_process.stdout.fileno(), fcntl.F_SETFL, fl & (~os.O_NONBLOCK))
                    break
                if 'Sorry, try again.' in msg:
                    incorrent_pw_entered = True
                if sudo_prompt in msg:
                    dlg_message = _('luckyLUKS needs administrative privileges.\nPlease enter your password:')
                    if incorrent_pw_entered:
                        dlg_message = _('Sorry, incorrect password.') + '\n' + dlg_message
                        incorrent_pw_entered = False
                    try:
                        worker_process.stdin.write(passwordUI(dlg_message).get_password()+'\n')
                        worker_process.stdin.flush()
                    except UserInputError:#user cancelled dlg -> quit without msg
                        raise SudoException()
                    
            elif event & select.EPOLLERR or event & select.EPOLLHUP:
                #react to error/hangup (msg has most likely been read before)
                if 'incorrect password attempts' in msg:
                    #max password attempts reached -> restart sudo process and continue
                    pipe_events.unregister(worker_process.stdout.fileno())
                    worker_process = _connect_to_sudo()
                    pipe_events.register(worker_process.stdout.fileno(), select.EPOLLIN)
                elif 'not allowed to execute' in msg:
                    raise SudoException(_('You are not allowed to execute this script with sudo\nPlease check your sudo configuration'))
                elif msg != '':
                    raise SudoException(msg)
                else:
                    raise IOError
                
    except IOError as ioe:
        raise SudoException(_('Communication with sudo process failed') + '\n' + str(ioe))
    finally:
        pipe_events.unregister(worker_process.stdout.fileno())
        pipe_events.close()
    
    return worker_process


def _connect_to_sudo():
    """ Calls worker with sudo and initializes pipes for communication 
        :returns : An initialized Python subprocess object with a non-blocking stdout, that waits for password input
        :rtype: :class:`subprocess.Popen`
    """
    #since output from sudo gets parsed, it needs to be run without localization
    #saving original language settings to pass to the worker process
    original_language = os.getenv("LANGUAGE")
    env_lang_cleared = os.environ.copy()
    env_lang_cleared['LANGUAGE'] = 'C'
    cmd = ['sudo', '-S', 'LANGUAGE='+original_language, sys.argv[0], '--ishelperprocess']
    sudo_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, universal_newlines=True, env=env_lang_cleared)
    #switch pipe to non-blocking IO
    fd = sudo_process.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    return sudo_process
        
        
class PipeMonitor(QThread):
    """ Establishes an asynchronous communication channel with the worker process:
        Since the worker executes only one task at a time a queue is not needed.
        After execute is called with command and callbacks further commands will get blocked
        until an answer from the worker arrives. The answer will get injected into the UI-loop
        -> the UI stays responsive, and thus has to disable buttons etc to prevent additional commands
    """
        
    def __init__(self, parent, worker_process, com_errorhandler):
        """ Daemon thread - because of blocking readline()
            :param worker_process: A Python subprocess object initialized with a privileged worker process
            :type worker_process: :class:`subprocess.Popen`
            :param com_errorhandler: The function to be called if communication with the worker fails.
            :type com_errorhandler: function that displays an errormessage and quits the program afterwards
        """
        super(PipeMonitor, self).__init__()
        self.daemon = True#forced kill needed 
        self.worker_out = worker_process.stdout
        self.worker_in = worker_process.stdin
        self.parent = parent
        self.com_errorhandler = com_errorhandler
        self.success_callback, self.error_callback = None, None


    def run(self):
        """ Listens on workers stdout and executes callbacks when answers arrive """
        while True:
            try:
                response = json.loads(self.worker_out.readline().strip(),encoding='utf-8')#blocks
                assert('type' in response and 'msg' in response)
                assert(self.success_callback is not None and self.error_callback is not None)#there should be somebody waiting for an answer!
                # valid response received
                if response['type'] == 'error':
                    QApplication.postEvent(self.parent, WorkerEvent(self.error_callback, response['msg']))
                else:
                    QApplication.postEvent(self.parent, WorkerEvent(self.success_callback, response['msg']))
                # reset callbacks   
                self.success_callback, self.error_callback = None, None
                
            except (IOError, ValueError, AssertionError) as communication_error:
                QApplication.postEvent(self.parent, WorkerEvent(self.com_errorhandler, _('Error in communication:\n{error}').format(error = communication_error.args[0])))
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
            assert('type' in command and 'msg' in command)#valid command obj?
            assert(self.success_callback is None and self.error_callback is None)#channel clear?
            self.success_callback = success_callback
            self.error_callback = error_callback
            self.worker_in.write(json.dumps(command) + '\n')
            self.worker_in.flush()
        except (IOError, AssertionError) as communication_error:
            QApplication.postEvent(self.parent, WorkerEvent(self.com_errorhandler, _('Error in communication:\n{error}').format(error = communication_error.args[0])))


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
    """ Checks if executable is present in path 
        :param executable: executable to search for
        :type executable: str
        :returns: True if executable found
        :rtype: bool
    """
    return any([os.path.exists(os.path.join(p, executable)) for p in os.environ["PATH"].split(os.pathsep)])
