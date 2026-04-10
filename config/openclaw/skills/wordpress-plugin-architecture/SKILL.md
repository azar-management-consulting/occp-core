---
name: wordpress-plugin-architecture
description: Design and scaffold WordPress plugins following WPCS, OOP patterns, and security standards
user-invocable: true
---

## Architecture Standards

**PHP:** 8.3+, strict_types=1, PSR-4 autoloading via Composer
**Standards:** WordPress Coding Standards (WPCS), PHPStan level 6+

## Plugin Structure
```
plugin-name/
  plugin-name.php          # Main file: headers, bootstrap, version constants
  includes/
    class-plugin-name.php  # Core class: hooks registration
    class-admin.php        # Admin-only logic
    class-api.php          # REST API endpoints
  templates/               # Frontend templates (output only, no logic)
  assets/                  # JS/CSS (enqueued properly, versioned)
  languages/               # .pot file for i18n
  tests/                   # PHPUnit 11 tests
```

## Security Checklist (mandatory per PR)
- [ ] All user inputs: `wp_unslash()` + `sanitize_*()` appropriate function
- [ ] All outputs: `esc_html()`, `esc_attr()`, `esc_url()` context-aware
- [ ] All forms: `wp_nonce_field()` + `wp_verify_nonce()`
- [ ] All AJAX: `check_ajax_referer()` + `current_user_can()`
- [ ] All DB queries: `$wpdb->prepare()` — zero string concatenation
- [ ] Capability checks before all privileged operations

## Hook Design Rules
- Use namespaced hook names: `plugin_name/feature/action`
- `add_action` calls only in constructor or `init` hook
- Never call `add_action` from template files
- Deregister plugin on uninstall (cleanup DB options, custom tables)

## Output Expectations
- Full plugin scaffold with all files
- `README.md` with hooks documented
- PHPUnit bootstrap + at least 2 test cases (activation + a core function)

## Quality Criteria
- `phpcs --standard=WordPress` passes with zero errors
- PHPStan level 6 passes
- Plugin activates without PHP notices/warnings
