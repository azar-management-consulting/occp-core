---
name: wp-rest-endpoint
description: Create secure, versioned WordPress REST API endpoints with authentication and schema validation
user-invocable: true
---

## Implementation Standards

**Registration:** always in `rest_api_init` hook, never `init`
**Namespace format:** `plugin-name/v1`
**Authentication:** Application Passwords for external clients, nonce for logged-in frontend

## Endpoint Scaffold
```php
register_rest_route( 'plugin-name/v1', '/resource/(?P<id>\d+)', [
    'methods'             => WP_REST_Request::METHOD_GET,
    'callback'            => [ $this, 'get_resource' ],
    'permission_callback' => [ $this, 'check_permission' ],
    'args'                => [
        'id' => [
            'required'          => true,
            'type'              => 'integer',
            'sanitize_callback' => 'absint',
            'validate_callback' => fn($v) => $v > 0,
        ],
    ],
] );
```

## Security Requirements
- `permission_callback` must NEVER return `__return_true` in production
- All write endpoints: verify `current_user_can()` with specific capability
- Schema validation via `args` array — no manual `isset()` checking
- Response: use `WP_REST_Response` with explicit HTTP status codes
- Rate limiting: add `X-RateLimit-*` headers via custom middleware

## Input/Output Standards
- Input: `$request->get_param()` only — never `$_GET`/`$_POST` directly
- Output: `rest_ensure_response()` wrapping array — never `echo` or `wp_send_json()`
- Errors: `WP_Error` with code, message, HTTP status (e.g., `rest_forbidden`, 403)
- Collections: include `total`, `total_pages`, `per_page` headers

## Output Expectations
- Full endpoint registration code
- Permission callback implementation
- Schema args array with sanitize/validate for all parameters
- Example `curl` call for documentation

## Quality Criteria
- Endpoint appears correctly in `/wp-json/` schema
- PHPStan level 6 passes on endpoint class
- Works with `--user login:application_password` curl auth
