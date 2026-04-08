---
name: ssl-letsencrypt
description: Obtain and auto-renew Let's Encrypt SSL certificates for Apache/Nginx with HSTS and redirect
user-invocable: true
---

## Certificate Provisioning

**Method:** Certbot with webroot or standalone plugin
**Wildcard:** use DNS challenge via Cloudflare plugin for `*.domain.com` certs

## Apache Setup Steps
```bash
# Install certbot + Apache plugin
apt install -y certbot python3-certbot-apache

# Obtain certificate (auto-configures Apache redirect + SSL vhost)
certbot --apache -d domain.com -d www.domain.com \
  --non-interactive --agree-tos --email admin@domain.com

# Verify auto-renew
certbot renew --dry-run
```

## Required SSL Configuration (Apache vhost)
```apache
SSLEngine on
SSLProtocol TLSv1.2 TLSv1.3
SSLHonorCipherOrder off
SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "SAMEORIGIN"
```

## Renewal Automation
- Certbot installs cron/systemd timer automatically — verify with `systemctl list-timers | grep certbot`
- Add post-renewal hook to reload Apache: `/etc/letsencrypt/renewal-hooks/post/reload-apache.sh`
- Alert if cert expires in < 14 days (add to monitoring)

## Multi-Domain / Wildcard
- Standard: list all domains with `-d` flags
- Wildcard (`*.domain.com`): use `--dns-cloudflare` plugin, provide API token
- SAN order: primary domain first

## Output Expectations
- Certificate obtained: `certbot certificates` shows domain + expiry
- HTTPS redirect working: `curl -I http://domain.com` → 301 to https
- HSTS header present: `curl -I https://domain.com | grep Strict`
- SSL Labs grade: minimum A (A+ with HSTS preload)

## Quality Criteria
- TLS 1.0/1.1 disabled — verify with `openssl s_client -tls1 domain.com` → handshake failure
- Certificate chain complete: no intermediate cert missing
- Auto-renew timer active before marking task complete
