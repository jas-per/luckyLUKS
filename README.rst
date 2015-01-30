luckyLUKS
=========
luckyLUKS is a Linux GUI for creating and (un-)locking encrypted volumes from container files. Unlocked containers leave an icon in the systray as a reminder to close them eventually ;) Supports cryptsetup/LUKS and Truecrypt container files.

luckyLUKS was brought to life to offer an equivalent to the Windows TrueCrypt program. Although most Linux distributions provide excellent support for encrypted partitions these days - you can choose to run from a completely encrypted hardrive on installation with one or two clicks - the situation with encrypted containers is not that great. An encrypted container is basically a large file which encapsulates an encrypted partition - this approach has some advantages, especially for casual computer users:

- No need to deal with partition table wizardry when creating an encrypted container, you basically create a file on a harddrive, it doesn't matter if its an internal one or an external usbstick etc..
- Backup is straightforward as well, just copy the file somewhere else - done! No need to backup your precious data unencrypted
- You can easily add some encrypted private data to an unencrypted external harddrive you want to share with friends or take with you while travelling
- Lots of users are already quite familiar with all this, because their first touch with data encryption has been TrueCrypt which uses the encrypted container approach

The major technical drawback is a bit of overhead while accessing data inside an encrypted container, because the computer has to work on two filesystems on top of each other (although you probably won't notice the difference on a reasonably fast computer). The much bigger problem for users right now is the lack of a graphical interface for using encrypted containers in almost every Linux distribution. Although you can run TrueCrypt on Linux, it's not an ideal solution for various reasons and almost certainly won't make it into default installations because of licencing issues. There is another program called ZuluCrypt which offers a graphical interface to all the options of the underlying command line tool called cryptsetup. I'd definitely recommend ZuluCrypt for power users, but for technical reasons this program probably won't find its way into default Linux installations as well.

luckyLUKS follows a keep-it-simple philosophy that aims to keep users from shooting themselves in the foot and might be a bit too simple for power users - please use ZuluCrypt and/or cryptsetup/tcplay on the command line if you need special options when creating new containers. On the other hand, to unlock existing containers luckyLUKS offers all you need and the possibility to create a shortcut to a container in your start menu or on the desktop. From the shortcut its just one click and you can enter your password to unlock the container. To get a better understanding of the technical details please see the FAQ at the end of this page.


Installation
============

For Ubuntu and derivates just use this ppa::

    > sudo add-apt-repository ppa:jas-per/lucky-luks
    > sudo apt-get update && sudo apt-get upgrade
    > sudo apt-get install python-luckyLUKS

For other debian based distributions download this debian package and install manually:


`python-luckyluks_0.9.6-1_all.deb <https://launchpad.net/~jas-per/+archive/ubuntu/lucky-luks/+files/python-luckyluks_0.9.6-1_all.deb>`_

make sure you have the following installed:
`cryptsetup`, `sudo` and `python-qt4`

add `tcplay` if you want to use TrueCrypt containers


TODO: manual install


FAQ
===

TODO

Translations
============

TODO

