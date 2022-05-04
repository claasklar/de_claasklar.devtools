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
        type: str
        choices: ['build', 'install']
        default: 'build'
    install_options:
        description:
            - These optiosn will be appendend to pacman -U call
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


def pkg_info(pkgbuild):
    version_info = {"pkgname": None, "pkgver": None, "pkgrel": None}

    for line in pkgbuild:
        line = line.strip()
        if line.startswith("pkgname="):
            _, _, version_info["pkgname"] = line.partition("=")
            # TODO: support split packages
            version_info["pkgname"] = version_info["pkgname"].lstrip("('").rstrip("')")
        if line.startswith("pkgver="):
            _, _, version_info["pkgver"] = line.partition("=")
        if line.startswith("pkgrel="):
            _, _, version_info["pkgrel"] = line.partition("=")

    for item in version_info.items():
        if item[1] is None:
            raise KeyError("{0} not found in PKGBUILD".format(item[0]))

    return version_info


def pkg_version_regex(pkgbuild):
    version_info = pkg_info(pkgbuild)
    return "{pkgname}-{pkgver}-{pkgrel}-[a-z0-9_]+\\.pkg\\.tar\\.((zst|xz))".format_map(version_info)


def pkg_exists():
    with open("PKGBUILD", "r") as pkgbuild:
        pkg_version = pkg_version_regex(pkgbuild)
    for file_name in os.listdir():
        if re.fullmatch(pkg_version, file_name) is not None:
            return True
    return False


def build_package(pkgbuild_dir, module):
    if pkg_exists():
        return False

    module.run_command(["extra-x86_64-build"], check_rc=True, cwd=pkgbuild_dir)
    return True


def is_package_installed(module):
    _, stdout, _ = module.run_command(["pacman", "-Q"], check_rc=True)
    module.debug(stdout)
    installed_packages = map(lambda line: line.partition(" ")[0], stdout.splitlines())

    with open("PKGBUILD", "r") as pkgbuild:
        pkg_version = pkg_info(pkgbuild)
        if pkg_version["pkgname"] in installed_packages:
            return True

    return False


def install_package(pkgbuild_dir, install_options, module):
    if is_package_installed(module):
        return False

    pkg_file_name = None
    with open("PKGBUILD", "r") as pkgbuild:
        pkg_version = pkg_version_regex(pkgbuild)

    for file_name in os.listdir():
        if re.fullmatch(pkg_version, file_name) is not None:
            pkg_file_name = file_name
            break

    module.run_command(["pacman", "-U", "--noconfirm"] + install_options + [pkg_file_name], check_rc=True, cwd=pkgbuild_dir)
    return True


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        pkgbuild_dir=dict(type='str', required=True),
        action=dict(type='str', choices=['build', 'install'], default='build'),
        install_options=dict(type='list', elements='str', default=[])
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(changed=False)

    if module.check_mode:
        module.exit_json(**result)

    os.chdir(module.params['pkgbuild_dir'])
    result["changed"] = build_package(module.params['pkgbuild_dir'], module)

    if module.params['action'] == "install":
        result["changed"] = result["changed"] or install_package(module.params['pkgbuild_dir'], module.params['install_options'], module)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
