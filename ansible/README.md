# Ansible

Post-deployment configuration playbooks for Exousia hosts.

Ansible is used for **transient configuration only** (bootc best practice).
Persistent changes belong in the image overlay, not in Ansible.

## Structure

```text
ansible/
├── site.yml         # Main playbook
├── inventory/       # Host inventory
└── roles/
    ├── firewall/    # Firewalld zone and rule configuration
    ├── network/     # NetworkManager connection profiles
    ├── containers/  # Podman Quadlet service deployment
    ├── services/    # Systemd service enablement
    └── user_config/ # User-level configuration
```

## Usage

```bash
ansible-playbook -i ansible/inventory ansible/site.yml
```

## See Also

- [Ansible Docs](../docs/ansible.md) -- Detailed playbook documentation
