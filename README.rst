luckyLUKS
=========
luckyLUKS is a Linux GUI for creating and (un-)locking encrypted volumes from container files. Unlocked containers leave an icon in the systray as a reminder to close them eventually ;) Supports cryptsetup/LUKS and Truecrypt container files.

luckyLUKS was brought to life to offer an equivalent to the Windows TrueCrypt program. Although most Linux distributions provide excellent support for encrypted partitions these days - you can choose to run from a completely encrypted hardrive on installation with one or two clicks - the situation with encrypted containers is not that great. An encrypted container is basically a large file which encapsulates an encrypted partition - this approach has some advantages, especially for casual computer users:

- No need to deal with partition table wizardry when creating an encrypted container, you basically create a file on a harddrive, it doesn't matter if its an internal one or an external usbstick etc..
- Backup is straightforward as well, just copy the file somewhere else - done! No need to backup your precious data unencrypted
- You can easily add some encrypted private data to an unencrypted external harddrive you want to share with friends or take with you while travelling
- Lots of users are already quite familiar with all this, because their first touch with data encryption has been TrueCrypt which uses the encrypted container approach

luckyLUKS follows a keep-it-simple philosophy that aims to keep users from shooting themselves in the foot and might be a bit too simple for power users - please use `ZuluCrypt <https://code.google.com/p/zulucrypt/>`_ and/or `cryptsetup <https://code.google.com/p/cryptsetup/>`_/`tcplay <https://github.com/bwalex/tc-play>`_ on the command line if you need special options when creating new containers. On the other hand, to unlock existing containers luckyLUKS offers all you need and the possibility to create a shortcut to a container in your start menu or on the desktop. From the shortcut its just one click and you can enter your password to unlock the container. To get a better understanding of the technical details please see the FAQ at the end of this page, for a first impression watch this screencast:

.. image:: screencast.gif
    :align: center
    :alt: screencast of luckyLUKS

Installation
============

For Ubuntu and derivates just use this ppa::

    > sudo add-apt-repository ppa:jas-per/lucky-luks
    > sudo apt-get update && sudo apt-get upgrade
    > sudo apt-get install python-luckyLUKS

For other debian based distributions download this debian package and install manually:

`python-luckyluks_0.9.7-1_all.deb <https://github.com/jas-per/luckyLUKS/releases/download/v0.9.7/python-luckyluks_0.9.7-1_all.deb>`_

On other distriubution you can use the following zip-packaged python file:

`luckyLUKS-0.9.7 <https://github.com/jas-per/luckyLUKS/releases/download/v0.9.7/luckyLUKS-0.9.7>`_

This file contains all resources and can be executed directly by the python intepreter. Place in /usr/bin and change ownership to root for security::

    > sudo mv luckyLUKS-0.9.7 /usr/bin/
    > sudo chown root:root /usr/bin/luckyLUKS-0.9.7
    > sudo chmod 755 /usr/bin/luckyLUKS-0.9.7

Then start with 'luckyLUKS-0.9.7' on the command line and create a desktop shortcut manually.

Dependencies
------------

To run luckyLUKS, make sure you have the following installed:

- `cryptsetup`
- `sudo`
- `python-qt4`
- `tcplay` (if you want to use TrueCrypt containers)

When using the ubuntu-ppa or debian package, these will get installed automatically, if you use the zip-package please install the dependencies manually with your distributions repository tools.


FAQ
===

TODO

Bugs
====

Please report all bugs on the github issue tracker. Since this is a GUI tool, the most important information is the exact name of the distribution you're using including the version/year. I will try to make sure luckyLUKS works with any recent distribution (from ~2012 on), providing the exact name and version will help reproducing bugs on a virtual machine a lot.


Translations
============

TODO

