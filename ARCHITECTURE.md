# MoneyFlow — Architecture & How It Works

## Overview

MoneyFlow is a personal finance tracker that imports transactions from multiple sources:
1. **Gmail email alerts** — real-time transaction notifications
2. **Gmail PDF statements** — monthly CC/bank statement PDFs attached to emails
3. **Manual PDF upload** — drag & drop statement PDFs
4. **Manual entry** — add transactions by hand

## Supported Banks

| Bank | Email Alerts | PDF Statements | Notes |
|------|-------------|----------------|-------|
| HDFC Bank | ✅ UPI debits, CC OTP alerts | ✅ CC statements | Sender: alerts@hdfcbank.net |
| Axis Bank | ❌ | ✅ CC + Bank account | Sender: cc.statements@axis.bank.in, statements@axis.bank.in |
| Scapia (Federal) | ✅ Transaction confirmations | ❌ (no PDF attached) | Sender: scapiacards@federalbank.co.in |
| ICICI Bank | ❌ | ✅ CC statements | Needs separate password |
| Kotak Bank | ❌ | ✅ Bank account statements | Needs separate password |
| SBI | ❌ | ✅ (if format matches) | Untested |

### Adding a New Bank

1. **Email alerts**: Add sender to `BANK_SENDERS` in `gmail_sync.py`, add parser in `email_parser.py`
2. **PDF statements**: Usually works automatically via `auto_detect.py` → `bank_parser.py` or `credit_card_parser.py`. Add sender domain to `statement_senders` in `gmail_sync.py`.
3. **Bank name**: Add to `_detect_bank()` in `gmail_sync.py` and `_source_to_bank()` in `expenses.py`

## Transaction Flow

```
Gmail API                          Parser                          Database
─────────                          ──────                          ────────
Email alerts  ──→  email_parser.py  ──→  ExpenseCreate  ──→  dedup  ──→  Expense table
PDF attachments ──→ detect_and_parse ──→ ExpenseCreate  ──→  dedup  ──→  Expense table
Manual upload  ──→  detect_and_parse ──→ ExpenseCreate  ──→  dedup  ──→  Expense table
Manual entry   ──→  direct           ──→ ExpenseCreate  ──→          ──→  Expense table
```

## Source Tags

Each transaction is tagged with its origin:

| Source | Meaning |
|--------|---------|
| `email_hdfc_bank` | HDFC bank account email alert |
| `email_hdfc_cc` | HDFC credit card OTP email |
| `email_scapia` | Scapia CC transaction email |
| `stmt_axis_cc` | Axis CC statement PDF (from Gmail) |
| `stmt_axis_bank` | Axis bank account statement PDF (from Gmail) |
| `stmt_hdfc_cc` | HDFC CC statement PDF (from Gmail) |
| `stmt_kotak_bank` | Kotak bank statement PDF (from Gmail) |
| `upi_pdf` | PhonePe/UPI PDF (manual upload) |
| `credit_card_pdf` | CC PDF (manual upload) |
| `bank_pdf` | Bank statement PDF (manual upload) |
| `manual` | Manually entered |

## CC vs Bank Detection

After parsing a PDF, the system counts transactions with `payment_method="credit_card"`:
- If >50% → CC statement → source tag ends with `_cc`
- Otherwise → bank account → source tag ends with `_bank`

This is automatic and works for any bank.

## Credit vs Debit Handling

- **Positive amounts** = debits (money spent)
- **Negative amounts** = credits (money received/refunds/payments)
- **CC credits** (bill payments, refunds) are NOT counted as income
- **Bank credits** (salary, transfers) ARE counted as income
- Detection: `_is_cc_source()` checks the source tag

## Duplicate Detection

Before inserting, each transaction is checked against existing records:
1. Same date (date portion only, ignores time)
2. Same amount (absolute value within ₹0.01)
3. Either: matching `reference_id` (UTR number) OR similar description (normalized word overlap ≥50%)

## PDF Passwords

- Stored in `pdf_passwords` table (label + password)
- Tried in order when opening encrypted PDFs
- Saved passwords tried first, then `None` (unprotected)
- If no password works → "Could not open — add correct password"
- If password works but 0 transactions → "Unsupported format"

## Gmail OAuth

- Scope: `gmail.readonly` (minimum permission)
- Tokens stored in `gmail_accounts` table
- Auto-refreshes expired tokens
- PKCE flow with code_verifier stored in memory between auth and callback
