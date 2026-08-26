# Supabase

The DevStacks Supabase project reference is `zscwpqtqdqoqpgjhckif`. The immutable evidence graph and tenant RLS migrations live in [migrations](migrations). Do not create application tables outside a reviewed migration.

## Local Configuration

Copy the environment templates before running either application:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Set `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` only in the frontend local file. Set `SUPABASE_SERVICE_ROLE_KEY` only in the backend local file. The service-role key bypasses RLS and must never be committed, exposed to the browser, or sent in chat.

## Applying Migrations

Install the Supabase CLI, authenticate by entering the access token directly in the terminal, link this repository to the project, inspect the change set, then apply it:

```powershell
supabase login
supabase link --project-ref zscwpqtqdqoqpgjhckif
supabase db push --dry-run
supabase db push
```

The CLI creates and tracks migration history after the first successful push. Do not apply migrations until the dry run shows only the reviewed files in this directory. The local environment currently has no Supabase CLI, so database-backed migration validation remains a pending deployment prerequisite.