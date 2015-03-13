"""
Because access to /dev/mapper is restricted to root, administrator privileges are needed
to handle encrypted containers as block devices. The GUI will be run from a normal
user account while all calls to cryptsetup and mount will be executed from a separate
worker process with administrator privileges. Everything that runs with elevated privs
is included in this module.

Copyright (c) 2014,2015 Jasper van Hoorn (muzius@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""
from __future__ import division
import subprocess
import os.path
import json
import sys
import traceback
import pwd
import errno
import stat
import warnings
import threading
import signal
import random
from time import sleep
try:
    import queue
except ImportError:  # py2
    import Queue as queue


class WorkerException(Exception):

    """ Used to catch error messages from shell calls to give feedback via gtk-gui """
    pass


class UserAbort(Exception):

    """ Worker gets notified about user canceling the command -> no response needed """
    pass


def com_thread(cmdqueue):
    """ Monitors the incoming pipe and puts commands in a queue. Normal signals cannot be sent
        from the parent to a privileged childprocess, this thread detects if the parent closes the pipe instead,
        to signal the main thread and all its child processes.
        :param cmdqueue: Queue to pass incoming commands to main thread
        :type cmdqueue: queue
    """
    while True:
        try:
            buf = sys.stdin.readline().strip()  # blocks
            if not buf:  # check if input pipe closed
                break
            cmd = json.loads(buf, encoding='utf-8')
            # utf8 encode all py2 unicode names&paths
            # when a user enters unicode, the shell that get called here has to be able to handle utf8 of course
            # -> more or less a given, if you intend to USE unicode on your system anyway (eg for filesystem paths ..)
            cmd = {prop: val if val is None or isinstance(val, int) or isinstance(val, str) else val.encode('utf-8') for prop, val in cmd.items()}
            cmdqueue.put(cmd)
        except IOError:
            break
    # send INT to all child processes (eg currently creating new container with dd etc..)
    os.killpg(0, signal.SIGINT)


def run():
    """ Initialize helper and setup ipc. Reads json encoded, newline terminated commands from stdin,
        performs the requested command and returns the json encoded, newline terminated answer on stdout.
        All commands are executed sequentially, but stdin.readline() gets read in another thread that monitors
        the incoming pipe and passes to a queue or quits the helper process if the parent closes the pipe.
        This is needed because normal signals cannot be sent to a privileged childprocess """

    if os.getuid() != 0:
        sys.stdout.write(_('Please call with sudo.'))
        sys.exit(1)
    elif os.getenv("SUDO_USER") is None or os.getenv("SUDO_UID") is None or os.getenv("SUDO_GID") is None:
        sys.stdout.write(_('Missing information of the calling user in sudo environment.\n'
                           'Please make sure sudo is configured correctly.'))
        sys.exit(1)
    else:
        # send ack to establish simple json encoded request/response protocol using \n as terminator
        sys.stdout.write('ESTABLISHED')
        sys.stdout.flush()

    # start thread to monitor the incomming pipe, communicate via queue
    cmdqueue = queue.Queue()
    worker = WorkerHelper(cmdqueue)
    t = threading.Thread(target=com_thread, args=(cmdqueue,))
    t.start()
    # create process group to be able to quit all child processes of the worker
    os.setpgrp()

    with warnings.catch_warnings():
        warnings.filterwarnings('error')  # catch warnings to keep them from messing up the pipe
        while True:
            response = {'type': 'response', 'msg': 'success'}  # return success unless exception
            try:
                # arbitrary timeout needed to be able to get instant KeyboardInterrupt
                # pythons queue.get() without timeout prefers not to be interrupted by KeyboardInterrupt :)
                cmd = cmdqueue.get(timeout=32767)
                if cmd['msg'] == 'status':
                    is_unlocked = worker.check_status(cmd['device_name'], cmd['container_path'], cmd['mount_point'])
                    response['msg'] = 'unlocked' if is_unlocked else 'closed'
                elif cmd['msg'] == 'unlock':
                    worker.unlock_container(cmd['device_name'], cmd['container_path'], cmd['mount_point'])
                elif cmd['msg'] == 'close':
                    worker.close_container(cmd['device_name'], cmd['container_path'])
                elif cmd['msg'] == 'create':
                    worker.create_container(cmd['device_name'], cmd['container_path'], cmd['container_size'], cmd['filesystem_type'], cmd['encryption_format'])
                elif cmd['msg'] == 'authorize':
                    worker.modify_sudoers(os.getenv("SUDO_UID"), nopassword=True)
                else:
                    raise WorkerException(_('Helper process received unknown command'))
            except queue.Empty:
                continue  # timeout reached on queue.get() -> keep polling
            except UserAbort:
                continue  # no response needed
            except WorkerException as we:
                response = {'type': 'error', 'msg': format_exception(we)}
            except KeyError as ke:
                response = {'type': 'error', 'msg': _('Error in communication:\n{error}').format(error=format_exception(ke))}  # thrown if required parameters missing
            except KeyboardInterrupt:
                # gets raised by killpg -> quit
                sys.exit(0)
            except Exception:  # catch ANY exception (including warnings) to show via gui
                response = {'type': 'error', 'msg': ''.join(traceback.format_exception(*sys.exc_info()))}
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()


class WorkerHelper():

    """ offers 5 commands:
        -> check_status() validates the input and returns the current state (unlocked/closed) of the container
        -> unlock_container() asks for the passphrase and tries to unlock and mount a container
        -> close_container() closes and unmounts a container
        -> create_container() initializes a new encrypted LUKS container and sets up the filesystem
        -> modify_sudoers() adds sudo access to the program without password for the current user (/etc/sudoers.d/)
    """

    def __init__(self, cmdqueue=None):
        """ Determine cryptsetup/devmapper version and tcplay installation """
        self.cmdqueue = cmdqueue
        # since version 1.6 cryptsetup allows unified handling of different container types (eg truecrypt) - slight change in syntax required
        version = subprocess.check_output(['cryptsetup', '--version'], stderr=subprocess.STDOUT, universal_newlines=True).split()[1]
        self.is_cryptsetup_legacy = (int(version.split('.')[0]) < 2 and int(version.split('.')[1]) < 6)
        # mangling for non whitelisted characters was introduced in version 1.02.71 of dmsetup because udev needs mangled device names to work
        # see https://bugzilla.redhat.com/show_bug.cgi?id=736486 and https://git.fedorahosted.org/cgit/lvm2.git/tree/WHATS_NEW_DM
        version = subprocess.check_output(['dmsetup', '--version'], stderr=subprocess.STDOUT, universal_newlines=True).split()[2]
        self.is_dmsetup_nomangle = (int(version.split('.')[0]) < 2 and int(version.split('.')[1]) < 3 and int(version.split('.')[2]) < 72)
        # check if tcplay installed
        self.is_tc_installed = any([os.path.exists(os.path.join(p, 'tcplay')) for p in os.environ["PATH"].split(os.pathsep)])
        # http://bugs.python.org/issue16903 (backward compat python3: solved in 3.2.4 but debian wheezy and ubuntu precise come with 3.2.3)
        # up to 3.2.3: communicate with universal_newlines=True accepts bytes and doesn't accept strings
        # since 3.2.4: accepts strings and doesn't accept bytes
        from pkg_resources import parse_version
        self.is_popen_communicate_broken = parse_version('3') < parse_version(sys.version) < parse_version('3.2.4')

    def communicate(self, request):
        """ Helper to get an synchronous response from UI (obtain Passphrase or signal create progress)
            :param request: message to send to the UI
            :type request: str
            :returns: The JSON encoded response from the UI
            :rtype: str
            :raises: UserAbort
        """
        sys.stdout.write(json.dumps({'type': 'request', 'msg': request}) + '\n')
        sys.stdout.flush()
        response = self.cmdqueue.get()  # wait for response
        try:
            assert('type' in response and 'msg' in response)
        except AssertionError:
            raise UserAbort()
        # quit if abort or unexpected msg from ui
        if response['type'] != 'response':
            raise UserAbort()
        if self.is_popen_communicate_broken:
            response['msg'] = response['msg'].encode('utf-8')
        return response

    def check_status(self, device_name, container_path, mount_point=None):
        """
            Validates the input and returns the current state (unlocked/closed) of the container.
            The checks are sufficient to keep users from shooting themselves in the foot and
            provide the most possible protection against TOCTOU attacks: Since most commands are
            executed using the device mapper name, there is not much attack surface for TOCTOU anyway,
            since root access is needed to access device mapper. It would be possible to unmount
            other users containers with the right timing though - slightly annoying but no serious threat
            :param device_name: The device mapper name
            :type device_name: str
            :param container_path: The path of the container file
            :type container_path: str
            :param mount_point: The path of an optional mount point
            :type mount_point: str or None
            :returns: True if LUKS device is active/unlocked
            :rtype: bool
            :raises: WorkerException
        """
        uid = int(os.getenv("SUDO_UID"))

        # device_name and container_path valid?
        if device_name is '':
            raise WorkerException(_('Device Name is empty'))
        # block non conforming device names when using older device mapper to prevent problems with udev
        if self.is_dmsetup_nomangle and device_name not in self.get_device_mapper_name(device_name):
            raise WorkerException(_('Device Name is contains characters,\n'
                                    'not supported by your version of device mapper.\n\n'
                                    'Please restrict the name to 0-9, A-Z, a-z and #+-.:=@_'))
        # check access rights to container file
        if not os.path.exists(container_path) or os.stat(container_path).st_uid != uid:
            sleep(random.random())  # 0-1s to prevent misuse of exists()
            raise WorkerException(_('Container file not accessible\nor path does not exist:\n\n{file_path}').format(file_path=container_path))

        is_unlocked = self.is_LUKS_active(device_name)

        if is_unlocked:
            # make sure container file currently in use for device name is the same as the supplied container path
            if container_path != self.get_container(device_name):
                raise WorkerException(_('Could not unlock container:\n{file_path}\n'
                                        '<b>{device_name}</b> is already unlocked\n'
                                        'using a different container\n'
                                        'Please change the name to unlock this container').
                                      format(file_path=container_path, device_name=device_name))

        # container is not unlocked
        else:
            # validate device name
            try:
                name_len = len(bytes(device_name, 'utf-8'))  # PY3
            except TypeError:
                name_len = len(device_name)
            if name_len > 16:
                # the goal here is not to confuse the user:
                # thus Name==Label of the partition inside the encrypted container -> because thats what usually gets presented to the user (filemanager)
                # see checks in create_container below for length restictions on partition labels
                # dev/mapper would only be able to handle slightly longer names for unicode anyways
                raise WorkerException(_('Device Name too long:\nOnly up to 16 characters possible, even less for unicode\n(roughly 8 non-ascii characters possible)'))

            if device_name[0:1] is '-' or '/' in device_name:  # cryptsetup thinks -isanoption and "/" is not supported by devmapper
                raise WorkerException(_('Illegal Device Name!\nNames starting with `-` or using `/` are not possible'))

            # prevent container from being unlocked multiple times with different names
            if subprocess.check_output(['losetup', '-j', container_path], stderr=subprocess.STDOUT, universal_newlines=True) != '':
                # container is already in use -> try to find out the device name
                existing_device_name = ''
                encrypted_devices = subprocess.check_output(['dmsetup', 'status', '--target', 'crypt'], stderr=subprocess.STDOUT, universal_newlines=True).strip()
                for encrypted_device in encrypted_devices.split('\n'):
                    encrypted_device = encrypted_device[:encrypted_device.find(':')].strip()
                    if container_path == self.get_container(encrypted_device):
                        existing_device_name = encrypted_device
                        break
                raise WorkerException(_('Cannot use the container\n'
                                        '{file_path}\n'
                                        'The container is already in use ({existing_device}).').format(file_path=container_path, existing_device=existing_device_name))

            # validate mount_point if given
            if not mount_point is None:

                if not os.path.exists(mount_point) or os.stat(mount_point).st_uid != uid:
                    sleep(random.random())  # 0-1s to prevent misuse of exists()
                    raise WorkerException(_('Mount point not accessible\nor path does not exist:\n\n{mount_dir}').format(mount_dir=mount_point))

                if os.path.ismount(mount_point):
                    raise WorkerException(_('Already mounted at mount point:\n\n{mount_dir}').format(mount_dir=mount_point))

                if os.listdir(mount_point):
                    raise WorkerException(_('Designated mount directory\n{mount_dir}\nis not empty').format(mount_dir=mount_point))

        return is_unlocked

    def unlock_container(self, device_name, container_path, mount_point=None):
        """ Unlocks LUKS or Truecrypt containers.
            Validates input and keeps asking
            for the passphrase until successfull unlock,
            followed by an optional mount.
            :param device_name: The device mapper name
            :type device_name: str
            :param container_path: The path of the container file
            :type container_path: str
            :param mount_point: The path of an optional mount point
            :type mount_point: str or None
            :raises: WorkerException
        """
        ''' ask for password and try to open container, followed by an optional mount '''
        is_unlocked = self.check_status(device_name, container_path, mount_point)
        if not is_unlocked:  # just return if unlocked -> does not mount an already unlocked container

            # workaround udisks-daemon crash (udisksd from udisks2 is okay): although cryptsetup is able to handle
            # loopback device creation/teardown itself using this crashes udisks-daemon  -> manual loopback device handling here
            try:
                loop_dev = subprocess.check_output(['losetup', '-f', '--show', container_path], stderr=subprocess.PIPE, universal_newlines=True).strip()
            except subprocess.CalledProcessError as cpe:
                raise WorkerException(cpe.output)  # most likely no more loopdevices available
            crypt_initialized = False

            try:
                # check if LUKS container, try Truecrypt otherwise (tc container cannot be identified by design)
                container_is_luks = (subprocess.call(['cryptsetup', 'isLuks', container_path]) == 0)
                if container_is_luks:
                    open_command = ['cryptsetup', 'luksOpen' if self.is_cryptsetup_legacy else 'open', loop_dev, device_name]
                else:
                    if self.is_cryptsetup_legacy:
                        raise WorkerException(_('Container file is not a LUKS encrypted device:\n{file_path}\n\n').format(file_path=loop_dev) +
                                              _('If you want to use TrueCrypt containers\n'
                                                'make sure `cryptsetup` is at least version 1.6 (`cryptsetup --version`)\n'
                                                'and `tcplay` is installed (eg for Debian/Ubuntu `apt-get install tcplay`)'))
                    else:
                        open_command = ['cryptsetup', 'open', '--type', 'tcrypt', loop_dev, device_name]

                with open(os.devnull) as DEVNULL:
                    while not is_unlocked:
                        p = subprocess.Popen(open_command, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=DEVNULL, universal_newlines=True, close_fds=True)
                        __, errors = p.communicate(self.communicate('getPassword')['msg'])
                        if p.returncode == 0:
                            is_unlocked = True
                        elif p.returncode == 2:  # cryptsetup: no permission (bad passphrase)
                            continue
                        else:
                            raise WorkerException(errors)
                crypt_initialized = True
            finally:
                if not crypt_initialized:
                    self.detach_loopback_device(loop_dev)

            if mount_point is not None:  # only mount if optional parameter mountpoint is set
                try:
                    subprocess.check_output(['mount', '-o', 'nosuid,nodev', self.get_device_mapper_name(device_name), mount_point], stderr=subprocess.STDOUT, universal_newlines=True)
                except subprocess.CalledProcessError as cpe:
                    raise WorkerException(cpe.output)
            # signal udev to process event queue (required for older udisks)
            with open(os.devnull) as DEVNULL:
                subprocess.call(['udevadm', 'trigger'], stdout=DEVNULL, stderr=subprocess.STDOUT)

    def close_container(self, device_name, container_path):
        """ Validates input and tries to unmount /dev/mapper/<name> and close container
            :param device_name: The device mapper name
            :type device_name: str
            :param container_path: The path of the container file
            :type container_path: str
            :raises: WorkerException
        """
        if self.check_status(device_name, container_path):  # just return if not unlocked
            # for all mounting /dev/mapper/device_name is used
            try:
                # unfortunately, umount returns the same errorcode for device not mounted and device busy
                # clear locale to be able to parse output
                env_lang_cleared = os.environ.copy()
                env_lang_cleared['LANGUAGE'] = 'C'
                subprocess.check_output(['umount', self.get_device_mapper_name(device_name)], stderr=subprocess.STDOUT, universal_newlines=True, env=env_lang_cleared)
            except subprocess.CalledProcessError as cpe:
                if 'not mounted' not in cpe.output:  # ignore if not mounted and proceed with closing the container
                    raise WorkerException(_('Unable to close container, device is busy'))
            # get reference to loopback device before closing the container
            associated_loop = self.get_loopback_device(device_name)
            try:
                subprocess.check_output(['cryptsetup', 'luksClose' if self.is_cryptsetup_legacy else 'close', device_name], stderr=subprocess.STDOUT, universal_newlines=True)
            except subprocess.CalledProcessError as cpe:
                # ignore single remove ioctl: bug with older versions of dev-mapper/udev, see https://bugzilla.redhat.com/show_bug.cgi?id=1024347
                if cpe.returncode != errno.EIO or len(cpe.output.splitlines()) > 1:
                    raise WorkerException(cpe.output)
            # remove loopback device and signal udev to process event queue (required for older udisks)
            try:
                sleep(0.2)  # give udisks some time to process closing of container ..
                subprocess.check_output(['losetup', '-d', associated_loop], stderr=subprocess.STDOUT, universal_newlines=True)
            except subprocess.CalledProcessError as cpe:
                raise WorkerException(cpe.output)
            with open(os.devnull) as DEVNULL:
                subprocess.call(['udevadm', 'trigger'], stdout=DEVNULL, stderr=subprocess.STDOUT)

    def create_container(self, device_name, container_path, container_size, filesystem_type, encryption_format):
        """ Creates a new LUKS container with requested size and filesystem after validating parameters
            Three step process: asks for passphrase after initializing container with random bits,
            and signals successful LUKS initialization before writing the filesystem
            :param device_name: The device mapper name, used as filesystem label as well
            :type device_name: str
            :param container_path: The path of the container file to be created
            :type container_path: str
            :param container_size: The size the new container in KB
            :type container_size: int
            :param filesystem_type: The type of the filesystem inside the new container (supported: 'ext4', 'ext2', 'ntfs')
            :type filesystem_type: str
            :param encryption_format: The type of the encryption format used for the new container (supported: 'LUKS', 'TrueCrypt')
            :type encryption_format: str
            :raises: WorkerException
        """
        # STEP0: #########################################################################
        # Sanitize user input and perform some checks before starting the process to avoid
        # failure later on eg. dd writing out random data for 3 hours to initialize the
        # new container, only to find out that there is not enough space on the device,
        # or that the designated device name is already in use on /dev/mapper
        #

        # validate container file
        if os.path.basename(container_path).strip() == '':
            raise WorkerException(_('Container Filename not supplied'))

        # validate device name
        if device_name is '':
            raise WorkerException(_('Device Name is empty'))

        if device_name[0:1] is '-' or '/' in device_name:  # cryptsetup thinks -isanoption and "/" is not supported by devmapper
            raise WorkerException(_('Illegal Device Name!\nNames starting with `-` or using `/` are not possible'))

        if self.is_dmsetup_nomangle and device_name not in self.get_device_mapper_name(device_name):
            raise WorkerException(_('Device Name is contains characters,\n'
                                    'not supported by your version of device mapper.\n\n'
                                    'Please restrict the name to 0-9, A-Z, a-z and #+-.:=@_'))

        try:
            name_len = len(bytes(device_name, 'utf-8'))  # PY3
        except TypeError:
            name_len = len(device_name)
        if name_len > 16:  # ext-labels are the most restricted (max 16Bytes)
            # dev-mapper and ntfs-label would support slightly longer strings, but hey: DOS allowed only 8chars and unicode wasn't even supported ;)
            raise WorkerException(_('Device Name too long:\nOnly up to 16 characters possible, even less for unicode \n(roughly 8 non-ascii characters possible)'))

        if os.path.exists(self.get_device_mapper_name(device_name)):
            raise WorkerException(_('Device Name already in use:\n\n{device_name}').format(device_name=device_name))

        # validate container size
        if container_size < 5242880:
            raise WorkerException(_('Container size too small\nto create encrypted filesystem\nPlease choose at least 5MB'))

        container_dir = os.path.dirname(container_path)
        free_space = os.statvfs(container_dir)
        free_space = free_space.f_bavail * free_space.f_bsize
        if container_size > free_space:
            raise WorkerException(_('Not enough free disc space for container:\n\n{space_needed} MB needed\n{space_available} MB available').
                                  format(space_needed=str(int(container_size / 1024 / 1024)),
                                         space_available=str(int(free_space / 1024 / 1024))))

        # validate encryption_format and filesystem
        if filesystem_type not in ['ext4', 'ext2', 'ntfs']:
            raise WorkerException(_('Unknown filesystem type: {filesystem_type}').format(filesystem_type=str(filesystem_type)))
        if encryption_format == 'Truecrypt' and (not self.is_tc_installed or self.is_cryptsetup_legacy):
            raise WorkerException(_('If you want to use TrueCrypt containers\n'
                                    'make sure `cryptsetup` is at least version 1.6 (`cryptsetup --version`)\n'
                                    'and `tcplay` is installed (eg for Debian/Ubuntu `apt-get install tcplay`)'))

        # STEP1: ##########################################################
        # create container file by filling allocated space with random bits
        #

        count = str(int(container_size / 1024 / 1024)) + 'K'
        # oflag=excl -> fail if the output file already exists
        # runas user to fail on access restictions
        cmd = ['sudo', '-u', os.getenv("SUDO_USER"), 'dd', 'if=/dev/urandom', 'of=' + container_path, 'bs=1K', 'count=' + count, 'conv=excl']
        with open(os.devnull) as DEVNULL:
            p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=DEVNULL, universal_newlines=True, close_fds=True)
            __, errors = p.communicate()
        if p.returncode != 0:
            #'sudo -u' might add this -> don't display
            raise WorkerException(errors.replace('Sessions still open, not unmounting', '').strip())
            # TODO: this can only work with english locale, but this errormessage doesn't seem to be localized in sudo yet .. get rid of the problem (strip env?) or remove msg in all languages

        # setup loopback device with created container
        try:
            reserved_loopback_device = subprocess.check_output(['losetup', '-f', '--show', container_path], stderr=subprocess.PIPE, universal_newlines=True).strip()
        except subprocess.CalledProcessError as cpe:
            raise WorkerException(cpe.output)
        crypt_initialized = False
        try:

            # STEP2: ######################################################
            # ask user for password and initialize LUKS/TrueCrypt container
            #

            resp = self.communicate('getPassword')

            if encryption_format == 'LUKS':

                cmd = ['cryptsetup', 'luksFormat', '-q', reserved_loopback_device]
                with open(os.devnull) as DEVNULL:
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=DEVNULL, universal_newlines=True, close_fds=True)
                    __, errors = p.communicate(resp['msg'])
                if p.returncode != 0 or errors:
                    raise WorkerException(errors)

                open_command = ['cryptsetup', 'luksOpen' if self.is_cryptsetup_legacy else 'open', reserved_loopback_device, device_name]

            elif encryption_format == 'TrueCrypt':

                with open(os.devnull) as DEVNULL:
                    cmd = ['tcplay', '-c', '-d', reserved_loopback_device, '--insecure-erase']  # secure erase already done with dd
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=DEVNULL, universal_newlines=True, close_fds=True)
                    # tcplay needs the password twice & confirm -> using sleep instead of parsing output
                    # ugly, but crypt-init takes ages with tcplay anyway
                    sleep(1)
                    p.stdin.write(resp['msg'] + '\n')
                    p.stdin.flush()
                    sleep(1)
                    p.stdin.write(resp['msg'] + '\n')
                    p.stdin.flush()
                    sleep(1)
                    p.stdin.write('y\n')  # .. until tcplay gets localized :)
                    p.stdin.flush()
                    p.wait()
                if p.returncode != 0:
                    raise WorkerException(p.stderr.read())

                open_command = ['cryptsetup', 'open', '--type', 'tcrypt', reserved_loopback_device, device_name]

            else:
                raise WorkerException(_('Unknown encryption format: {enc_fmt}').format(enc_fmt=encryption_format))

            crypt_initialized = True
            self.communicate('formatDone')  # signal status

            # STEP3: ############################################
            # open encrypted container and format with filesystem
            #

            with open(os.devnull) as DEVNULL:
                p = subprocess.Popen(open_command, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=DEVNULL, universal_newlines=True, close_fds=True)
                __, errors = p.communicate(resp['msg'])
            del resp  # get rid of pw
            if p.returncode != 0 or errors:
                raise WorkerException(errors)

            # fs-root of created ext-filesystem should belong to the user
            device_mapper_name = self.get_device_mapper_name(device_name)
            if filesystem_type == 'ext4':
                cmd = ['mkfs.ext4', '-L', device_name, '-O', '^has_journal', '-m', '0', '-q', device_mapper_name]
            elif filesystem_type == 'ext2':
                cmd = ['mkfs.ext2', '-L', device_name, '-m', '0', '-q', device_mapper_name]
            elif filesystem_type == 'ntfs':
                cmd = ['mkfs.ntfs', '-L', device_name, '-Q', '-q', device_mapper_name]
            try:
                subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
            except subprocess.CalledProcessError as cpe:
                raise WorkerException(cpe.output)

            # remove group/other read/execute rights from fs root if possible
            if filesystem_type != 'ntfs':
                from uuid import uuid4
                tmp_mount = os.path.join('/tmp/', str(uuid4()))
                os.mkdir(tmp_mount)
                try:
                    subprocess.check_output(['mount', '-o', 'nosuid,nodev', device_mapper_name, tmp_mount], stderr=subprocess.STDOUT, universal_newlines=True)
                except subprocess.CalledProcessError as cpe:
                    raise WorkerException(cpe.output)
                os.chown(tmp_mount, int(os.getenv("SUDO_UID")), int(os.getenv("SUDO_GID")))
                os.chmod(tmp_mount, 0o700)

        finally:
            # cleanup: either close container or just remove loopback if early abort/exception
            if not crypt_initialized:
                self.detach_loopback_device(reserved_loopback_device)
            else:
                self.close_container(device_name, container_path)

    def modify_sudoers(self, user_id, nopassword=False):
        """ Adds sudo access to the program (without password) for the current user (/etc/sudoers.d/)
            :param user_id: unix user id
            :type user_id: int
            :returns: should access be granted without password
            :rtype: bool
        """
        program_path = os.path.abspath(sys.argv[0])
        try:
            user_name = pwd.getpwuid(int(user_id))[0]
        except KeyError:
            raise WorkerException(_('Cannot change sudo rights, invalid username'))

        if (os.stat(program_path).st_uid != 0 or os.stat(program_path).st_gid != 0 or os.stat(program_path).st_mode & stat.S_IWOTH):

            raise WorkerException(_('I`m afraid I can`t do that.\n\n'
                                    'To be able to permit permanent changes to sudo rights,\n'
                                    'please make sure the program is owned by root\n'
                                    'and not writeable by others.\n'
                                    'Execute the following commands in your shell:\n\n'
                                    'chmod 755 {program}\n'
                                    'sudo chown root:root {program}\n\n').format(program=program_path))

        if not os.path.exists('/etc/sudoers.d'):
            os.makedirs('/etc/sudoers.d')

        sudoers_file_path = '/etc/sudoers.d/lucky-luks'
        sudoers_file = open(sudoers_file_path, 'a')
        sudoers_file.write("{username} ALL = (root) {nopasswd}{program}\n".format(username=user_name,
                                                                                  nopasswd='NOPASSWD: ' if nopassword else '',
                                                                                  program=program_path))
        sudoers_file.close()

        os.chmod(sudoers_file_path, 0o440)

    def is_LUKS_active(self, device_name):
        """ Checks if device is active/unlocked
            :param device_name: The device mapper name
            :type device_name: str
            :returns: True if active LUKS device found
            :rtype: bool
        """
        with open(os.devnull) as DEVNULL:
            returncode = subprocess.call(['cryptsetup', 'status', device_name], stdout=DEVNULL, stderr=subprocess.STDOUT)
        return returncode == 0

    def detach_loopback_device(self, loopback_device):
        """ Detaches given loopback device
            :param loopback_device: The loopback device path (eg /dev/loop2)
            :type loopback_device: str
        """
        with open(os.devnull) as DEVNULL:
            subprocess.call(['losetup', '-d', loopback_device], stdout=DEVNULL, stderr=subprocess.STDOUT)

    def get_loopback_device(self, device_name):
        """ Returns the corresponding loopback device path to a given device mapper name
            :param device_name: The device mapper name
            :type device_name: str
            :returns: The corresponding loopback device path (eg /dev/loop2)
            :rtype: str
        """
        return self.get_crypt_status(device_name, 'device:')

    def get_container(self, device_name):
        """ Returns the corresponding container path to a given device mapper name
            :param device_name: The device mapper name
            :type device_name: str
            :returns: The corresponding container path
            :rtype: str
        """
        return self.get_crypt_status(device_name, 'loop:')

    def get_crypt_status(self, device_name, search_property):
        """ Parses cryptsetup status output for a device mapper name
            and returns either loopback device or container path
            :param device_name: The device mapper name
            :type device_name: str
            :param search_property: The property to return from status output
            :type search_property: 'device:' or 'loop:'
            :returns: loopback device or container path
            :rtype: str
        """
        try:
            stat_output = subprocess.check_output(['cryptsetup', 'status', device_name], stderr=subprocess.STDOUT, universal_newlines=True)
            # parsing status output: this has been unchanged in cryptsetup since version 1.3 (April 2011) - should be safe to use
            for line in stat_output.split('\n'):
                if search_property in line:
                    return line[line.find('/'):].strip()
        except subprocess.CalledProcessError:
            return ''  # device not found

    def get_device_mapper_name(self, device_name):
        """ Mapping for filesystem access to /dev/mapper/
            Escapes most non alphanumeric and all unicode characters in the device name

            -> from the device-mapper sources:
            * Mangle all characters in the input string which are not on a whitelist
            * with '\xCC' format, where CC is the hex value of the character.
            * Actually, DM supports any character in a device name.
            * This whitelist is just for proper integration with udev.

            :param device_name: The device mapper name
            :type device_name: str
            :returns: The mangled device mapper name for filesystem access
            :rtype: str
        """
        dm_name = '/dev/mapper/'
        try:  # use single-char list for python3 (splitting 2 or more byte utf8-encoded chars..)
            device_name = bytes(device_name, 'utf-8')
            device_name = [chr(byte) for byte in device_name]
        except TypeError:
            # already a utf-8 encoded bytestring in python2
            pass

        for char in device_name:
            if ((char >= '0' and char <= '9') or
                (char >= 'A' and char <= 'Z') or
                (char >= 'a' and char <= 'z') or
                    char in "#+-.:=@_"):

                dm_name += char
            else:
                dm_name += '\\' + str(hex(ord(char))[1:])

        return dm_name
