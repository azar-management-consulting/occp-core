-- OM Core Schema v1.0 · 2026-04-20 · migrations 0001
-- Országos Média (OM) Content Intelligence Layer
-- Target: Supabase (Postgres 16+) · pgvector 0.8+ · pg_cron · pgmq 1.x
-- Author: supabase-data-engineer (OCCP Brain)
-- Idempotent DDL · RLS on every table · HNSW on all embedding columns
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. EXTENSIONS
-- ─────────────────────────────────────────────────────────────────────────────
create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";
create extension if not exists "vector";
create extension if not exists "pg_cron";
create extension if not exists "pgmq" cascade;
create extension if not exists "pg_stat_statements";
create extension if not exists "pg_trgm";

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. SCHEMAS
-- ─────────────────────────────────────────────────────────────────────────────
create schema if not exists om;
comment on schema om is 'Országos Média content intelligence layer — canonical source of truth';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. ENUM TYPES
-- ─────────────────────────────────────────────────────────────────────────────
do $$ begin
  create type om.article_status as enum (
    'raw', 'normalized', 'deduped', 'canonical', 'rejected', 'archived'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.derivative_role as enum ('news', 'blog', 'forum', 'hub', 'sponsored');
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.publish_status as enum (
    'queued', 'processing', 'drafted', 'published', 'failed', 'cancelled', 'scheduled'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.guard_verdict as enum ('pass', 'warn', 'fail', 'block', 'manual_review');
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.agent_role as enum (
    'system_architect', 'wp_mainwp_engineer', 'supabase_data_engineer',
    'ai_content_orchestrator', 'seo_geo_strategist', 'internal_link_graph_engineer',
    'qa_verifier', 'security_governance', 'migration_release', 'observability',
    'forum_automation', 'blog_structure', 'media_hub', 'news_routing',
    'design_system', 'prompt_author', 'orchestrator'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.source_kind as enum ('rss', 'api', 'scrape', 'social', 'newsletter', 'manual');
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.domain_cluster as enum ('orszagos', 'varosi', 'blog', 'forum', 'media', 'hir', 'tematikus');
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.relation_type as enum (
    'related', 'source', 'canonical', 'hub', 'city_hub', 'topic_hub', 'follow_up', 'contradicts'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.ad_format as enum (
    'display_leaderboard', 'display_rectangle', 'display_skyscraper',
    'sticky_bottom', 'in_article', 'native_card', 'sponsored_post',
    'newsletter_slot', 'push_slot', 'video_preroll'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.subscription_tier as enum ('free', 'basic', 'premium', 'enterprise');
exception when duplicate_object then null; end $$;

do $$ begin
  create type om.subscription_status as enum ('trial', 'active', 'past_due', 'cancelled', 'expired');
exception when duplicate_object then null; end $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. UTILITY: updated_at trigger function
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function om.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function om.set_updated_at() is 'Auto-update updated_at timestamp on row UPDATE';

-- Helper: content hash normalizer
create or replace function om.content_hash(txt text)
returns text
language sql
immutable
as $$
  select encode(digest(lower(regexp_replace(coalesce(txt,''), '\s+', ' ', 'g')), 'sha256'), 'hex');
$$;

comment on function om.content_hash(text) is 'SHA-256 of whitespace-normalized lowercase text (dedup key)';

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. TABLES (dependency-ordered)
-- ─────────────────────────────────────────────────────────────────────────────

-- 5.1 domain_role — 139 child site inventory
create table if not exists om.domain_role (
  id            uuid primary key default gen_random_uuid(),
  domain        text not null unique check (domain ~ '^[a-z0-9.-]+\.[a-z]{2,}$'),
  cluster       om.domain_cluster not null,
  role          text not null,
  parent_domain text,
  city          text,
  county        text,
  topic_primary text,
  mainwp_group  text,
  wp_version    text,
  active        boolean not null default true,
  metadata      jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  created_by    uuid,
  updated_by    uuid,
  deleted_at    timestamptz
);
comment on table om.domain_role is '139 OM child sites — cluster, role, geo, topic mapping';
comment on column om.domain_role.cluster is 'High-level bucket: orszagos/varosi/blog/forum/media/hir/tematikus';
comment on column om.domain_role.parent_domain is 'Hub domain this satellite feeds from/into';

create index if not exists idx_domain_role_cluster on om.domain_role(cluster) where deleted_at is null;
create index if not exists idx_domain_role_city    on om.domain_role(city) where deleted_at is null;
create index if not exists idx_domain_role_county  on om.domain_role(county) where deleted_at is null;
create index if not exists idx_domain_role_meta    on om.domain_role using gin(metadata);

-- 5.2 sources — upstream content providers
create table if not exists om.sources (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  kind        om.source_kind not null,
  base_url    text check (base_url is null or base_url ~ '^https?://'),
  language    text not null default 'hu',
  country     text not null default 'HU',
  credibility_score numeric(3,2) not null default 0.50 check (credibility_score between 0 and 1),
  paywall     boolean not null default false,
  active      boolean not null default true,
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  created_by  uuid,
  updated_by  uuid,
  deleted_at  timestamptz,
  unique (name, kind)
);
comment on table om.sources is 'Upstream content providers (RSS, API, scrape, social)';

create index if not exists idx_sources_kind on om.sources(kind) where deleted_at is null and active;
create index if not exists idx_sources_meta on om.sources using gin(metadata);

-- 5.3 source_feeds — concrete feed endpoints per source
create table if not exists om.source_feeds (
  id           uuid primary key default gen_random_uuid(),
  source_id    uuid not null references om.sources(id) on delete cascade,
  feed_url     text not null check (feed_url ~ '^https?://'),
  feed_kind    text not null default 'rss',
  topic_hint   text,
  poll_interval_seconds int not null default 900 check (poll_interval_seconds >= 60),
  last_polled_at timestamptz,
  last_status  text,
  active       boolean not null default true,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  deleted_at   timestamptz,
  unique (source_id, feed_url)
);
comment on table om.source_feeds is 'Concrete feed URLs with polling schedule';

create index if not exists idx_source_feeds_source on om.source_feeds(source_id);
create index if not exists idx_source_feeds_poll   on om.source_feeds(last_polled_at) where active;

-- 5.4 raw_articles — untouched fetch payload
create table if not exists om.raw_articles (
  id          uuid primary key default gen_random_uuid(),
  source_id   uuid not null references om.sources(id) on delete cascade,
  feed_id     uuid references om.source_feeds(id) on delete set null,
  source_url  text not null check (source_url ~ '^https?://'),
  fetched_at  timestamptz not null default now(),
  http_status int,
  raw_html    text,
  raw_text    text,
  raw_json    jsonb,
  headers     jsonb,
  fetch_hash  text not null,
  processing_error text,
  status      om.article_status not null default 'raw',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz,
  unique (source_id, fetch_hash)
);
comment on table om.raw_articles is 'Untouched upstream payload — immutable audit trail';

create index if not exists idx_raw_articles_source on om.raw_articles(source_id);
create index if not exists idx_raw_articles_url    on om.raw_articles using hash (source_url);
create index if not exists idx_raw_articles_status on om.raw_articles(status) where deleted_at is null;
create index if not exists idx_raw_articles_json   on om.raw_articles using gin(raw_json);

-- 5.5 normalized_articles — readability-processed text
create table if not exists om.normalized_articles (
  id              uuid primary key default gen_random_uuid(),
  raw_id          uuid not null references om.raw_articles(id) on delete cascade,
  source_id       uuid not null references om.sources(id) on delete cascade,
  title           text not null,
  subtitle        text,
  body_text       text not null,
  body_html       text,
  author          text,
  published_at    timestamptz,
  language        text not null default 'hu',
  word_count      int generated always as (array_length(regexp_split_to_array(body_text, '\s+'), 1)) stored,
  content_hash    text not null,
  reading_minutes int generated always as (greatest(1, ceil(array_length(regexp_split_to_array(body_text, '\s+'), 1)::numeric / 220))::int) stored,
  image_urls      text[] default '{}'::text[],
  status          om.article_status not null default 'normalized',
  metadata        jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  unique (content_hash)
);
comment on table om.normalized_articles is 'Readability-cleaned text, generated word_count/reading_minutes';
comment on column om.normalized_articles.content_hash is 'SHA-256 of normalized body — exact dedup key (stage 1)';

create index if not exists idx_norm_articles_raw      on om.normalized_articles(raw_id);
create index if not exists idx_norm_articles_source   on om.normalized_articles(source_id);
create index if not exists idx_norm_articles_pub      on om.normalized_articles(published_at desc nulls last);
create index if not exists idx_norm_articles_status   on om.normalized_articles(status) where deleted_at is null;
create index if not exists idx_norm_articles_title    on om.normalized_articles using gin(title gin_trgm_ops);
create index if not exists idx_norm_articles_meta     on om.normalized_articles using gin(metadata);

-- 5.6 article_entities — NER output per normalized article
create table if not exists om.article_entities (
  id             uuid primary key default gen_random_uuid(),
  article_id     uuid not null references om.normalized_articles(id) on delete cascade,
  entity_type    text not null check (entity_type in ('PER','ORG','LOC','GPE','EVENT','PRODUCT','MISC')),
  entity_value   text not null,
  normalized_form text,
  confidence     numeric(3,2) check (confidence between 0 and 1),
  char_start     int,
  char_end       int,
  created_at     timestamptz not null default now()
);
comment on table om.article_entities is 'NER extraction (spaCy hu_core_news_lg)';

create index if not exists idx_article_entities_article on om.article_entities(article_id);
create index if not exists idx_article_entities_value   on om.article_entities(entity_type, normalized_form);

-- 5.7 article_locations — geo-annotated mentions
create table if not exists om.article_locations (
  id             uuid primary key default gen_random_uuid(),
  article_id     uuid not null references om.normalized_articles(id) on delete cascade,
  city           text,
  county         text,
  country        text default 'HU',
  lat            numeric(9,6),
  lon            numeric(9,6),
  confidence     numeric(3,2) check (confidence between 0 and 1),
  is_primary     boolean not null default false,
  created_at     timestamptz not null default now()
);
comment on table om.article_locations is 'Geo-annotated location mentions, is_primary marks lead location';

create index if not exists idx_article_locations_article on om.article_locations(article_id);
create index if not exists idx_article_locations_city    on om.article_locations(city);
create index if not exists idx_article_locations_county  on om.article_locations(county);
create index if not exists idx_article_locations_primary on om.article_locations(article_id) where is_primary;

-- 5.8 article_topics — topic classification
create table if not exists om.article_topics (
  id          uuid primary key default gen_random_uuid(),
  article_id  uuid not null references om.normalized_articles(id) on delete cascade,
  topic       text not null,
  topic_slug  text not null,
  confidence  numeric(3,2) check (confidence between 0 and 1),
  is_primary  boolean not null default false,
  created_at  timestamptz not null default now(),
  unique (article_id, topic_slug)
);
comment on table om.article_topics is 'Topic classification output (politics, sport, travel, ...)';

create index if not exists idx_article_topics_topic   on om.article_topics(topic_slug);
create index if not exists idx_article_topics_primary on om.article_topics(article_id) where is_primary;

-- 5.9 canonical_assets — single source of truth per story
create table if not exists om.canonical_assets (
  id                uuid primary key default gen_random_uuid(),
  normalized_id     uuid references om.normalized_articles(id) on delete set null,
  title             text not null,
  slug              text not null,
  summary           text,
  body_text         text not null,
  canonical_url     text not null check (canonical_url ~ '^https?://'),
  content_hash      text not null,
  embedding         vector(1536),
  topic_primary_id  uuid,
  topic_primary     text,
  city_id           uuid,
  city              text,
  county_id         uuid,
  county            text,
  published_at      timestamptz,
  first_seen_at     timestamptz not null default now(),
  last_updated_at   timestamptz not null default now(),
  credibility       numeric(3,2) default 0.50 check (credibility between 0 and 1),
  freshness_score   numeric(3,2) default 1.00 check (freshness_score between 0 and 1),
  merged_from       uuid[] default '{}'::uuid[],
  metadata          jsonb not null default '{}'::jsonb,
  status            om.article_status not null default 'canonical',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  created_by        uuid,
  updated_by        uuid,
  deleted_at        timestamptz,
  unique (content_hash),
  unique (slug)
);
comment on table om.canonical_assets is 'Canonical story — single source of truth, dedup cluster head';
comment on column om.canonical_assets.embedding is 'OpenAI text-embedding-3-small (1536 dim) for semantic dedup';
comment on column om.canonical_assets.merged_from is 'normalized_article_ids absorbed into this canonical during dedup';

create index if not exists idx_canonical_pub       on om.canonical_assets(published_at desc nulls last) where deleted_at is null;
create index if not exists idx_canonical_city      on om.canonical_assets(city) where deleted_at is null;
create index if not exists idx_canonical_county    on om.canonical_assets(county) where deleted_at is null;
create index if not exists idx_canonical_topic     on om.canonical_assets(topic_primary) where deleted_at is null;
create index if not exists idx_canonical_title_trgm on om.canonical_assets using gin(title gin_trgm_ops);
create index if not exists idx_canonical_meta      on om.canonical_assets using gin(metadata);
create index if not exists idx_canonical_embedding on om.canonical_assets
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- 5.10 derivative_assets — role-specific rewrites per target domain
create table if not exists om.derivative_assets (
  id                    uuid primary key default gen_random_uuid(),
  canonical_id          uuid not null references om.canonical_assets(id) on delete cascade,
  target_domain         text not null references om.domain_role(domain) on delete cascade,
  role                  om.derivative_role not null,
  narrative             text,
  title                 text not null,
  slug                  text not null,
  body_text             text not null,
  body_html             text,
  excerpt               text,
  execution_directives  jsonb not null default '{}'::jsonb,
  rewrite_profile       text not null,
  prompt_version        int,
  model_used            text,
  token_usage           jsonb,
  embedding             vector(1536),
  schema_type           text default 'NewsArticle',
  rel_canonical_to      text check (rel_canonical_to is null or rel_canonical_to ~ '^https?://'),
  publish_state         om.publish_status not null default 'queued',
  wp_post_id            bigint,
  wp_post_url           text,
  quality_score         numeric(3,2) check (quality_score is null or quality_score between 0 and 1),
  guard_verdict         om.guard_verdict,
  metadata              jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  created_by            uuid,
  updated_by            uuid,
  deleted_at            timestamptz,
  unique (canonical_id, target_domain, role)
);
comment on table om.derivative_assets is 'Role-specific rewrite per target domain (news/blog/forum/hub)';
comment on column om.derivative_assets.execution_directives is 'Rewrite plan JSON: tone, length, structure, forbidden_phrases, required_facts';
comment on column om.derivative_assets.rel_canonical_to is 'If set, emit rel=canonical pointing to this URL (satellite mode)';

create index if not exists idx_deriv_canonical   on om.derivative_assets(canonical_id);
create index if not exists idx_deriv_target      on om.derivative_assets(target_domain);
create index if not exists idx_deriv_role        on om.derivative_assets(role);
create index if not exists idx_deriv_state       on om.derivative_assets(publish_state) where deleted_at is null;
create index if not exists idx_deriv_meta        on om.derivative_assets using gin(metadata);
create index if not exists idx_deriv_embedding   on om.derivative_assets
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- 5.11 prompt_registry — versioned rewrite prompts
create table if not exists om.prompt_registry (
  id              uuid primary key default gen_random_uuid(),
  name            text not null,
  version         int not null check (version >= 1),
  body            text not null,
  checksum        text not null,
  parent_version  int,
  description     text,
  metadata        jsonb not null default '{}'::jsonb,
  win_rate        numeric(4,3) not null default 0 check (win_rate between 0 and 1),
  runs_count      int not null default 0 check (runs_count >= 0),
  promoted        boolean not null default false,
  promoted_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  created_by      uuid,
  deleted_at      timestamptz,
  unique (name, version)
);
comment on table om.prompt_registry is 'Versioned rewrite/agent prompts, self-improvement loop target';

create index if not exists idx_prompt_promoted on om.prompt_registry(name) where promoted = true and deleted_at is null;
create index if not exists idx_prompt_meta     on om.prompt_registry using gin(metadata);

-- 5.12 generation_runs — per-derivative generation attempt
create table if not exists om.generation_runs (
  id               uuid primary key default gen_random_uuid(),
  derivative_id    uuid references om.derivative_assets(id) on delete cascade,
  canonical_id     uuid references om.canonical_assets(id) on delete set null,
  prompt_id        uuid references om.prompt_registry(id) on delete set null,
  model            text not null,
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  duration_ms      int generated always as (
    case when finished_at is null then null
    else (extract(epoch from (finished_at - started_at)) * 1000)::int end
  ) stored,
  prompt_tokens    int,
  completion_tokens int,
  total_tokens     int,
  cost_usd         numeric(10,6),
  success          boolean,
  error_class      text,
  error_message    text,
  output_hash      text,
  metadata         jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now()
);
comment on table om.generation_runs is 'Per-derivative LLM generation audit log (tokens, cost, timing)';

create index if not exists idx_genruns_derivative on om.generation_runs(derivative_id);
create index if not exists idx_genruns_canonical  on om.generation_runs(canonical_id);
create index if not exists idx_genruns_started    on om.generation_runs(started_at desc);
create index if not exists idx_genruns_success    on om.generation_runs(success) where success is not null;

-- 5.13 publication_targets — routing matrix output (which canonical → which domain)
create table if not exists om.publication_targets (
  id             uuid primary key default gen_random_uuid(),
  canonical_id   uuid not null references om.canonical_assets(id) on delete cascade,
  target_domain  text not null references om.domain_role(domain) on delete cascade,
  role           om.derivative_role not null,
  priority       int not null default 100 check (priority between 1 and 1000),
  rewrite_profile text not null,
  reason         text,
  scheduled_at   timestamptz,
  resolved_at    timestamptz,
  derivative_id  uuid references om.derivative_assets(id) on delete set null,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  deleted_at     timestamptz,
  unique (canonical_id, target_domain, role)
);
comment on table om.publication_targets is 'Routing engine output — which canonical targets which domain/role';

create index if not exists idx_pubtargets_canonical on om.publication_targets(canonical_id);
create index if not exists idx_pubtargets_domain    on om.publication_targets(target_domain);
create index if not exists idx_pubtargets_sched     on om.publication_targets(scheduled_at) where resolved_at is null;

-- 5.14 publish_queue — pgmq-backed outbox to MainWP/WP REST
create table if not exists om.publish_queue (
  id             uuid primary key default gen_random_uuid(),
  queue_id       bigint,
  derivative_id  uuid not null references om.derivative_assets(id) on delete cascade,
  canonical_id   uuid not null references om.canonical_assets(id) on delete cascade,
  target_domain  text not null references om.domain_role(domain) on delete cascade,
  scheduled_at   timestamptz not null default now(),
  attempts       int not null default 0 check (attempts >= 0),
  max_attempts   int not null default 5,
  last_attempt_at timestamptz,
  last_error     text,
  state          om.publish_status not null default 'queued',
  wp_post_id     bigint,
  wp_post_url    text,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
comment on table om.publish_queue is 'Outbox table mirrored by pgmq queue om_publish — state machine to WP publish';
comment on column om.publish_queue.queue_id is 'Matching pgmq message id (om_publish queue)';

create index if not exists idx_pubq_state on om.publish_queue(state);
create index if not exists idx_pubq_sched on om.publish_queue(scheduled_at) where state in ('queued','scheduled');
create index if not exists idx_pubq_domain on om.publish_queue(target_domain);

-- Create pgmq queue (idempotent)
do $$ begin
  perform pgmq.create('om_publish');
exception when others then null; end $$;

-- 5.15 interlink_graph — internal link graph (from_url, to_url composite PK)
create table if not exists om.interlink_graph (
  from_url       text not null check (from_url ~ '^https?://'),
  to_url         text not null check (to_url ~ '^https?://'),
  anchor         text not null,
  weight         numeric(4,3) not null default 1.000 check (weight between 0 and 1),
  relation_type  om.relation_type not null default 'related',
  from_domain    text,
  to_domain      text,
  from_canonical_id uuid references om.canonical_assets(id) on delete set null,
  to_canonical_id   uuid references om.canonical_assets(id) on delete set null,
  active         boolean not null default true,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  deleted_at     timestamptz,
  primary key (from_url, to_url)
);
comment on table om.interlink_graph is 'Internal link graph — from_url+to_url composite PK, weekly cron rebuild';

create index if not exists idx_interlink_from_domain on om.interlink_graph(from_domain);
create index if not exists idx_interlink_to_domain   on om.interlink_graph(to_domain);
create index if not exists idx_interlink_relation    on om.interlink_graph(relation_type);
create index if not exists idx_interlink_from_canon  on om.interlink_graph(from_canonical_id);
create index if not exists idx_interlink_to_canon    on om.interlink_graph(to_canonical_id);

-- 5.16 audit_logs — structured audit trail
create table if not exists om.audit_logs (
  id           uuid primary key default gen_random_uuid(),
  event_type   text not null,
  entity_type  text not null,
  entity_id    uuid,
  actor        text,
  actor_role   om.agent_role,
  action       text not null,
  before_state jsonb,
  after_state  jsonb,
  diff         jsonb,
  severity     text not null default 'info' check (severity in ('debug','info','warn','error','critical')),
  request_id   uuid,
  ip_addr      inet,
  user_agent   text,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
comment on table om.audit_logs is 'Structured audit trail — all mutations, entity changes, privileged actions';

create index if not exists idx_audit_entity   on om.audit_logs(entity_type, entity_id);
create index if not exists idx_audit_event    on om.audit_logs(event_type);
create index if not exists idx_audit_actor    on om.audit_logs(actor);
create index if not exists idx_audit_created  on om.audit_logs(created_at desc);
create index if not exists idx_audit_severity on om.audit_logs(severity) where severity in ('error','critical');

-- 5.17 error_events — errors surfaced from agents/pipeline
create table if not exists om.error_events (
  id           uuid primary key default gen_random_uuid(),
  source       text not null,
  error_class  text not null,
  error_message text not null,
  stack_trace  text,
  entity_type  text,
  entity_id    uuid,
  request_id   uuid,
  agent_role   om.agent_role,
  severity     text not null default 'error' check (severity in ('warn','error','critical','fatal')),
  resolved     boolean not null default false,
  resolved_at  timestamptz,
  resolved_by  text,
  resolution_notes text,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
comment on table om.error_events is 'Errors thrown by agents/edge functions/pipelines, with resolution workflow';

create index if not exists idx_errors_class     on om.error_events(error_class);
create index if not exists idx_errors_unresolved on om.error_events(created_at desc) where not resolved;
create index if not exists idx_errors_severity  on om.error_events(severity);
create index if not exists idx_errors_agent     on om.error_events(agent_role);

-- 5.18 agent_prompts — per-agent canonical prompt body + version history
create table if not exists om.agent_prompts (
  id              uuid primary key default gen_random_uuid(),
  name            text not null,
  agent_role      om.agent_role not null,
  version         int not null check (version >= 1),
  body            text not null,
  checksum        text not null,
  parent_version  int,
  tools_allowed   text[],
  model_preferred text,
  metadata        jsonb not null default '{}'::jsonb,
  win_rate        numeric(4,3) not null default 0 check (win_rate between 0 and 1),
  runs_count      int not null default 0,
  promoted        boolean not null default false,
  promoted_at     timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  unique (name, version)
);
comment on table om.agent_prompts is 'Per-agent system prompt body, versioned, win_rate tracked for self-improvement';

create index if not exists idx_agent_prompts_promoted on om.agent_prompts(name) where promoted = true;
create index if not exists idx_agent_prompts_role     on om.agent_prompts(agent_role);

-- 5.19 agent_runs — one row per agent task execution
create table if not exists om.agent_runs (
  id              uuid primary key default gen_random_uuid(),
  run_id          uuid not null,
  wave_id         text,
  agent_role      om.agent_role not null,
  agent_name      text not null,
  prompt_id       uuid references om.agent_prompts(id) on delete set null,
  prompt_version  int,
  parent_run_id   uuid references om.agent_runs(id) on delete set null,
  task_summary    text,
  status          text not null default 'pending' check (status in ('pending','running','success','failed','timeout','cancelled','escalated')),
  started_at      timestamptz,
  finished_at     timestamptz,
  duration_ms     int,
  model           text,
  prompt_tokens   int,
  completion_tokens int,
  total_tokens    int,
  cost_usd        numeric(10,6),
  retries         int not null default 0,
  error_message   text,
  output_summary  text,
  metadata        jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
comment on table om.agent_runs is 'One row per agent task execution — feeds win_rate calculation';

create index if not exists idx_agent_runs_run    on om.agent_runs(run_id);
create index if not exists idx_agent_runs_role   on om.agent_runs(agent_role);
create index if not exists idx_agent_runs_status on om.agent_runs(status);
create index if not exists idx_agent_runs_parent on om.agent_runs(parent_run_id);
create index if not exists idx_agent_runs_time   on om.agent_runs(started_at desc);

-- 5.20 agent_events — fine-grained agent event stream (tool calls, MCP, hooks)
create table if not exists om.agent_events (
  id            uuid primary key default gen_random_uuid(),
  run_id        uuid references om.agent_runs(id) on delete cascade,
  event_kind    text not null check (event_kind in (
    'tool_call','tool_result','mcp_call','mcp_result','hook_fire',
    'model_prompt','model_response','checkpoint','escalation','log'
  )),
  tool_name     text,
  mcp_server    text,
  payload       jsonb,
  payload_hash  text,
  duration_ms   int,
  success       boolean,
  error_message text,
  created_at    timestamptz not null default now()
);
comment on table om.agent_events is 'Fine-grained per-event stream from agent executions (tool/MCP/hook)';

create index if not exists idx_agent_events_run  on om.agent_events(run_id);
create index if not exists idx_agent_events_kind on om.agent_events(event_kind);
create index if not exists idx_agent_events_time on om.agent_events(created_at desc);
create index if not exists idx_agent_events_payload on om.agent_events using gin(payload);

-- 5.21 ad_inventory — ad units available across network
create table if not exists om.ad_inventory (
  id            uuid primary key default gen_random_uuid(),
  unit_code     text not null unique,
  name          text not null,
  format        om.ad_format not null,
  width         int,
  height        int,
  domain        text references om.domain_role(domain) on delete cascade,
  role_scope    om.derivative_role,
  floor_price_huf numeric(10,2) not null default 0 check (floor_price_huf >= 0),
  active        boolean not null default true,
  prebid_enabled boolean not null default false,
  metadata      jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
comment on table om.ad_inventory is 'Ad units catalog — display/native/sponsored/newsletter/push slots';

create index if not exists idx_adinv_domain on om.ad_inventory(domain);
create index if not exists idx_adinv_format on om.ad_inventory(format);
create index if not exists idx_adinv_active on om.ad_inventory(active) where active;

-- 5.22 ad_placements — actual bookings/campaigns
create table if not exists om.ad_placements (
  id              uuid primary key default gen_random_uuid(),
  inventory_id    uuid not null references om.ad_inventory(id) on delete cascade,
  advertiser_name text not null,
  campaign_name   text,
  creative_url    text check (creative_url is null or creative_url ~ '^https?://'),
  click_url       text check (click_url is null or click_url ~ '^https?://'),
  start_at        timestamptz not null,
  end_at          timestamptz not null,
  budget_huf      numeric(12,2) check (budget_huf is null or budget_huf >= 0),
  impressions_target bigint,
  impressions_served bigint not null default 0,
  clicks_served   bigint not null default 0,
  revenue_huf     numeric(12,2) not null default 0,
  state           text not null default 'scheduled' check (state in ('scheduled','active','paused','ended','cancelled')),
  targeting       jsonb not null default '{}'::jsonb,
  metadata        jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  check (end_at > start_at)
);
comment on table om.ad_placements is 'Booked campaigns per inventory unit — drives Revive/Prebid decisioning';

create index if not exists idx_adplace_inv    on om.ad_placements(inventory_id);
create index if not exists idx_adplace_state  on om.ad_placements(state) where deleted_at is null;
create index if not exists idx_adplace_window on om.ad_placements(start_at, end_at);
create index if not exists idx_adplace_target on om.ad_placements using gin(targeting);

-- 5.23 subscriptions — premium ad-free subscriber records
create table if not exists om.subscriptions (
  id             uuid primary key default gen_random_uuid(),
  user_email     text not null check (user_email ~ '^[^@]+@[^@]+\.[^@]+$'),
  user_id_ext    text,
  tier           om.subscription_tier not null default 'basic',
  status         om.subscription_status not null default 'trial',
  price_huf      numeric(10,2) not null default 990,
  currency       text not null default 'HUF',
  billing_cycle  text not null default 'monthly' check (billing_cycle in ('monthly','quarterly','yearly')),
  provider       text not null default 'barion' check (provider in ('barion','stripe','paypal','manual')),
  provider_customer_id text,
  provider_subscription_id text,
  started_at     timestamptz not null default now(),
  current_period_end timestamptz,
  cancelled_at   timestamptz,
  expires_at     timestamptz,
  metadata       jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  deleted_at     timestamptz,
  unique (user_email, provider)
);
comment on table om.subscriptions is 'Premium ad-free subscribers — Barion/Stripe backed';

create index if not exists idx_subs_email   on om.subscriptions(user_email);
create index if not exists idx_subs_status  on om.subscriptions(status) where deleted_at is null;
create index if not exists idx_subs_period  on om.subscriptions(current_period_end) where status = 'active';

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. UPDATED_AT TRIGGERS
-- ─────────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  tables text[] := array[
    'domain_role','sources','source_feeds','raw_articles','normalized_articles',
    'canonical_assets','derivative_assets','prompt_registry','publication_targets',
    'publish_queue','interlink_graph','error_events','agent_prompts','agent_runs',
    'ad_inventory','ad_placements','subscriptions'
  ];
begin
  foreach t in array tables loop
    execute format('drop trigger if exists trg_%I_updated_at on om.%I', t, t);
    execute format(
      'create trigger trg_%I_updated_at before update on om.%I
       for each row execute function om.set_updated_at()', t, t
    );
  end loop;
end $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. ROW-LEVEL SECURITY — enable + baseline policies
-- ─────────────────────────────────────────────────────────────────────────────
do $$
declare
  t text;
  rls_tables text[] := array[
    'domain_role','sources','source_feeds','raw_articles','normalized_articles',
    'article_entities','article_locations','article_topics','canonical_assets',
    'derivative_assets','prompt_registry','generation_runs','publication_targets',
    'publish_queue','interlink_graph','audit_logs','error_events','agent_prompts',
    'agent_runs','agent_events','ad_inventory','ad_placements','subscriptions'
  ];
begin
  foreach t in array rls_tables loop
    execute format('alter table om.%I enable row level security', t);
    execute format('alter table om.%I force row level security', t);

    -- service_role bypass (full access)
    execute format(
      'drop policy if exists %I_service_role_all on om.%I', t||'_svc', t);
    execute format(
      'create policy %I_service_role_all on om.%I
         for all to service_role using (true) with check (true)',
      t||'_svc', t);

    -- authenticated read-only default (tightened per-table below for sensitive ones)
    execute format(
      'drop policy if exists %I_auth_read on om.%I', t||'_auth_r', t);
    execute format(
      'create policy %I_auth_read on om.%I
         for select to authenticated using (true)',
      t||'_auth_r', t);
  end loop;
end $$;

-- Tighten: subscriptions — users only see their own row
drop policy if exists subscriptions_auth_read on om.subscriptions;
create policy subscriptions_self_read on om.subscriptions
  for select to authenticated
  using (user_email = auth.jwt() ->> 'email');

-- Tighten: audit_logs / error_events — no anon, authenticated read-only is enough
-- (no insert/update by non-service_role)

-- Tighten: agent_prompts body leak prevention — strip body from anon (anon has no read policy by default)
-- (anon role never added to policies above → fully denied)

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. PG_CRON JOBS
-- ─────────────────────────────────────────────────────────────────────────────
-- All cron jobs are idempotent (unschedule+reschedule if exists)
do $$
declare
  v_jobid bigint;
begin
  -- Daily dedup sweep (semantic similarity merge, stale canonical cleanup)
  select jobid into v_jobid from cron.job where jobname = 'om-dedup-daily';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'om-dedup-daily',
    '0 3 * * *',
    $CRON$
      update om.canonical_assets
         set freshness_score = greatest(0, 1 - (extract(epoch from (now() - coalesce(published_at, first_seen_at))) / 604800.0))
       where deleted_at is null;
    $CRON$
  );

  -- Hourly interlink graph rebuild tick (worker consumes this)
  select jobid into v_jobid from cron.job where jobname = 'om-interlink-tick';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'om-interlink-tick',
    '15 * * * *',
    $CRON$ insert into om.audit_logs(event_type, entity_type, action, severity)
           values ('cron_tick','interlink_graph','rebuild_requested','info'); $CRON$
  );

  -- Every minute: promote scheduled publish_queue rows whose scheduled_at <= now()
  select jobid into v_jobid from cron.job where jobname = 'om-publish-queue-promote';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'om-publish-queue-promote',
    '* * * * *',
    $CRON$
      update om.publish_queue
         set state = 'queued', updated_at = now()
       where state = 'scheduled' and scheduled_at <= now();
    $CRON$
  );

  -- Nightly: aggregate agent_runs → agent_prompts.win_rate
  select jobid into v_jobid from cron.job where jobname = 'om-agent-winrate-nightly';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'om-agent-winrate-nightly',
    '30 2 * * *',
    $CRON$
      update om.agent_prompts ap
         set win_rate = sub.win_rate,
             runs_count = sub.runs,
             updated_at = now()
        from (
          select prompt_id,
                 count(*) filter (where status = 'success')::numeric / nullif(count(*),0) as win_rate,
                 count(*) as runs
            from om.agent_runs
           where prompt_id is not null
             and started_at > now() - interval '30 days'
           group by prompt_id
        ) sub
       where ap.id = sub.prompt_id;
    $CRON$
  );

  -- Weekly: archive raw_articles older than 180 days
  select jobid into v_jobid from cron.job where jobname = 'om-raw-archive-weekly';
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
  perform cron.schedule(
    'om-raw-archive-weekly',
    '0 4 * * 0',
    $CRON$
      update om.raw_articles
         set status = 'archived', updated_at = now()
       where fetched_at < now() - interval '180 days'
         and status <> 'archived'
         and deleted_at is null;
    $CRON$
  );
end $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. INITIAL SEED — domain_role (20 sample of 139 sites)
-- Full seed script to follow in supabase/seed/domain_role_full.sql
-- ─────────────────────────────────────────────────────────────────────────────
insert into om.domain_role (domain, cluster, role, parent_domain, city, county, topic_primary, mainwp_group)
values
  ('orszagosmediahalozat.hu', 'orszagos', 'root_hub',     null,                      null,          null,         'orszagos',  '0 Root'),
  ('azar.hu',                 'tematikus','brand_hub',    'orszagosmediahalozat.hu', null,          null,         'technology','0 Root'),
  ('budapestma.hu',           'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Budapest',    'Budapest',   'hirek',     '3 Média'),
  ('debrecenma.hu',           'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Debrecen',    'Hajdu-Bihar','hirek',     '3 Média'),
  ('szegedma.hu',             'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Szeged',      'Csongrad',   'hirek',     '3 Média'),
  ('miskolcma.hu',            'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Miskolc',     'Borsod',     'hirek',     '3 Média'),
  ('pecsma.hu',               'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Pecs',        'Baranya',    'hirek',     '3 Média'),
  ('gyorma.hu',               'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Gyor',        'Gyor-M-S',   'hirek',     '3 Média'),
  ('nyiregyhazama.hu',        'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Nyiregyhaza', 'Szabolcs',   'hirek',     '3 Média'),
  ('kecskemetma.hu',          'varosi',   'city_hub',     'orszagosmediahalozat.hu', 'Kecskemet',   'Bacs-Kiskun','hirek',     '3 Média'),
  ('utazasblog.hu',           'blog',     'travel_blog',  'orszagosmediahalozat.hu', null,          null,         'travel',    '1 Blogok'),
  ('uzletiblog.hu',           'blog',     'business_blog','orszagosmediahalozat.hu', null,          null,         'business',  '1 Blogok'),
  ('egeszsegblog.hu',         'blog',     'health_blog',  'orszagosmediahalozat.hu', null,          null,         'health',    '1 Blogok'),
  ('sportblog.hu',            'blog',     'sport_blog',   'orszagosmediahalozat.hu', null,          null,         'sport',     '1 Blogok'),
  ('itblog.hu',               'blog',     'it_blog',      'orszagosmediahalozat.hu', null,          null,         'it',        '1 Blogok'),
  ('utazasforum.hu',          'forum',    'travel_forum', 'utazasblog.hu',           null,          null,         'travel',    '2 Fórumok'),
  ('uzletiforum.hu',          'forum',    'business_forum','uzletiblog.hu',          null,          null,         'business',  '2 Fórumok'),
  ('politikaihirek.hu',       'hir',      'news_site',    'orszagosmediahalozat.hu', null,          null,         'politics',  '4 Hírek'),
  ('gazdasagihirek.hu',       'hir',      'news_site',    'orszagosmediahalozat.hu', null,          null,         'economy',   '4 Hírek'),
  ('sporthirek.hu',           'hir',      'news_site',    'orszagosmediahalozat.hu', null,          null,         'sport',     '4 Hírek')
on conflict (domain) do nothing;

-- ─────────────────────────────────────────────────────────────────────────────
-- 10. GRANTS (Supabase role model)
-- ─────────────────────────────────────────────────────────────────────────────
grant usage on schema om to anon, authenticated, service_role;
grant select on all tables in schema om to authenticated;
grant all    on all tables in schema om to service_role;
grant usage, select on all sequences in schema om to authenticated, service_role;

alter default privileges in schema om grant select on tables to authenticated;
alter default privileges in schema om grant all    on tables to service_role;

-- ─────────────────────────────────────────────────────────────────────────────
-- END · OM Core Schema v1.0
-- ─────────────────────────────────────────────────────────────────────────────
