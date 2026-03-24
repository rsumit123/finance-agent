"""Shared transaction categorization logic.

Used by all parsers (bank, CC, UPI, email) for consistent categorization.
"""

import re

# Category keywords — ordered by specificity (more specific first)
CATEGORY_KEYWORDS = {
    "subscriptions": [
        "netflix", "hotstar", "spotify", "youtube premium", "google play",
        "prime video", "amazon prime", "disney", "zee5", "sonyliv", "jiocinema",
        "claude", "anthropic", "openai", "chatgpt", "cursor", "github copilot",
        "notion", "slack premium", "figma", "canva pro",
        "google cloud", "aws", "azure", "digitalocean", "heroku",
        "cloudflare", "vercel", "netlify",
    ],
    "food": [
        "swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "mcdonald",
        "domino", "kfc", "starbucks", "chai", "barista", "hotel", "madrasi",
        "dhaba", "biryani", "burger", "subway", "haldiram", "barbeque",
        "kitchen", "bakery", "dine", "eat", "meal",
    ],
    "groceries": [
        "bigbasket", "dmart", "blinkit", "zepto", "instamart", "grocery",
        "supermarket", "smart bazaar", "flour mill", "reliance fresh",
        "more supermarket", "nature basket", "spencers", "nursery",
    ],
    "transport": [
        "uber", "ola", "rapido", "metro", "fuel", "petrol", "diesel",
        "irctc", "indian railways", "makemytrip", "cleartrip", "goibibo",
        "agoda", "booking.com", "yatra", "redbus", "auto service",
        "automobiles", "service station", "parking", "toll", "fastag",
        "airlines", "indigo", "air india", "vistara", "spicejet",
    ],
    "entertainment": [
        "movie", "pvr", "inox", "bookmyshow", "cinepolis",
        "cinema", "theatre", "bigtree entertainment", "apple india", "apple.com",
    ],
    "bills": [
        "electricity", "water bill", "gas bill", "broadband", "jio",
        "airtel", "vi ", "bsnl", "tata play", "recharge", "prepaid",
        "postpaid", "finance charges", "late fee", "gst", "igst", "cgst",
        "foreign currency transaction fee", "dcc markup", "annual fee",
        "github",
        "insurance", "lic", "premium", "openrouter", "google ",
        "federal bank",
    ],
    "shopping": [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "shopping",
        "mall", "reliance", "asspl", "nykaa", "tata cliq", "snapdeal",
        "paytm mall", "croma", "vijay sales",
    ],
    "health": [
        "hospital", "medical", "pharmacy", "doctor", "apollo", "1mg",
        "pharmeasy", "medplus", "clinic", "dental", "lab", "diagnostic",
        "pathology", "fortis", "max hospital",
    ],
    "education": [
        "school", "college", "course", "udemy", "coursera", "unacademy",
        "byju", "vedantu", "upgrad", "tuition", "coaching",
    ],
    "rent": [
        "rent", "landlord", "house rent", "pg ", "hostel",
    ],
    "home": [
        "furniture", "ikea", "pepperfry", "urban ladder", "construction",
        "infrastructure", "plumber", "electrician", "carpenter", "painter",
        "home decor", "hardware", "cement", "tiles", "sanitary",
    ],
    "personal care": [
        "salon", "jawed habib", "parlour", "parlor", "spa", "gym",
        "fitness", "grooming", "haircut", "beauty", "skincare",
        "cult.fit", "cultfit",
    ],
    "investment": [
        "sip", "mutual fund", "mf purchase", "zerodha", "groww",
        "kuvera", "coin by zerodha", "et money", "paytm money",
        "fixed deposit", "recurring deposit", "nps", "ppf",
        "stocks", "shares", "trading", "demat",
    ],
    "emi": [
        "emi", "loan", "instalment", "equated monthly",
        "home loan", "car loan", "personal loan", "loan repayment",
    ],
    "atm": [
        "atm", "cash withdrawal", "cash count", "cwdr", "iccw atm",
        "atl/", "cash deposit",
    ],
    "salary": [
        "salary", "sal credit", "payroll", "think workforce",
    ],
    "transfer": [
        "transfer to self", "own account",
        "creditcard payment", "credit card payment", "mb payment",
        "cred club", "cred pay", "payzapp",
    ],
}

# Known person name patterns — these are UPI transfers to people
# We detect them by checking if the description is just a person's name
# (no merchant keywords matched)
PERSON_NAME_PATTERN = re.compile(
    r"^(?:mr\.?|mrs\.?|ms\.?|shri\.?)?\s*[A-Z][a-z]+ (?:[A-Z][a-z]+ )*(?:S/?O|D/?O|W/?O)?\s*",
    re.IGNORECASE,
)


def classify_category(description: str, source: str = "", user_name: str = "", user_rules: list = None) -> str:
    """Classify a transaction into a category based on description.

    Args:
        description: Transaction description/merchant name
        source: Source tag (for context)
        user_name: User's name for self-transfer detection
        user_rules: List of (keyword, category) tuples from user's learned rules
    """
    if not description:
        return "other"

    desc_lower = description.lower().strip()

    # Check user-specific learned rules first (highest priority)
    if user_rules:
        desc_normalized = re.sub(r"[^a-z\s]", "", desc_lower)
        desc_normalized = re.sub(r"\s+", " ", desc_normalized).strip()
        for keyword, category in user_rules:
            if keyword in desc_normalized:
                return category

    # Self-transfer detection
    if user_name:
        name_lower = user_name.lower()
        name_parts = name_lower.split()
        if len(name_parts) >= 2 and all(part in desc_lower for part in name_parts):
            return "transfer"

    # Check against keyword categories
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return category

    # CC-specific: payment to card is a transfer
    if "credit" in (source or "").lower() or "cc" in (source or "").lower():
        if any(kw in desc_lower for kw in ["payment", "mb payment"]):
            return "transfer"

    # Kotak UPI format: "UPI/PersonName/RefId/..." — extract name
    upi_match = re.match(r"UPI/([^/]+)/\d+/", description)
    if upi_match:
        name_part = upi_match.group(1).strip()
        # Check if the name part matches any merchant keywords
        name_cat = classify_category(name_part, source=source, user_name=user_name)
        if name_cat != "other":
            return name_cat
        # Only mark as transfer if it matches user's name
        if user_name and all(p in name_part.lower() for p in user_name.lower().split()):
            return "transfer"
        return "other"  # Payment to a person, not self-transfer

    # "fund transfer" with user's name = self-transfer
    if "fund transfer" in desc_lower or "neft to" in desc_lower or "upi transfer to" in desc_lower:
        if user_name and all(p in desc_lower for p in user_name.lower().split()):
            return "transfer"
        # Fund transfer to someone else — could be anything
        return "other"

    return "other"
