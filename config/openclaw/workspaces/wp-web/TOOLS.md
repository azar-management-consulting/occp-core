# wp-web — Allowed Tools

## Engedelyezett eszkozok
| Tool | Hasznalat | Korlat |
|------|-----------|--------|
| bash | wp-cli, composer, npm, git | Csak staging/dev kornyezetben |
| read | PHP/JS/CSS forrasfajlok | Korlatlan |
| write | Plugin/theme fajlok | Csak workspace + WP konyvtarak |
| edit | Letezo PHP/JS/CSS modositas | Preferal write helyett |
| browser | WP Codex, Elementor docs, plugin docs | Csak olvasas |

## Bash korlatozasok
- ENGEDELYEZETT: wp-cli (wp post, wp plugin, wp option), composer, npm, git, curl
- TILTOTT: wp db drop, wp site delete, rm -rf wp-content, force push
- WP-CLI: mindig --path= megadassal
- Timeout: 120s

## WordPress-specifikus szabalyok
- SQL: mindig $wpdb->prepare()
- REST API: register_rest_route() + permission_callback
- AJAX: check_ajax_referer() + current_user_can()
- Enqueueing: wp_enqueue_script/style, soha ne inline
- Nonce: wp_nonce_field() + wp_verify_nonce()

## Sub-agent tool oroklodes
- elementor-builder: read, write, edit, browser (NO bash)
- wp-debugger: +exec (debug log olvasashoz)
- seo-page-optimizer: read, browser (read-only)
