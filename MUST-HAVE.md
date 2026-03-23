# Must-Have Features for Multi-User Launch

Things that are currently hardcoded or missing that need to be built when adding user accounts.

## 1. User-specific salary/employer detection
**Current state:** Salary detected via hardcoded keywords including "think workforce" (specific to one user). Generic keywords ("salary", "payroll") work but most salary transactions say "NEFT FROM COMPANY NAME" which won't match.

**Needed:** When a user manually tags a transaction as "salary" category, learn the employer name/description pattern and auto-apply to future imports. Store per-user employer patterns.

## 2. Self-transfer detection needs user's name
**Current state:** Self-transfers detected by matching "SUMIT KUMAR" in transaction descriptions. The `recategorize` endpoint accepts `user_name` as a parameter but it's not stored anywhere.

**Needed:** Store user's full name in their profile. Auto-detect self-transfers using their name during import (not just during recategorize). Handle name variations (SUMIT KUMAR vs Sumit Kumar vs S KUMAR).

## 3. Per-user Gmail OAuth tokens
**Current state:** Single `gmail_accounts` table row — only one user can connect Gmail. Tokens not tied to a user account.

**Needed:** Link Gmail tokens to user accounts. Support multiple users each with their own Gmail connection.

## 4. Per-user PDF passwords
**Current state:** Single `pdf_passwords` table shared. All passwords tried for all PDFs.

**Needed:** Passwords scoped to user accounts. Each user manages their own password list.

## 5. Per-user database / data isolation
**Current state:** Single SQLite database. All expenses, budgets, upload history shared.

**Needed:** Either multi-tenant with user_id foreign keys on every table, or per-user database files. Budget settings per user.

## 6. Authentication & authorization
**Current state:** No auth. Anyone with the URL can access all data.

**Needed:** Login flow (email/password or OAuth). Session management. API auth middleware.

## 7. Category learning / custom categories
**Current state:** Fixed category list hardcoded in frontend and backend. Users can edit categories on transactions but can't create new ones. No learning from edits.

**Needed:** User-defined categories. When user repeatedly recategorizes "XYZ MERCHANT" from "other" to "food", auto-learn that pattern for future imports.

## 8. Multi-currency support
**Current state:** Everything assumed INR. Foreign transactions show USD amount in description but stored in INR.

**Needed:** Store original currency + converted amount. Show both in UI.
