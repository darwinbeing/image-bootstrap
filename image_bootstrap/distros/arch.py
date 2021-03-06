# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under AGPL v3 or later

from __future__ import print_function

import os

from textwrap import dedent

from directory_bootstrap.distros.arch import ArchBootstrapper, \
        SUPPORTED_ARCHITECTURES
from directory_bootstrap.shared.commands import \
        COMMAND_CHROOT, COMMAND_SED, COMMAND_FIND

from image_bootstrap.distros.base import DISTRO_CLASS_FIELD, DistroStrategy


class ArchStrategy(DistroStrategy):
    DISTRO_KEY = 'arch'
    DISTRO_NAME_SHORT = 'Arch'
    DISTRO_NAME_LONG = 'Arch Linux'

    def __init__(self, messenger, executor,
                abs_cache_dir, image_date_triple_or_none, mirror_url,
                abs_resolv_conf):
        self._messenger = messenger
        self._executor = executor

        self._abs_cache_dir = abs_cache_dir
        self._image_date_triple_or_none = image_date_triple_or_none
        self._mirror_url = mirror_url
        self._abs_resolv_conf = abs_resolv_conf

    def get_commands_to_check_for(self):
        return ArchBootstrapper.get_commands_to_check_for() + [
                COMMAND_CHROOT,
                COMMAND_FIND,
                COMMAND_SED,
                ]

    def check_architecture(self, architecture):
        if architecture == 'amd64':
            architecture = 'x86_64'

        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ValueError('Architecture "%s" not supported' % architecture)

        return architecture

    def run_directory_bootstrap(self, abs_mountpoint, architecture, bootloader_approach):
        self._messenger.info('Bootstrapping %s into "%s"...'
                % (self.DISTRO_NAME_SHORT, abs_mountpoint))

        bootstrap = ArchBootstrapper(
                self._messenger,
                self._executor,
                abs_mountpoint,
                self._abs_cache_dir,
                architecture,
                self._image_date_triple_or_none,
                self._mirror_url,
                self._abs_resolv_conf,
                )
        bootstrap.run()

    def create_network_configuration(self, abs_mountpoint):
        self._messenger.info('Making sure that network interfaces get named eth*...')
        os.symlink('/dev/null', os.path.join(abs_mountpoint, 'etc/udev/rules.d/80-net-setup-link.rules'))

        network_filename = os.path.join(abs_mountpoint, 'etc/systemd/network/eth0-dhcp.network')
        self._messenger.info('Writing file "%s"...' % network_filename)
        with open(network_filename, 'w') as f:
            print(dedent("""
                    [Match]
                    Name=eth0

                    [Network]
                    DHCP=both
                    """), file=f)

    def _install_packages(self, package_names, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'pacman',
                '--noconfirm',
                '--sync',
                ] + list(package_names)
        self._executor.check_call(cmd, env=env)

    def ensure_chroot_has_grub2_installed(self, abs_mountpoint, env):
        self._install_packages(['grub'], abs_mountpoint, env)

    def get_chroot_command_grub2_install(self):
        return 'grub-install'

    def generate_grub_cfg_from_inside_chroot(self, abs_mountpoint, env):
        cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'grub-mkconfig',
                '-o', '/boot/grub/grub.cfg',
                ]
        self._executor.check_call(cmd, env=env)

    def adjust_initramfs_generator_config(self, abs_mountpoint):
        abs_linux_preset = os.path.join(abs_mountpoint, 'etc', 'mkinitcpio.d', 'linux.preset')
        self._messenger.info('Adjusting "%s"...' % abs_linux_preset)
        cmd_sed = [
                COMMAND_SED,
                's,^[# \\t]*default_options=.*,default_options="-S autodetect"  # set by image-bootstrap,g',
                '-i', abs_linux_preset,
                ]
        self._executor.check_call(cmd_sed)

    def generate_initramfs_from_inside_chroot(self, abs_mountpoint, env):
        cmd_mkinitcpio = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'mkinitcpio',
                '-p', 'linux',
                ]
        self._executor.check_call(cmd_mkinitcpio, env=env)

    def perform_post_chroot_clean_up(self, abs_mountpoint):
        self._messenger.info('Cleaning chroot pacman cache...')
        cmd = [
                COMMAND_FIND,
                os.path.join(abs_mountpoint, 'var/cache/pacman/pkg/'),
                '-type', 'f',
                '-delete',
                ]
        self._executor.check_call(cmd)

    def install_sudo(self, abs_mountpoint, env):
        self._install_packages(['sudo'], abs_mountpoint, env)

    def install_cloud_init_and_friends(self, abs_mountpoint, env):
        self._install_packages(['cloud-init'], abs_mountpoint, env)

    def get_cloud_init_datasource_cfg_path(self):
        return '/etc/cloud/cloud.cfg.d/90_datasource.cfg'

    def install_sshd(self, abs_mountpoint, env):
        self._install_packages(['openssh'], abs_mountpoint, env)

    def _make_services_autostart(self, service_names, abs_mountpoint, env):
        for service_name in service_names:
            self._messenger.info('Making service "%s" start automatically...' % service_name)
            cmd = [
                COMMAND_CHROOT,
                abs_mountpoint,
                'systemctl',
                'enable',
                service_name,
                ]
            self._executor.check_call(cmd, env=env)

    def make_openstack_services_autostart(self, abs_mountpoint, env):
        self._make_services_autostart([
                'systemd-networkd',
                'sshd',
                'cloud-init-local',
                'cloud-init',
                'cloud-config',
                'cloud-final',
                ], abs_mountpoint, env)

    @classmethod
    def add_parser_to(clazz, distros):
        arch = distros.add_parser(clazz.DISTRO_KEY, help=clazz.DISTRO_NAME_LONG)
        arch.set_defaults(**{DISTRO_CLASS_FIELD: clazz})

        ArchBootstrapper.add_arguments_to(arch)

    @classmethod
    def create(clazz, messenger, executor, options):
        return clazz(
                messenger,
                executor,
                os.path.abspath(options.cache_dir),
                options.image_date,
                options.mirror_url,
                os.path.abspath(options.resolv_conf),
                )
