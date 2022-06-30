#!/usr/bin/python3

"""
Ansible stow module.

This script makes the connection between Ansible and GNU stow.
"""

import os

from ansible.module_utils.basic import AnsibleModule


def purge_conflicts(conflicts):
    """
    Delete a file or unlink a symlink conflicting with a package.

    :param list conflicts:
        Path of files or symlinks on the filesystem that conflicts with
        package files.

    :return:
         If the file is purged successfully, a None object is returned.
         If something goes wrong, a dictionary is returned containing
         the error message.
    :rtype: dict or null
    """
    try:
        for file in conflicts:
            if os.path.islink(file):
                os.unlink(file)
            else:
                os.remove(file)
    except Exception as err:  # noqa: disable=broad-except
        return {'message': f'unable to purge file "{file}"; error: {str(err)}'}

    return None


def stow_has_conflicts(module, package, cmd):
    """
    Verify if a package has any conflicting files.

    :param AnsibleModule module:
        The Ansible module object.

    :param str package:
        The name of the package to be un/re/stowed.

    :param str cmd:
        The complete stow command, with all flags and arguments, to be
        executed in dry-run mode (no change is made on the filesystem).

    :return:
        If a conflict is found returns a dictionary. Otherwise returns
        None.

        The dictionary can be recoverable (i.e., conflicts on
        pre-existing files and symlinks on the filesystem) by having the
        list of files and the `recoverable` key set to `True`:

            >>> {
            ...     'recoverable': True,
            ...     'message': '...',
            ...     'files': ['/home/user/.bashrc',
            ...               '/home/user/.config/foo']
            ... }

        Or can be unrecoverable:

            >>> {
            ...     'recoverable': False,
            ...     'message': '...'
            ... }
    :rtype: dict or null
    """
    params = module.params

    # dry-run to check for conflicts
    cmd = f'{cmd} --no'
    rc, _, stderr = module.run_command(cmd)

    if rc == 0:
        return None

    # return code 2 means that the package points to a path that has a
    # directory on it therefore stow can't continue
    #
    # as it would be ricky to attempt to proceed, this scenario should be
    # handled manually by the user, hence it should return a non-recoverable
    # flag error
    if rc == 2:
        return {'recoverable': False, 'message': 'conflicting directory found'}

    conflicts = []

    # grab the conflicting files path.
    stderr_lines = stderr.split('\n')
    for sel in stderr_lines:
        if '* existing target is' in sel:
            conflict = sel.split(':')
            conflict = conflict[-1].strip()
            conflict = os.path.join(params['target'], conflict)

            conflicts.append(conflict)

    conff = ', '.join(f'"{f}"' for f in conflicts)
    msg = f'unable to stow package "{package}" to "{params["target"]}";' \
          + f' conflicted files: {conff}'

    return {'recoverable': True, 'message': msg, 'files': conflicts}


def stow(module, package, state):
    """
    Perform stow on a package against the filesystem.

    :param AnsibleModule module:
        The Ansible module object.

    :param str package:
        The name of the package to be un/re/stowed.

    :param str state:
        The desirable package state within the system.

    :return:
        A dictionary that contains an error flag, the returned message
        and wether something changed or not.
    :rtype: dict
    """
    params = module.params

    flag = ''
    if state in ('present', 'supress'):
        flag = '--stow'
    elif state == 'absent':
        flag = '--delete'
    elif state == 'latest':
        flag = '--restow'

    path = module.get_bin_path('stow', True)
    cmd = f'{path} {flag} {package} --target={params["target"]}' \
          + f' --dir={params["dir"]} --verbose'

    conflict = stow_has_conflicts(module, package, cmd)
    if conflict:
        if state != 'supress' or not conflict['recoverable']:
            return {'error': True, 'message': conflict['message']}

        err = purge_conflicts(conflict['files'])
        if err:
            return {'error': True, 'message': err['message']}

    # when increasing verbosity level with the "--verbose" flag, all output
    # will be sent to the standard error (stderr)
    #
    # stow is, by itself, an idempotent tool. If a given package is already
    # stowed, the tool will not perform again. If a package is succesfully
    # stowed, stow will output what have been done
    #
    # that's why "information on stderr" equals "something has changed"
    # (supposing execution passed all errors checking).
    rc, _, se = module.run_command(cmd)
    if rc != 0:
        msg = f'execution of command "{cmd}" failed with error code {rc};' \
              + f' output: "{se}"'
        return {'error': True, 'message': msg}

    return {'error': False, 'changed': (se != '')}


def main():
    """Instantiate the ansible module."""
    module = AnsibleModule(
        argument_spec={
            'dir': {'required': True, 'type': 'str'},
            'package': {'required': True, 'type': 'list'},
            'target': {
                'required': False,
                'type': 'str',
                'default': os.environ.get('HOME')
            },
            'state': {
                'required': True,
                'type': 'str',
                'choices': ['absent', 'present', 'latest', 'supress']
            },
        }
    )

    params = module.params

    has_changed = False

    for package in list(params['package']):
        ret = stow(module, package, params['state'])
        if ret['error']:
            module.fail_json(msg=ret['message'])

        has_changed = has_changed or ret['changed']

    module.exit_json(changed=has_changed)


if __name__ == '__main__':
    main()
