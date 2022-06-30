# Ansible Role: stow

Ansible role that installs [GNU Stow](https://www.gnu.org/software/stow).

## Requirements

None.

## Role Variables

Available variables are listed below (see `defaults/main.yml` for default
values):

- `stow_packages`: List of packages necessary to install stow.

## Use with Ansible


```yaml
- hosts: all
  become: true

  roles:
    - role: stow
```

## Dependencies

None.

## Author Information

This role was created in 2022 by Tiago Martins.
