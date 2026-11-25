create table if not exists public.news_submissions (
    id uuid primary key default gen_random_uuid(),
    headline text not null check (char_length(headline) between 5 and 300),
    article_text text not null check (char_length(article_text) between 40 and 20000),
    source_name text check (source_name is null or char_length(source_name) <= 200),
    source_url text,
    status text not null default 'received' check (status in ('received', 'analyzing', 'analyzed', 'failed')),
    analysis_result jsonb,
    created_at timestamptz not null default now()
);

alter table public.news_submissions
    add column if not exists analysis_result jsonb;

alter table public.news_submissions enable row level security;

revoke all on table public.news_submissions from anon, authenticated;
grant all on table public.news_submissions to service_role;
