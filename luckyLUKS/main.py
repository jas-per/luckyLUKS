"""
luckyLUKS is a GUI for creating and (un-)locking LUKS volumes from container files.
For more information visit: http://github.com/jas-per/luckyLUKS

Copyright (c) 2014,2015 Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""
from luckyLUKS import VERSION_STRING, PROJECT_URL
import os.path
import sys
import argparse
import types


def luckyLUKS(translation, *args, **kwargs):
    """ main entry point: initialize gettext, parse arguments and start either GUI or worker """
    try:
        # py3:
        import builtins
        translation.gettext_qt = types.MethodType(lambda self, msg: self.gettext(msg).replace('\n', '<br>'), translation)
        translation.ugettext_qt = types.MethodType(lambda self, msg: self.gettext(msg).replace('\n', '<br>'), translation)
        commandline_unicode_arg = lambda arg: arg
        argparse._ = _ = translation.gettext  # gettext for argsparse
        builtins.format_exception = str  # format exception message for gui
    except:
        # py2: explicit unicode for qt string translations, exception output and commandline args parsing
        import __builtin__ as builtins
        translation.gettext_qt = types.MethodType(lambda self, msg: self.gettext(msg).replace('\n', '<br>'), translation)
        translation.ugettext_qt = types.MethodType(lambda self, msg: self.ugettext(msg).replace('\n', '<br>'), translation)
        commandline_unicode_arg = lambda arg: arg.decode(sys.getfilesystemencoding())
        argparse._ = _ = translation.ugettext  # gettext for argsparse
        # format exception message for gui

        def format_exception(exception):
            try:
                return str(exception).decode('utf-8')
            except UnicodeEncodeError:
                return unicode(exception.message)
        builtins.format_exception = format_exception

    parser = argparse.ArgumentParser(description=_('GUI for creating and unlocking LUKS/TrueCrypt volumes from container files'),
                                     epilog=_('When called without any arguments a setup dialog will be shown before unlocking,\n'
                                              'where you can select containerfile and name, or create a new encrypted container.\n'
                                              'If both arguments are supplied, the unlock dialog will be shown directly.\n\n'
                                              'Example:\n'
                                              '  {executable} -c /usbstick/encrypted.bin -n mydata -m /home/user/enc\n\n'
                                              'If automatic mounting (eg udisks/polkit) is configured on your system,\n'
                                              'explicitly setting a mountpoint is usually not needed (but still possible)\n\n'
                                              'Homepage: {project_url}'
                                              ).format(executable=os.path.basename(sys.argv[0]),
                                                       project_url=PROJECT_URL),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    # L10n: used by argsparse to generate help output on the console (luckyLUKS --help)
    ap_usage = _('usage: ')
    # L10n: used by argsparse to generate help output on the console (luckyLUKS --help)
    ap_optargs = _('optional arguments')
    # L10n: used by argsparse to generate help output on the console (luckyLUKS --help)
    ap_helpmsg = _('show this help message and exit')
    # L10n: used by argsparse to generate help output on the console (luckyLUKS --help)
    ap_errmsg = _('%(prog)s: error: %(message)s\n')
    # L10n: used by argsparse to generate help output on the console (luckyLUKS --help)
    ap_unknown = _('unrecognized arguments: %s')

    # if argument not specified or empty set value to None
    # error messages will be shown by the GUI, not on the command line
    parser.add_argument('-c', dest='container', type=commandline_unicode_arg, nargs='?', metavar=_('PATH'),
                        help=_('Path to the encrypted container file'))
    parser.add_argument('-n', dest='name', type=commandline_unicode_arg, nargs='?', metavar=_('NAME'),
                        help=_('Choose a device name to identify the unlocked container'))
    parser.add_argument('-m', dest='mountpoint', type=commandline_unicode_arg, nargs='?', metavar=_('PATH'),
                        help=_('Where to mount the encrypted filesystem'))
    parser.add_argument('-v', '--version', action='version', version="luckyLUKS " + VERSION_STRING,
                        help=_("show program's version number and exit"))
    parser.add_argument('--ishelperprocess', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--sudouser', type=int, help=argparse.SUPPRESS)

    parsed_args = parser.parse_args()

    # worker will be created by calling the script again (but this time with su privileges)
    if parsed_args.ishelperprocess:
        # the backend process uses utf8 encoded str in py2
        builtins._ = translation.gettext_qt
        startWorker(parsed_args.sudouser)
    else:
        # unicode translations for the qt gui
        builtins._ = translation.ugettext_qt
        startUI(parsed_args)


def startUI(parsed_args):
    """ Import the required GUI elements and create main window """
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QLocale, QTranslator, QLibraryInfo
    except ImportError:  # py2 or py3 without pyqt5
        from PyQt4.QtGui import QApplication
        from PyQt4.QtCore import QLocale, QTranslator, QLibraryInfo
    from luckyLUKS.mainUI import MainWindow

    # l10n qt-gui elements
    qt_translator = QTranslator()
    qt_translator.load('qt_' + QLocale.system().name(), QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    application = QApplication(sys.argv)
    application.installTranslator(qt_translator)

    # start application
    main_win = MainWindow(parsed_args.name, parsed_args.container, parsed_args.mountpoint)
    # setup OK -> run event loop
    if main_win.is_initialized:
        sys.exit(application.exec_())
    else:
        sys.exit(0)


def startWorker(sudouser=None):
    """ Initialize worker process """
    from luckyLUKS import worker
    if sudouser is not None:
        # helper called with su to configure sudo
        if os.getuid() == 0 and os.getenv("SUDO_UID") is None:
            try:
                worker.WorkerHelper().modify_sudoers(sudouser)
                sys.exit(0)
            except worker.WorkerException as we:
                sys.stdout.write(format_exception(we))
                sys.exit(2)
        else:
            # deny giving other user userids sudo access to luckyLUKS if not called with su
            sys.exit(2)
    else:
        worker.run()
