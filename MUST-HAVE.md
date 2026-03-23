# Must-Have Features — Status Tracker

## ✅ Completed

### 2. Self-transfer detection ✅
Uses Google profile name automatically at import time. No hardcoded names.

### 3. Per-user Gmail OAuth tokens ✅
`gmail_accounts` table has `user_id`. Each user connects their own Gmail.

### 4. Per-user PDF passwords ✅
`pdf_passwords` table has `user_id`. Each user manages their own passwords.

### 5. Per-user data isolation ✅
`user_id` column on all tables (expenses, budgets, gmail_accounts, passwords, upload_history). Every query filtered by user.

### 6. Authentication & authorization ✅
Google Sign-In with JWT. All endpoints protected with `get_current_user` dependency.

---

## ❌ Still Needed

### 1. Salary/employer auto-learning
**Current state:** Salary detected via hardcoded keywords including "think workforce" (specific to one user). Generic keywords ("salary", "payroll") work but most salary transactions say "NEFT FROM COMPANY NAME" which won't match.

**Needed:** When a user manually tags a transaction as "salary" category, learn the employer name/description pattern and auto-apply to future imports. Store per-user keyword overrides.

**Implementation idea:**
- New table: `user_category_rules(user_id, keyword, category)`
- When user edits a category on the Expenses page, save a rule
- At import time, check user rules before the default categorizer
- UI: show learned rules in Account/Settings page

### 7. Category learning from edits
**Current state:** Fixed category list hardcoded in frontend and backend. Users can edit categories on transactions but can't create new ones. No learning from edits.

**Needed:** When user repeatedly recategorizes "XYZ MERCHANT" from "other" to "food", auto-learn that pattern for future imports.

**Implementation idea:**
- Same `user_category_rules` table as #1
- When user changes category on an expense, extract a keyword from description
- Ask user: "Apply 'food' to all future transactions matching 'XYZ MERCHANT'?"
- Store rule, check at import time

### 8. Multi-currency support
**Current state:** Everything assumed INR. Foreign transactions show USD amount in description but stored in converted INR amount.

**Needed:** Store original currency + converted amount. Show both in UI.

**Implementation idea:**
- Add `original_currency` and `original_amount` columns to Expense
- Parse currency from CC statements (e.g. "USD 118.00" in description)
- Show "₹10,735 (USD 118)" in transaction cards
- Low priority — most transactions are domestic INR
