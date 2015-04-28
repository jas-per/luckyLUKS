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
import os
import sys
import argparse


def luckyLUKS(translation, *args, **kwargs):
    """ main entry point: initialize gettext, parse arguments and start either GUI or worker """
    try:
        # py3:
        import builtins
        commandline_unicode_arg = lambda arg: arg
        argparse._ = builtins._ = translation.gettext
        builtins.format_exception = str  # format exception message for gui
    except:
        # py2: explicit unicode for string translations, exception output and commandline args parsing
        import __builtin__ as builtins
        commandline_unicode_arg = lambda arg: arg.decode(sys.getfilesystemencoding())
        argparse._ = builtins._ = translation.ugettext
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
    parser.add_argument('-k', dest='keyfile', type=commandline_unicode_arg, nargs='?', metavar=_('PATH'),
                        help=_('Path to an optional key file'))
    parser.add_argument('-v', '--version', action='version', version="luckyLUKS " + VERSION_STRING,
                        help=_("show program's version number and exit"))
    parser.add_argument('--ishelperprocess', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--sudouser', type=int, help=argparse.SUPPRESS)

    parsed_args = parser.parse_args()

    # worker will be created by calling the script again (but this time with su privileges)
    if parsed_args.ishelperprocess:
        # the backend process uses utf8 encoded str in py2
        builtins._ = translation.gettext
        startWorker(parsed_args.sudouser)
    else:
        startUI(parsed_args)


def startUI(parsed_args):
    """ Import the required GUI elements and create main window """
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
    
    from luckyLUKS.mainUI import MainWindow

    # start application
    gobject.threads_init()#needed for PyGObject up to 3.10.1
    # TODO: remove after testing
    settings = gtk.settings_get_default()
#     settings.props.gtk_button_images = True
#     settings.props.gtk_menu_images = True
    MainWindow(parsed_args.name, parsed_args.container,  parsed_args.keyfile, parsed_args.mountpoint)
    sys.exit(gtk.main())


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
