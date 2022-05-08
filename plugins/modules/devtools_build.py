#!/usr/bin/python

# Copyright: (c) 2022, claasklar <git@claasklar.de>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r'''
---
module: devtools_build

short_description: Module for interacting with archlinux extra-x86_64-build tool

version_added: "0.0.0"

description: The module builds packages using extra-x86_64-build and optionally installs them

options:
    pkgbuild_dir:
        description: Directory containing the PKGBUILD file
        required: true
        type: str
    action:
        description:
            - Action to take
            - Install includes build
            - If package is a split package, all packages will be installed
        type: str
        choices: ['build', 'install']
        default: 'build'
    install_options:
        description:
            - These options will be appended to pacman -U call
        type: list
        elements: str
        default: []

requirements:
    - devtools installed

# extends_documentation_fragment:
#     - de_claasklar.devtools.devtools_build

author:
    - claasklar (@claasklar)
'''

EXAMPLES = r'''
# Pass in a message
- name: Test with a message
  my_namespace.my_collection.my_test:
    name: hello world

# pass in a message and have changed true
- name: Test with a message and changed output
  my_namespace.my_collection.my_test:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_namespace.my_collection.my_test:
    name: fail me
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'hello world'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'
'''

from ansible.module_utils.basic import AnsibleModule
import os
import re
import sys

MAKEPKG_SRCINFO = ["bash", "-c", "source /usr/share/makepkg/srcinfo.sh && source PKGBUILD && write_srcinfo"]

def srcinfo(pkgbuild_dir, module):
    _, srcinfo, err = module.run_command(MAKEPKG_SRCINFO, cwd=pkgbuild_dir)
    return srcinfo

def pkg_infos(srcinfo):
    packages = []
    version_info = {"pkgname": None, "pkgver": None, "pkgrel": None}

    for line in srcinfo.splitlines():
        line = line.strip()
        if line.startswith("pkgver ="):
            _, _, version_info["pkgver"] = line.partition(" = ")
        if line.startswith("pkgrel ="):
            _, _, version_info["pkgrel"] = line.partition(" = ")

    for line in srcinfo.splitlines():
        line = line.strip()
        if line.startswith("pkgname ="):
            _, _, pkgname = line.partition(" = ")
            pkg_version_info = dict(version_info)
            pkg_version_info["pkgname"] = pkgname
            packages.append(pkg_version_info)

    return packages


def pkg_version_regex(pkg_info):
    return "{pkgname}-{pkgver}-{pkgrel}-[a-z0-9_]+\\.pkg\\.tar\\.((zst|xz))".format_map(pkg_info)


def pkg_exists(pkg_info):
    file_regex = pkg_version_regex(pkg_info)
    for file_name in os.listdir():
        if re.fullmatch(file_regex, file_name) is not None:
            return True
    return False


def build_packages(pkgbuild_dir, module):
    changed = False
    for pkg_info in pkg_infos(srcinfo(pkgbuild_dir, module)):
        changed = changed or build_package(pkg_info, pkgbuild_dir, module)

    return changed


def build_package(pkg_info, pkgbuild_dir, module):
    if not pkg_exists(pkg_info):
        module.run_command(["extra-x86_64-build"], check_rc=True, cwd=pkgbuild_dir)
        return True

    return False


def is_package_installed(pkg_info, module):
    rc, stdout, _ = module.run_command(["pacman", "-Q", pkg_info["pkgname"]], check_rc=False)
    if rc != 0:
        return False

    # stdout is in this format "<pkgname> <pkgver>-<pkgrel>"
    installed_pkgver, _, installed_pkgrel = stdout.partition(" ")[2].partition("-")
    if installed_pkgver != pkg_info["pkgver"]:
        return False
    if installed_pkgrel != pkg_info["pkgrel"]:
        return False

    return True


def install_packages(pkgbuild_dir, install_options, module):
    changed = False
    for pkg_info in pkg_infos(srcinfo(pkgbuild_dir, module)):
        changed = install_package(pkg_info, install_options, pkgbuild_dir, module) or changed

    return changed

def install_package(pkg_info, install_options, pkgbuild_dir, module):
    if is_package_installed(pkg_info, module):
        return False

    pkg_file_name = None
    file_regex = pkg_version_regex(pkg_info)

    for file_name in os.listdir():
        if re.fullmatch(file_regex, file_name) is not None:
            pkg_file_name = file_name
            break

    module.run_command(["pacman", "-U", "--noconfirm"] + install_options + [pkg_file_name], check_rc=True, cwd=pkgbuild_dir)
    return True


def init_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        pkgbuild_dir=dict(type='str', required=True),
        action=dict(type='str', choices=['build', 'install'], default='build'),
        install_options=dict(type='list', elements='str', default=[])
    )
    return AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )


def run_module():
    module = init_module()

    result = dict(changed=False)

    if module.check_mode:
        module.exit_json(**result)

    os.chdir(module.params['pkgbuild_dir'])
    result["changed"] = build_packages(module.params['pkgbuild_dir'], module)

    if module.params['action'] == "install":
        install_packages(module.params['pkgbuild_dir'], module.params['install_options'], module)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
