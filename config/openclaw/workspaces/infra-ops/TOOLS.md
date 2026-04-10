# infra-ops — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| bash | ssh, docker, git, curl, systemctl | PROD-SAFE korlatok! |
| read | Config fajlok, logok | Korlatlan |
| exec | Szerver parancsok | Megerosites destruktiv muveletekhez |

## Bash korlatozasok — STRICT
- ENGEDELYEZETT: ssh, scp, rsync, docker, docker-compose, git, curl, systemctl, certbot, ufw
- TILTOTT PARANCSOK (hardblock):
  - rm -rf / (root torlese)
  - mkfs (filesystem formatalas)
  - dd if= (disk write)
  - shutdown, reboot, init 0 (kiveve explicit keres)
  - iptables -F (firewall flush)
  - passwd (jelszo modositas)
  - chmod 777 (tul terlekeny jogosultsag)
- Timeout: 180s (hosszabb deploy-okhoz)

## PROD-SAFE protokoll
1. Valtozas elott: backup keszitese (config, DB, volume)
2. Valtozas: minimalis, atomikus
3. Valtozas utan: health check (curl, docker ps, systemctl status)
4. Hiba eseten: azonnali rollback a backup-bol

## Deploy checklist (kotelezeo)
- [ ] Backup keszult
- [ ] Rollback terv megvan
- [ ] Health check endpoint mukodik
- [ ] SSL certifikat valid
- [ ] DNS propagacio kesz
- [ ] Monitoring aktiv

## Sub-agent tool oroklodes
- server-provision: bash, read, exec (FULL)
- docker-stack: bash (docker only), read
- ssl-dns-mail: bash (certbot, dig), read
- live-verifier: bash (curl, wget), read (read-only)
