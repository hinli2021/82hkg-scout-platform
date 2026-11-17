-- 82HKG 童軍平台 — Supabase 試驗用資料表
-- 用法：在 Supabase 專案的 SQL Editor 貼上整份檔案，按 Run 一次就可以。
-- 每個試算表分頁對應一張表：key 是該列的主鍵，data 以 JSONB 保存整列資料，seq 是加入次序。
-- 這樣日後平台新增欄位時不用再改資料表；要查資料可以用 data->>'欄位名'。
-- RLS 已開啟而且沒有公開規則：只有 service_role 金鑰（只放在伺服器）可以讀寫。

create table if not exists public.users (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.users enable row level security;

create table if not exists public.password_reset_requests (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.password_reset_requests enable row level security;

create table if not exists public.password_resets (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.password_resets enable row level security;

create table if not exists public.stats (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.stats enable row level security;

create table if not exists public.badges (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.badges enable row level security;

create table if not exists public.tasks (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.tasks enable row level security;

create table if not exists public.progress_records (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.progress_records enable row level security;

create table if not exists public.badge_awards (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.badge_awards enable row level security;

create table if not exists public.points_ledger (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.points_ledger enable row level security;

create table if not exists public.rewards (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.rewards enable row level security;

create table if not exists public.redemptions (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.redemptions enable row level security;

create table if not exists public.suggestions (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.suggestions enable row level security;

create table if not exists public.announcements (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.announcements enable row level security;

create table if not exists public.audit_log (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.audit_log enable row level security;

create table if not exists public.sessions (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.sessions enable row level security;

create table if not exists public.settings (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.settings enable row level security;

create table if not exists public.feedback (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.feedback enable row level security;

create table if not exists public.profiles (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;

create table if not exists public.gacha (
  seq bigint generated always as identity,
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.gacha enable row level security;

-- 上載檔案（證據相片、卡圖）存放的儲存桶，公開讀取、只有伺服器可以寫入。
insert into storage.buckets (id, name, public) values ('uploads', 'uploads', true)
on conflict (id) do nothing;
