"""
UI helper/classes for luckyLUKS

luckyLUKS Copyright (c) 2014,2015 Jasper van Hoorn (muzius@gmail.com)
QExpander Copyright (c) 2012 Canonical Ltd.
modified, originally from https://launchpad.net/ubuntu-sso-client (GPL v3+)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""
import sys
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

from luckyLUKS import VERSION_STRING, PROJECT_URL


class HelpDialog(gtk.Dialog):
    
    """ Displays a help dialog that consists of
        a help icon and a header/title
        a main text
        an iniatially hidden secondary help text that can be expanded
        followed by a footer
    """
 
    def __init__(self, parent, header_text, basic_text, advanced_topics):
        """ Create a new instance
            :param parent: The parent window/dialog used to enable modal behaviour
            :type parent: :class:`gtk.Widget`
            :param header_text: Displayed in the top of the dialog next to the help icon
            :type header_text: str/unicode
            :param basic_text: Displayed in the middle of the help dialog
            :type basic_text: str/unicode
            :param advanced_topics: Displayed below the basic text, initially only the header is shown, the content gets hidden
            :type advanced_topics: Array of dicts with str/unicode head and text properties
        """
        super(HelpDialog, self).__init__( _('Help'), parent,
                                        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                        (gtk.STOCK_OK, gtk.RESPONSE_OK)
                                    )
        self.set_resizable(False)
        self.set_border_width(10)
        self.get_content_area().set_spacing(10)

        # icon and header
        header_label = gtk.Label()
        header_label.set_markup(header_text)
        header_box = gtk.HBox(spacing=10)
        header_box.pack_start(gtk.image_new_from_stock(gtk.STOCK_HELP, gtk.ICON_SIZE_DIALOG), False, False, 10)
        header_box.pack_start(header_label, True, True, 0)
        self.get_content_area().add(header_box)
        # main help text
        basic_help = gtk.Label()
        basic_help.set_markup(basic_text)
        basic_help.set_line_wrap(True)
        basic_help.set_width_chars(80)
        basic_help.set_justify(gtk.JUSTIFY_FILL)
        self.get_content_area().add(basic_help)
        # advanced help
        advanced = gtk.Alignment()
        advanced_label = gtk.Label()
        advanced_label.set_markup('<b>' + _('Advanced Topics:') + '</b>')
        advanced.add(advanced_label)
        self.get_content_area().add(advanced)
        self._advanced_topics = []
        
        for topic in advanced_topics:
            expander = gtk.Expander()
            expander.set_label(topic['head'])
            child = gtk.Alignment()
            child.set_padding(10,10,0,0)
            text = gtk.Label()
            text.set_markup(topic['text'])
            text.set_line_wrap(True)
            text.set_width_chars(80)
            text.set_justify(gtk.JUSTIFY_FILL)
            child.add(text)
            expander.add(child)
            self.get_content_area().add(expander)
            expander.connect('notify::expanded', self._on_topic_clicked)
            self._advanced_topics += [expander]

        # footer
        hl = gtk.HSeparator()
        self.get_content_area().add(hl)
        footer = gtk.Alignment()
        footer_label = gtk.Label()
        footer_label.set_markup(_('luckyLUKS version {version}\n'
                                  'For more information, visit\n'
                                  '<a href="{project_url}">{project_url}</a>').format(version=VERSION_STRING,
                                                                                      project_url=PROJECT_URL))
        footer.add(footer_label)
        self.get_content_area().add(footer)
        
        self.show_all()
        
    def _on_topic_clicked(self, topic_clicked, params):
        if topic_clicked.get_expanded():
            for topic in self._advanced_topics:
                if not topic == topic_clicked:
                    topic.set_expanded(False)


def show_info(parent, message, title=''):
    """ Helper to show info message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`gtk.Widget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param title: Displayed in the dialogs titlebar
        :type title: str/unicode
    """
    show_message(parent, message, title, gtk.MESSAGE_INFO)

def show_alert(parent, message, critical=False):
    """ Helper to show error message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`gtk.Widget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param critical: If critical, quit application (default=False)
        :type critical: bool
    """
    show_message(parent, message, _('Error'), gtk.MESSAGE_ERROR if critical else gtk.MESSAGE_WARNING)
    if critical:
        sys.exit()

def show_message(parent, message, title, message_type):
    """ Generic helper to show message
        :param parent: The parent widget to be passed to the modal dialog
        :type parent: :class:`gtk.Widget`
        :param message: The message that gets displayed in a modal dialog
        :type message: str/unicode
        :param title: Displayed in the dialogs titlebar
        :type title: str/unicode
        :param message_type: Type of message box to be used
        :type message_type: :class:`QMessageBox.Icon`
    """
    if message != '':
        md = gtk.MessageDialog(parent,
          gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
          message_type, 
          gtk.BUTTONS_OK)
        md.set_title(title)
        md.set_markup(message)
        md.get_widget_for_response(gtk.RESPONSE_OK).grab_focus()
        md.run()
        md.destroy()
