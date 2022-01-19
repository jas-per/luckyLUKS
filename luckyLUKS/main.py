"""
luckyLUKS is a GUI for creating and (un-)locking LUKS volumes from container files.
For more information visit: http://github.com/jas-per/luckyLUKS

Copyright (c) 2014,2015,2022 Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""

import os.path
import sys
import argparse
import types
import builtins
from luckyLUKS import VERSION_STRING, PROJECT_URL


def luckyLUKS(translation, *args, **kwargs):
    """ main entry point: initialize gettext, parse arguments and start either GUI or worker """

    translation.gettext_qt = types.MethodType(lambda self, msg: self.gettext(msg).replace('\n', '<br>'), translation)
    argparse._ = _ = translation.gettext  # gettext for argsparse

    parser = argparse.ArgumentParser(
        description=_('GUI for creating and unlocking LUKS/TrueCrypt volumes from container files'),
        epilog=_('When called without any arguments a setup dialog will be shown before unlocking,\n'
                 'where you can select containerfile and name, or create a new encrypted container.\n'
                 'If both arguments are supplied, the unlock dialog will be shown directly.\n\n'
                 'Example:\n'
                 '  {executable} -c /usbstick/encrypted.bin -n mydata -m /home/user/enc\n\n'
                 'If automatic mounting (eg udisks/polkit) is configured on your system,\n'
                 'explicitly setting a mountpoint is usually not needed (but still possible)\n\n'
                 'Homepage: {project_url}').format(executable=os.path.basename(sys.argv[0]),
                                                   project_url=PROJECT_URL),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

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
    parser.add_argument('-c', dest='container', nargs='?', metavar=_('PATH'),
                        help=_('Path to the encrypted container file'))
    parser.add_argument('-n', dest='name', nargs='?', metavar=_('NAME'),
                        help=_('Choose a device name to identify the unlocked container'))
    parser.add_argument('-m', dest='mountpoint', nargs='?', metavar=_('PATH'),
                        help=_('Where to mount the encrypted filesystem'))
    parser.add_argument('-k', dest='keyfile', nargs='?', metavar=_('PATH'),
                        help=_('Path to an optional key file'))
    parser.add_argument('-v', '--version', action='version', version="luckyLUKS " + VERSION_STRING,
                        help=_("show program's version number and exit"))
    parser.add_argument('--ishelperprocess', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--sudouser', type=int, help=argparse.SUPPRESS)

    parsed_args = parser.parse_args()

    # worker will be created by calling the script again (but this time with su privileges)
    builtins._ = translation.gettext_qt
    if parsed_args.ishelperprocess:
        startWorker(parsed_args.sudouser)
    else:
        startUI(parsed_args)


def startUI(parsed_args):
    """ Import the required GUI elements and create main window """
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QLocale, QTranslator, QLibraryInfo
    from luckyLUKS.mainUI import MainWindow

    # l10n qt-gui elements
    qt_translator = QTranslator()
    qt_translator.load('qt_' + QLocale.system().name(), QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    application = QApplication(sys.argv)
    application.installTranslator(qt_translator)

    # start application
    main_win = MainWindow(parsed_args.name, parsed_args.container, parsed_args.keyfile, parsed_args.mountpoint)
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
                sys.stdout.write(str(we))
                sys.exit(2)
        else:
            # deny giving other user userids sudo access to luckyLUKS if not called with su
            sys.exit(2)
    else:
        worker.run()
