"""
luckyLUKS is a GTK-GUI for creating and (un-)locking LUKS volumes from container files.
For more information visit: http://github.com/jas-per/luckyLUKS

Copyright (c) 2014, Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details. <http://www.gnu.org/licenses/>
"""
import locale
import pkgutil
import io
from gettext import GNUTranslations, NullTranslations

from luckyLUKS import main

"""
This is the entry point, when run from the zip-file package.
To access resources inside the zip file, pkgutil.get_data() has to be used.
Because of this, gettext will be initialized here,
#if a .mo file for the users locale can be found inside the zip
"""
if __name__ == '__main__':
    
    locale.setlocale(locale.LC_ALL, '')
    loc, enc = locale.getlocale(locale.LC_MESSAGES)
    l10n_resource = None
    
    # try to find the corresponding gettext file (*.mo) for the users locale in the zip file
    if loc != 'C':
        try:
            l10n_resource = pkgutil.get_data('luckyLUKS', 'i18n/{0}/LC_MESSAGES/luckyLUKS.mo'.format(loc))
        except IOError:
            if '_' in loc:
                try:
                    l10n_resource = pkgutil.get_data('luckyLUKS', 'i18n/{0}/LC_MESSAGES/luckyLUKS.mo'.format(loc.split('_')[0]))
                except IOError:
                    pass

    if l10n_resource is None:                
        translation = NullTranslations()
    else:
        translation = GNUTranslations(io.BytesIO(l10n_resource))  
    
    main.luckyLUKS(translation)
