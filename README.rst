luckyLUKS
=========
luckyLUKS is a Linux GUI for creating and (un-)locking encrypted volumes from container files. Unlocked containers leave an icon in the systray \
as a reminder to close them eventually ;) Supports cryptsetup/LUKS and Truecrypt container files.

luckyLUKS was brought to life to offer an equivalent to the Windows TrueCrypt application. Although most Linux distributions provide excellent support for \
encrypted partitions these days - you can choose to run from a completely encrypted harddrive on installation with one or two clicks - the situation with \
encrypted containers is not that great. An encrypted container is basically a large file which encapsulates an encrypted partition. This approach has some advantages, especially for casual computer users:

- No need to deal with partition table wizardry when creating an encrypted container, you basically create a file on a harddrive, it doesn't matter if its an internal one or an external usbstick etc..
- Backup is straightforward as well, just copy the file somewhere else - done! No need to backup your precious data unencrypted
- Share confidential information by copying the container file. Similar to gpg encrypted archives but easier to handle (unlock - view or modify data - lock again)
- You can easily add some encrypted private data to an unencrypted external harddrive you want to share with friends or take with you while travelling
- Lots of users are already quite familiar with all this, because their first touch with data encryption has been TrueCrypt which uses the encrypted container approach

luckyLUKS follows a keep-it-simple philosophy that aims to keep users from shooting themselves in the foot and might be a bit too simple for power users - \
please use `ZuluCrypt <https://mhogomchungu.github.io/zuluCrypt/>`_ and/or `cryptsetup <https://gitlab.com/cryptsetup/cryptsetup>`_/`tcplay <https://github.com/bwalex/tc-play>`_ on the command line \
if you need special options when creating new containers. On the other hand, to unlock existing containers luckyLUKS offers all you need and the possibility \
to create a shortcut to a container in your start menu or on the desktop. From the shortcut its just one click and you can enter your password to \
unlock the container. For technical details please see the FAQ at the end of this page. For a first impression:

.. image:: https://github.com/jas-per/luckyLUKS/blob/gh-pages/screencast.gif
    :align: center
    :alt: screencast of luckyLUKS

Installation
============

For Ubuntu and derivates just use this `ppa <https://launchpad.net/~jas-per/+archive/ubuntu/lucky-luks>`_::

    > sudo add-apt-repository ppa:jas-per/lucky-luks
    > sudo apt-get update && sudo apt-get upgrade
    > sudo apt-get install luckyluks

(For older Ubuntu LTS install :code:`python-luckyLUKS` or :code:`python3-luckyLUKS` still present in that ppa)

All Debian based distributions can use this debian package and install manually:

`luckyluks_2.0.0_all.deb <https://github.com/jas-per/luckyLUKS/releases/download/v2.0.0/luckyluks_2.0.0_all.deb>`_

On other distriubutions you can use the following zip-packaged python file:

`luckyLUKS-2.0.0 <https://github.com/jas-per/luckyLUKS/releases/download/v2.0.0/luckyLUKS-2.0.0>`_

This file contains all resources and can be executed directly by the python intepreter. Place in :code:`/usr/bin` and change ownership to root::

    > sudo mv luckyLUKS-2.0.0 /usr/bin/
    > sudo chown root:root /usr/bin/luckyLUKS-2.0.0
    > sudo chmod 755 /usr/bin/luckyLUKS-2.0.0

Then start with :code:`luckyLUKS-2.0.0` on the command line or create a desktop shortcut manually.

Dependencies
------------

To run luckyLUKS, make sure you have the following installed:

- :code:`python3`
- :code:`cryptsetup`
- :code:`sudo`
- :code:`python3-pyqt5`
- :code:`tcplay` (if you want to create TrueCrypt containers)

When using the ubuntu-ppa these will get installed automatically, if you use the deb-/zip-package \
please install the dependencies manually with your distributions repository tools.

Desktop environments / distributions
------------------------------------

luckyLUKS gets tested with the major desktop environments:

- :code:`gnome` (needs extension for `tray icons <https://extensions.gnome.org/extension/615/appindicator-support/>`_)
- :code:`kde`
- :code:`ubuntu gnome`
- :code:`xfce`
- :code:`cinnamon`
- :code:`mate`
- :code:`lxqt` (known minor `issue <https://github.com/lxqt/lxqt-panel/issues/1705>`_)

There are also some distribution specifics with Debian:

- since debian doesn't rely on sudo you have to manually add your user to the sudo group::

    > su
    > usermod -aG sudo USERNAME
    
- dev-mapper is not configured to do automatic mounts on some desktop environments::

    please use the 'mount point' option in luckyLUKS

Using luckyLUKS with a wayland-based display server / compositor instead of Xorg is possible with `gnome` and `kde` \
and for security reasons this is very much recommended! There is still some work left to get wayland running smooth though, \
so check usability for yourself - things like gaming, input drivers, screen recording and also tray icon functionality \
might stop you from using a wayland compositor yet.


FAQ
===

luckyLUKS is basically a GUI wrapper for two command line tools: `cryptsetup` and `tcplay`. The cryptsetup project has an excellent `FAQ <https://gitlab.com/cryptsetup/cryptsetup/wikis/FrequentlyAskedQuestions>`_ that explains the underlying cryptography and security in great detail. \
If you want to know more e.g. about choosing a secure password or further protecting your computer, please read the cryptsetup FAQ first. The following \
information mainly refers to questions specific to encrypted containers and luckyLUKS as a graphical interface to cryptsetup and tcplay.

Backup
------

There is a whole chapter in the cryptsetup FAQ dealing with backup details. This is because cryptsetup is normally used for encrypted partitions, which complicates things a bit. Since luckyLUKS uses encrypted containers, backup is rather straightforward - just copy the whole container and you're done. \
By copying you technically create a clone of the encrypted LUKS container - see section 6.15 in the cryptsetup `FAQ <https://gitlab.com/cryptsetup/cryptsetup/wikis/FrequentlyAskedQuestions#6-backup-and-data-recovery>`_ in case you would like to change your passphrase later on.

Key files
---------

A key file can be used to allow access to an encrypted container instead of a password. Using a key file resembles unlocking a door with a key in the real world - anyone with access to the key file can open your encrypted container. Make sure to store it at a protected location. \
Its okay to store it on your computer if you are using a digital keystore or an already encrypted harddrive that you unlock on startup with a password. Having the key file on a `small USB drive <https://www.google.com/search?q=keychain+usb+drive&tbm=isch>`_ attached to your real chain of keys \
would be an option as well. Since you don't have to enter a password, using a key file can be a convenient way to access your encrypted container. Just make sure you don't lose the key (file) - backup to a safe location separate from the encrypted container. Printing the raw data \
(use a hex-editor/viewer) to paper is fine as a last resort as well.

Although basically any file could be used as a key file, a file with predictable content leads to similar problems as using weak passwords. Audio files or pictures are a good choice. If unsure use the 'create key file' function in luckyLUKS to generate a small key file filled with random data.

With LUKS it is also possible to use both, a passphrase and a keyfile. LUKS uses a concept called 'keyslots' that enables up to 8 keys to be used exchangeably to unlock a container. You could use a keyfile to unlock a container on an external drive when using your own computer with an already encrypted system, \
and a passphrase to open the same container on a different computer or in case you lost the keyfile. Because it might be a bit confusing for casual users, this option is not provided in the graphical interface of luckyLUKS. If you want to use it, you have to do the following once on the command line:

- generate a new keyfile with luckyLUKS
- open the container with luckyLUKS
- check which loopback device is used: :code:`sudo losetup -a`
- view the LUKS keyslots of this container: :code:`sudo cryptsetup luksDump /dev/loopX`
- add the keyfile to the keyslots: :code:`sudo cryptsetup luksAddKey /dev/loopX /PATH/TO/KEYFILE`
- view the LUKS keyslots again and you will see another keyslot in use: :code:`sudo cryptsetup luksDump /dev/loopX`

After you did this once, you can use the GUI of luckyLUKS, to open the container with either passphrase or keyfile and generate shortcuts for the startup menu as needed.

The TrueCrypt format offers another possibility when using keyfiles, where you have to provide both keyfile and password to unlock a container. While this provides a nice `two factor authentication <http://en.wikipedia.org/wiki/Two_factor_authentication>`_ it is also a more advanced approach \
that is beyond the scope of luckyLUKS - please use `ZuluCrypt <https://mhogomchungu.github.io/zuluCrypt/>`_ or the command line for this. And be aware that security through obscurity might not be the right approach for your privacy needs: a weak password combined with a keyfile \
is easily broken if the keyfile gets into the wrong hands.

Sudo Access
-----------

On Linux encrypted containers get mounted as loopback devices by using the device mapper infrastructure. Access to /dev/mapper is restricted to root for good reason: besides managing encrypted containers, the device mapper is also used by the Logical Volume Manager (LVM) and Software RAIDs for example. \
There have been `ideas <https://gitlab.com/cryptsetup/cryptsetup/issues/218>`_ on how to allow device-mapper access without root privileges but its complicated - the device mapper developers seem to prefer controlling loopback device mounts by integrating cryptsetup into udisks/dbus/udev/policykit/systemd. \
While this approach can enable fine grained access control in userspace, it also complicates things quite substantially - nowadays it might be possible to use encrypted containers this way, but decent documentation is hard to find.

So for now accessing the device mapper directly with administrative privileges is needed to use encrypted containers. Almost every Unix systems offers two ways to do this: setuid and sudo. With `setuid <http://en.wikipedia.org/wiki/Setuid>`_ an executable gains elevated privileges directly, \
while `sudo <http://en.wikipedia.org/wiki/Sudo>`_ is a program used to give elevated privileges to other executables, that can be configured to allow fine grained access control in userspace similar to the policykit framework mentioned above. With both setuid and sudo, \
it is the application developer's responsibility to take great care that the program running with elevated privileges cannot be used in any malicious way. \
Popular methods for privilege escalation in this context are buffer overruns, unsanitized environments, shell injection or toctou-attacks.

Because running setuid executables does not require an additional password, setuid is generally considered a security risk and to be avoided whenever possible. There are usually very few (well reviewed) setuid binaries on a modern Linux system. Sudo on the other hand requires the user's password, \
has a long record of security-conscious development and lots of flexibility in its access control \
(e.g.. the *Ubuntu distributions or Apples OSX rely heavily on using sudo for administrative tasks). luckyLUKS uses sudo for all privileged operations and also offers the option to create a sudo-rule to allow the current user to omit their password for running luckyLUKS.

The last remark on elevated privileges is about luckyLUKS graphical user interface. To minimize the possible attack surface, all UI code is run with normal user rights, while all privileged operations are executed in separate helper processes (privilege separation). 

Is my data/passphrase safe?
---------------------------

This depends more on general computer security issues than on this particular application. In times where you cannot even trust your `hard drive <http://www.wired.com/2015/02/nsa-firmware-hacking/>`_ you have to go a long way to be at least reasonably safe from state-level attackers. \
If this is a requirement for you, consider using a readonly operating system like `Tails <https://tails.boum.org/>`_ and keep learning about computer security. Sad to say, but a GUI to unlock your encrypted data should be the least of your concerns.

OK, but what about the safety of my passphrase in luckyLUKS compared to using cryptsetup/tcplay directly in a terminal? There are two areas that might be problematic: The first is the standard window system on Unix called X. The X window system originates in a time where the requirements \
and possibilities of a graphical interface where quite different from what they are now. The security architecture is fundamentally broken from todays point of view. It is for instance not possible to keep other applications from receiving all key-events - which includes the passphrase in our case \
(keep in mind that this is also true when using cryptsetup in an X-windowed terminal). That said, the successor to X called Wayland is just around the corner, if you feel adventurous try using luckyLUKS in a Wayland based compositor today.

The second problem is about keeping the passphrase in memory. In general you `should <http://security.stackexchange.com/questions/29019/are-passwords-stored-in-memory-safe>`_ trust your operating system to restrict memory access. Nevertheless it is good practice to overwrite the data in memory \
as soon as unneeded while handling sensitive information. Since luckyLUKS is written in Python, direct memory access is not possible, only removing all references to the passphrase and wait for the garbage collection to clean up later. This it not a problem per-se, since you have to trust your operating system anyway, \
but can turn into a security issue when the memory content gets written to disk on hibernation or into the swapfile. When this happens any sensitive data could still be found in clear text even weeks after the computer was shut down. \
Easy solution: use `encrypted swap <http://askubuntu.com/questions/248158/how-do-i-setup-an-encrypted-swap-file>`_! And consider using full disk encryption, to make sure nobody with physical access to your computer can e.g.. add a keylogger on startup.

OK, so whats the bottom line? LUKS or TrueCrypt containers are safe, nobody that gets access to such a container of yours will be able to open it without your passphrase. The vulnerable point is the computer you use to access the encrypted data. The degree of vulnerability depends on the resources \
and determination of an attacker. Furthermore safety is relative to your own needs being a tradeoff between comfort and security. Using luckyLUKS on your daily operating system without any further precautions will still protect your private data against almost all those prying eyes. \
If you want more certainty use full disk encryption, a live operating system like :code:`Tails` or a computer permanently disconnected from the internet in that order.

Accessing containers on Windows
-------------------------------

If you want to access encrypted containers on Linux and Windows, use NTFS as the filesystem inside the container. It is the only modern filesystem available on Windows and can be used from Linux as well. Since access permissions cannot be mapped from NTFS to Linux user accounts, \
access to NTFS devices is often not restricted -> take care when using unlocked NTFS devices in a multiuser environment! If you share a computer with other people like family members, always close your encrypted container before switching sessions.

To access LUKS containers from Windows use `LibreCrypt <https://github.com/t-d-k/LibreCrypt>`_. To access TrueCrypt containers use the original TrueCrypt or a successor like `VeraCrypt <https://veracrypt.fr/>`_.


Translations
============

The user interface of luckyLUKS is fully translateable, and to offer more translations your help is needed. Since the application is not too complex and more or less feature complete at this point, it won't take long to translate all the neccessary strings and translating won't be an ongoing effort. 

- install a translations editor (eg `Poedit <https://poedit.net/>`_) and `python-babel <https://babel.pocoo.org/>`_
- `Download <https://github.com/jas-per/luckyLUKS/archive/master.zip>`_ the source code of luckyLUKS
- Open a terminal, change directory to the location of the luckyLUKS source files
- Create new locale file (eg :code:`make init_locale NEW_LANG="pt"` for Portuguese, see two-letter codes `here <https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes>`_)
- You will find the new locale file in :code:`luckyLUKS/locale/<LANG_CODE>/LC_MESSAGES/luckyLUKS.po`
- Edit this file in the translations editor
- After editing the po file has to be compiled. Poedit can do this automatically: go to :code:`Preferences` and check :code:`Automatically compile .mo file on save`. Or use :code:`make compile_locales` from the source directory.
- To test your translation, start luckyLUKS from the command line. You might have to set the locale explicitly, if your operation system is using a different locale (eg :code:`LANG=pt_PT.utf-8 LANGUAGE=pt ./luckyluks`)

When you are happy with the results, mail the .po-file you created and your translation will get included in the next release. Pull requests are welcome too :)


Bugs
====

Please report all bugs on the github `issue tracker <https://github.com/jas-per/luckyLUKS/issues>`_. Since this is a GUI tool, the most important information is the exact name of the distribution including the version/year \
and the desktop environment used (eg Gnome, KDE, Mate, XFCE, LXDE). This will help reproducing bugs on a virtual machine a lot.
