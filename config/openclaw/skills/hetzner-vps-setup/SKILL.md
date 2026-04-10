---
name: hetzner-vps-setup
description: Provision and harden a Hetzner Cloud VPS with SSH, firewall, and initial service stack
user-invocable: true
---

## Provisioning Steps

**Pre-conditions:** Hetzner API token available, SSH key registered, target datacenter confirmed (fsn1/nbg1/hel1)

1. **Create server** via Hetzner MCP: type cx42 default, Ubuntu 24.04 LTS, assign existing SSH key
2. **Allocate Primary IP** separately (enables IP reassignment without server recreate)
3. **Firewall rules** (create + assign immediately after server creation):
   - Allow: 22/tcp (SSH, restrict to operator IP range if possible)
   - Allow: 80/tcp, 443/tcp (HTTP/HTTPS)
   - Allow: 25, 465, 587, 993, 995/tcp (Mailcow if mail server)
   - Deny: all other inbound
4. **SSH hardening** (`/etc/ssh/sshd_config`):
   - `PasswordAuthentication no`
   - `PermitRootLogin prohibit-password`
   - `MaxAuthTries 3`
5. **Base packages:** `fail2ban`, `unattended-upgrades`, `ufw`, `curl`, `git`, `htop`
6. **Docker install:** official Docker repo, `docker-compose-plugin` (not standalone)
7. **DNS record** update via Cloudflare MCP: A record → new server IP, TTL 300

## CRITICAL: Hetzner-Specific Rules
- Always use `list_servers` before `get_server` — IDs differ from UI display
- Primary IP swap requires server power-off first
- IPv6 abuse blocks are separate from IPv4 — check both
- New IP: update `DEPLOY_HOST` GitHub secret, update MEMORY.md

## Output Expectations
- Server ID, IPv4, datacenter confirmed
- Firewall rule IDs listed
- SSH connectivity verified: `ssh root@<ip> whoami` returns `root`
- Docker version confirmed: `docker --version`

## Quality Criteria
- `fail2ban` active: `systemctl is-active fail2ban` → active
- Unattended upgrades enabled: `unattended-upgrades --dry-run` succeeds
- Port scan (nmap): only 22, 80, 443 open externally
