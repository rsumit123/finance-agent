"""CLI interface for the finance agent."""

import click
from datetime import date
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .advisor import analyze_purchase
from .models import Category, PaymentMethod
from .storage import load_budget, load_expenses
from .tracker import (
    add_expense,
    get_budget_status,
    get_current_month_expenses,
    get_current_week_expenses,
    remove_expense,
    set_budget,
    summarize_expenses,
)

console = Console()

CATEGORY_CHOICES = [c.value for c in Category]
PAYMENT_CHOICES = [p.value for p in PaymentMethod]


@click.group()
def cli():
    """Personal Finance Tracker & Purchase Advisor"""
    pass


# --- Expense commands ---


@cli.group()
def expense():
    """Manage expenses."""
    pass


@expense.command("add")
@click.option("--amount", "-a", type=float, required=True, help="Amount in INR")
@click.option(
    "--category",
    "-c",
    type=click.Choice(CATEGORY_CHOICES),
    required=True,
    help="Expense category",
)
@click.option(
    "--payment",
    "-p",
    type=click.Choice(PAYMENT_CHOICES),
    required=True,
    help="Payment method",
)
@click.option("--description", "-d", required=True, help="What was this expense for?")
@click.option(
    "--date",
    "expense_date",
    type=str,
    default=None,
    help="Date (YYYY-MM-DD), defaults to today",
)
def add_expense_cmd(amount, category, payment, description, expense_date):
    """Add a new expense."""
    exp = add_expense(amount, category, payment, description, expense_date)
    console.print(
        Panel(
            f"[green]Added:[/green] ₹{amount:,.0f} for '{description}'\n"
            f"Category: {category} | Payment: {payment} | Date: {exp.date}",
            title="Expense Added",
            border_style="green",
        )
    )


@expense.command("list")
@click.option(
    "--period",
    type=click.Choice(["week", "month", "all"]),
    default="month",
    help="Time period",
)
def list_expenses_cmd(period):
    """List expenses."""
    if period == "week":
        expenses = get_current_week_expenses()
        title = "This Week's Expenses"
    elif period == "month":
        expenses = get_current_month_expenses()
        title = "This Month's Expenses"
    else:
        expenses = load_expenses()
        title = "All Expenses"

    if not expenses:
        console.print("[yellow]No expenses found for this period.[/yellow]")
        return

    table = Table(title=title)
    table.add_column("ID", style="dim")
    table.add_column("Date")
    table.add_column("Amount (₹)", justify="right", style="red")
    table.add_column("Category", style="cyan")
    table.add_column("Payment", style="magenta")
    table.add_column("Description")

    for e in sorted(expenses, key=lambda x: x.date, reverse=True):
        table.add_row(
            e.id,
            e.date,
            f"{e.amount:,.0f}",
            e.category.value,
            e.payment_method.value,
            e.description,
        )

    console.print(table)

    summary = summarize_expenses(expenses)
    console.print(f"\n[bold]Total: ₹{summary['total']:,.0f}[/bold] ({summary['count']} transactions)")


@expense.command("delete")
@click.argument("expense_id")
def delete_expense_cmd(expense_id):
    """Delete an expense by ID."""
    if remove_expense(expense_id):
        console.print(f"[green]Deleted expense {expense_id}[/green]")
    else:
        console.print(f"[red]Expense {expense_id} not found[/red]")


@expense.command("summary")
@click.option(
    "--period",
    type=click.Choice(["week", "month"]),
    default="month",
    help="Time period",
)
def summary_cmd(period):
    """Show expense summary by category and payment method."""
    if period == "week":
        expenses = get_current_week_expenses()
        title = "Weekly Summary"
    else:
        expenses = get_current_month_expenses()
        title = "Monthly Summary"

    if not expenses:
        console.print("[yellow]No expenses found.[/yellow]")
        return

    summary = summarize_expenses(expenses)

    # By category
    cat_table = Table(title=f"{title} — By Category")
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Amount (₹)", justify="right", style="red")
    cat_table.add_column("% of Total", justify="right")

    for cat, amt in sorted(summary["by_category"].items(), key=lambda x: x[1], reverse=True):
        pct = (amt / summary["total"]) * 100 if summary["total"] > 0 else 0
        cat_table.add_row(cat, f"{amt:,.0f}", f"{pct:.1f}%")

    console.print(cat_table)

    # By payment method
    pay_table = Table(title=f"{title} — By Payment Method")
    pay_table.add_column("Method", style="magenta")
    pay_table.add_column("Amount (₹)", justify="right", style="red")

    for method, amt in sorted(summary["by_payment_method"].items(), key=lambda x: x[1], reverse=True):
        pay_table.add_row(method, f"{amt:,.0f}")

    console.print(pay_table)
    console.print(f"\n[bold]Total: ₹{summary['total']:,.0f}[/bold]")


# --- Budget commands ---


@cli.group()
def budget():
    """Manage budget limits."""
    pass


@budget.command("set")
@click.option("--monthly", "-m", type=float, required=True, help="Monthly spending limit (INR)")
@click.option("--weekly", "-w", type=float, required=True, help="Weekly spending limit (INR)")
@click.option(
    "--category-limit",
    "-cl",
    multiple=True,
    type=(str, float),
    help="Category limit, e.g. -cl food 5000",
)
def set_budget_cmd(monthly, weekly, category_limit):
    """Set your spending budget."""
    cat_limits = {cat: limit for cat, limit in category_limit}
    budget = set_budget(monthly, weekly, cat_limits)
    console.print(
        Panel(
            f"[green]Budget set![/green]\n"
            f"Monthly limit: ₹{monthly:,.0f}\n"
            f"Weekly limit:  ₹{weekly:,.0f}"
            + (
                "\n\nCategory limits:\n"
                + "\n".join(f"  {c}: ₹{l:,.0f}" for c, l in cat_limits.items())
                if cat_limits
                else ""
            ),
            title="Budget Updated",
            border_style="green",
        )
    )


@budget.command("status")
def budget_status_cmd():
    """Show current budget status."""
    status = get_budget_status()
    if not status:
        console.print("[yellow]No budget set. Use `finance budget set` first.[/yellow]")
        return

    # Weekly status
    w = status["weekly"]
    week_color = "green" if w["percent_used"] < 75 else "yellow" if w["percent_used"] < 100 else "red"
    console.print(
        Panel(
            f"Spent: ₹{w['spent']:,.0f} / ₹{w['limit']:,.0f}\n"
            f"Remaining: [{week_color}]₹{w['remaining']:,.0f}[/{week_color}]\n"
            f"Used: [{week_color}]{w['percent_used']}%[/{week_color}]",
            title="Weekly Budget",
            border_style=week_color,
        )
    )

    # Monthly status
    m = status["monthly"]
    month_color = "green" if m["percent_used"] < 75 else "yellow" if m["percent_used"] < 100 else "red"
    console.print(
        Panel(
            f"Spent: ₹{m['spent']:,.0f} / ₹{m['limit']:,.0f}\n"
            f"Remaining: [{month_color}]₹{m['remaining']:,.0f}[/{month_color}]\n"
            f"Used: [{month_color}]{m['percent_used']}%[/{month_color}]",
            title="Monthly Budget",
            border_style=month_color,
        )
    )

    # Category breakdown
    if status["categories"]:
        cat_table = Table(title="Category Budget Status")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Spent", justify="right")
        cat_table.add_column("Limit", justify="right")
        cat_table.add_column("Remaining", justify="right")
        cat_table.add_column("Used %", justify="right")

        for cat, info in status["categories"].items():
            color = (
                "green" if info["percent_used"] < 75
                else "yellow" if info["percent_used"] < 100
                else "red"
            )
            cat_table.add_row(
                cat,
                f"₹{info['spent']:,.0f}",
                f"₹{info['limit']:,.0f}",
                f"[{color}]₹{info['remaining']:,.0f}[/{color}]",
                f"[{color}]{info['percent_used']}%[/{color}]",
            )

        console.print(cat_table)


# --- Purchase advisor ---


@cli.command("can-i-buy")
@click.argument("amount", type=float)
@click.option(
    "--category",
    "-c",
    type=click.Choice(CATEGORY_CHOICES),
    default=None,
    help="Category of the purchase",
)
def can_i_buy_cmd(amount, category):
    """Check if you can afford a purchase right now.

    Example: finance can-i-buy 2000
    """
    verdict = analyze_purchase(amount, category)

    if verdict.can_buy:
        style = "green"
        header = f"YES — You can buy this (₹{amount:,.0f})"
    else:
        style = "red"
        header = f"NO — Skip this purchase (₹{amount:,.0f})"

    lines = []

    if verdict.reasons:
        lines.append("[bold]Analysis:[/bold]")
        for r in verdict.reasons:
            lines.append(f"  {r}")

    if verdict.warnings:
        lines.append("\n[yellow][bold]Warnings:[/bold][/yellow]")
        for w in verdict.warnings:
            lines.append(f"  [yellow]{w}[/yellow]")

    if verdict.can_buy:
        lines.append(f"\nAfter purchase:")
        lines.append(f"  Weekly remaining:  ₹{verdict.weekly_remaining_after:,.0f}")
        lines.append(f"  Monthly remaining: ₹{verdict.monthly_remaining_after:,.0f}")

    lines.append(f"\n[bold]Suggestion:[/bold] {verdict.suggestion}")

    console.print(
        Panel(
            "\n".join(lines),
            title=header,
            border_style=style,
        )
    )


if __name__ == "__main__":
    cli()
