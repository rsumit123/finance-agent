# Assumptions & How We Count Money

This document explains the logic behind how MoneyFlow calculates your finances. Understanding these assumptions helps you verify the numbers make sense.

## Core Rule: No Double Counting

When you use a credit card, the transaction happens twice in your bank records:
1. **The purchase** — `NETFLIX ₹499` on your CC statement
2. **The CC bill payment** — `CREDITCARD PAYMENT ₹14,637` from your bank account

If we counted both, your spending would be inflated. So:

- **Individual CC transactions** (Netflix, Amazon, etc.) → counted as spending
- **CC bill payments** (MB PAYMENT, CRED CLUB, PayZapp) → tagged as "transfer", excluded from spending

The same applies to money you move between your own accounts (Axis → Kotak, HDFC → Axis).

## What Counts as What

### Spending (Debits)
Any positive amount transaction that is NOT a self-transfer:
- Credit card purchases (Netflix, Amazon, Swiggy, etc.)
- UPI payments to merchants and people
- Bank debits (NEFT, IMPS, ATM withdrawals)
- Bills, subscriptions, fees

### Income
Only transactions categorized as **"salary"**:
- Payroll credits from employer
- Detected by keywords: "salary", "payroll", "sal credit"
- Or manually categorized as salary by the user

**NOT counted as income:**
- Refunds (Amazon return, railway cancellation) — these reduce net spending but aren't earnings
- CC credits (payment reversals) — internal card adjustments
- Money received from self-transfers — just moving money between accounts

### Self-Transfers (Excluded from both income and spending)
Money moving between your own accounts:
- `CREDITCARD PAYMENT XX 1088` — paying your CC bill
- `MB PAYMENT #...` — mobile banking CC payment
- `UPI TRANSFER TO [YOUR NAME]` — sending to your own account
- `CRED CLUB`, `PayZapp` — CC bill payment apps
- `NEFT TO [YOUR NAME]` — bank-to-bank self transfer

**How we detect self-transfers:**
- CC bill payments: keywords like "creditcard payment", "mb payment", "cred club"
- Self-transfers: your name appears in the transaction description
- These are tagged as category "transfer" and visible in the Expenses page

### Refunds & Credits
Negative amounts from non-salary, non-transfer sources:
- Amazon refunds, railway cancellations, Google Play reversals
- Shown as green `+₹X` in the transaction list
- NOT counted as income (they just reduce your net outflow)
- NOT excluded from the transaction list (you can see them)

## Dashboard Numbers Explained

| Stat | What it shows | What's excluded |
|------|--------------|-----------------|
| **Spent** | Sum of all debit transactions | Self-transfers |
| **Income** | Sum of salary credits only | Refunds, CC credits, self-transfers |
| **Net Cash Flow** | Income minus Spent | Self-transfers on both sides |
| **CC Outstanding** | CC charges minus CC payments (all time) | Nothing — shows true debt |
| **Category bars** | Spending breakdown by category | Transfers shown dimmed with note |

## CC Outstanding Calculation

For each credit card:
```
Outstanding = Total CC charges − Total CC payments received
```

- **CC charges** = all positive amounts from CC sources (what you spent on the card)
- **CC payments** = negative amounts on CC (bill payments received by the card)
- If outstanding > 0, you owe that amount
- If outstanding = 0, card is "Paid up"
- CC outstanding is **always calculated across all time** (debt doesn't reset monthly)

## Edge Cases

### What if I only import the bank statement, not the CC statement?
The CC bill payment (`CREDITCARD PAYMENT ₹14,637`) will show as a transfer. But the individual CC purchases won't appear since the CC statement wasn't imported. Your spending will be undercounted. **Import both CC and bank statements for accurate numbers.**

### What about cash spending?
Cash withdrawals (ATM) are tracked as "atm" category. But what you spend the cash on isn't tracked — only the withdrawal. Cash spending after the ATM visit is invisible unless manually entered.

### What about EMIs?
EMI debits are tagged as "emi" category and counted as spending. The loan principal repayment part is technically not "spending" but a debt reduction — we don't separate interest vs principal.

### What about investment transactions?
We don't import investment/demat statements (FYERS, Zerodha, Groww, CDSL are filtered out). SIPs and mutual fund purchases from bank statements may show up as "other" — categorize them manually.

## How to Verify

1. Go to **Expenses page** → filter by **Type: Credits** → see all money coming in
2. Go to **Expenses page** → filter by **Category: Transfer** → see what's excluded from spend
3. Go to **Dashboard** → click any **category bar** → see exactly which transactions are counted
4. Go to **Statements page** → see per-bank, per-month breakdown with spent vs paid
