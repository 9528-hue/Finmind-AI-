"""
FinMind AI — Training Dataset for Transaction Categorizer (Model A)
=====================================================================
Provides a clearly-labelled synthetic training corpus.
Each record = (description, category).

Provenance: Synthetic — generated to represent common Indian and
international business bank-statement transaction patterns.
Not derived from real user data.
"""

from __future__ import annotations
from typing import List, Tuple

CATEGORY_LABELS = [
    "Revenue",
    "Payroll",
    "Rent",
    "Utilities",
    "Travel",
    "Food & Supplies",
    "Marketing",
    "Software & Subscriptions",
    "Loan & Finance",
    "Taxes",
    "Refund",
    "Transfer",
    "Other",
]

# (description_text, category_label)
TRAINING_EXAMPLES: List[Tuple[str, str]] = [
    # Revenue
    ("payment received from client abc pvt ltd", "Revenue"),
    ("invoice payment project alpha", "Revenue"),
    ("sales revenue deposit", "Revenue"),
    ("customer payment received", "Revenue"),
    ("online sales credit", "Revenue"),
    ("service charges received", "Revenue"),
    ("consulting fee inward", "Revenue"),
    ("subscription revenue collected", "Revenue"),
    ("product sale income", "Revenue"),
    ("gst refund from client", "Revenue"),
    ("export payment received usd", "Revenue"),
    ("royalty income credit", "Revenue"),
    ("client advance payment", "Revenue"),
    ("milestone payment project beta", "Revenue"),
    ("professional fee received", "Revenue"),
    ("commission income", "Revenue"),
    ("license fee received", "Revenue"),
    ("maintenance contract payment", "Revenue"),
    ("retainer fee credit", "Revenue"),
    ("interest income on deposits", "Revenue"),

    # Payroll
    ("salary payment staff october", "Payroll"),
    ("payroll processing oct 2024", "Payroll"),
    ("employee salary transfer", "Payroll"),
    ("wages credit october", "Payroll"),
    ("bonus payment employees", "Payroll"),
    ("stipend monthly intern", "Payroll"),
    ("contractor payment freelance", "Payroll"),
    ("pf epf contribution debit", "Payroll"),
    ("gratuity payment employee", "Payroll"),
    ("salary advance employee", "Payroll"),
    ("hr payroll batch transfer", "Payroll"),
    ("esic deduction employee", "Payroll"),
    ("tds on salary deducted", "Payroll"),
    ("leave encashment payment", "Payroll"),
    ("reimbursement employee expenses", "Payroll"),

    # Rent
    ("office rent payment october", "Rent"),
    ("monthly rent deposit landlord", "Rent"),
    ("rent advance 3 months", "Rent"),
    ("warehouse rent debit", "Rent"),
    ("lease payment commercial property", "Rent"),
    ("co-working space rent", "Rent"),
    ("shop rent transfer", "Rent"),
    ("annual rent payment", "Rent"),
    ("property rental payment", "Rent"),
    ("factory premises rent", "Rent"),

    # Utilities
    ("electricity bill payment", "Utilities"),
    ("bescom electricity charges", "Utilities"),
    ("water bill payment bwssb", "Utilities"),
    ("internet broadband payment", "Utilities"),
    ("airtel business broadband", "Utilities"),
    ("jio fiber bill payment", "Utilities"),
    ("mobile bill payment", "Utilities"),
    ("gas supply payment", "Utilities"),
    ("power bill commercial", "Utilities"),
    ("bsnl landline bill", "Utilities"),
    ("municipal water tax", "Utilities"),
    ("electricity consumption charge", "Utilities"),
    ("tata power bill", "Utilities"),
    ("reliance energy bill", "Utilities"),

    # Travel
    ("flight ticket booking indigo", "Travel"),
    ("irctc train ticket booking", "Travel"),
    ("hotel accommodation payment", "Travel"),
    ("makemytrip flight booking", "Travel"),
    ("goibibo hotel booking", "Travel"),
    ("business travel reimbursement", "Travel"),
    ("airbnb accommodation", "Travel"),
    ("cab booking outstation ola", "Travel"),
    ("visa application fee travel", "Travel"),
    ("airport transfer taxi", "Travel"),
    ("conference travel booking", "Travel"),
    ("cleartrip booking payment", "Travel"),
    ("yatra travel booking", "Travel"),
    ("international air ticket", "Travel"),

    # Food & Supplies
    ("office canteen expenses", "Food & Supplies"),
    ("team lunch amazon fresh", "Food & Supplies"),
    ("stationery purchase office", "Food & Supplies"),
    ("office supplies amazon", "Food & Supplies"),
    ("pantry restocking groceries", "Food & Supplies"),
    ("coffee machine supplies", "Food & Supplies"),
    ("printer paper and ink", "Food & Supplies"),
    ("cleaning supplies purchase", "Food & Supplies"),
    ("swiggy team order office", "Food & Supplies"),
    ("zomato corporate order", "Food & Supplies"),
    ("catering service payment", "Food & Supplies"),
    ("blinkit office supplies", "Food & Supplies"),
    ("business meals client dinner", "Food & Supplies"),

    # Marketing
    ("google ads payment", "Marketing"),
    ("facebook meta ads spend", "Marketing"),
    ("instagram advertising", "Marketing"),
    ("linkedin advertising", "Marketing"),
    ("digital marketing agency fee", "Marketing"),
    ("seo services payment", "Marketing"),
    ("content marketing expense", "Marketing"),
    ("social media marketing", "Marketing"),
    ("influencer marketing payment", "Marketing"),
    ("print advertising local", "Marketing"),
    ("trade show exhibition fee", "Marketing"),
    ("promotional merchandise", "Marketing"),
    ("email marketing tool", "Marketing"),
    ("brand photography shoot", "Marketing"),

    # Software & Subscriptions
    ("aws amazon web services", "Software & Subscriptions"),
    ("google cloud platform billing", "Software & Subscriptions"),
    ("microsoft azure subscription", "Software & Subscriptions"),
    ("github subscription payment", "Software & Subscriptions"),
    ("slack team subscription", "Software & Subscriptions"),
    ("zoom video conferencing", "Software & Subscriptions"),
    ("salesforce crm license", "Software & Subscriptions"),
    ("jira atlassian subscription", "Software & Subscriptions"),
    ("adobe creative cloud", "Software & Subscriptions"),
    ("figma design tool", "Software & Subscriptions"),
    ("notion team plan", "Software & Subscriptions"),
    ("hubspot subscription", "Software & Subscriptions"),
    ("quickbooks accounting software", "Software & Subscriptions"),
    ("tally erp license renewal", "Software & Subscriptions"),
    ("dropbox business storage", "Software & Subscriptions"),
    ("office 365 microsoft", "Software & Subscriptions"),
    ("antivirus software renewal", "Software & Subscriptions"),

    # Loan & Finance
    ("emi payment hdfc loan", "Loan & Finance"),
    ("loan repayment installment", "Loan & Finance"),
    ("bank loan emi debit", "Loan & Finance"),
    ("sbi business loan emi", "Loan & Finance"),
    ("cc payment credit card bill", "Loan & Finance"),
    ("icici credit card payment", "Loan & Finance"),
    ("axis bank emi auto debit", "Loan & Finance"),
    ("equipment finance payment", "Loan & Finance"),
    ("vehicle loan emi", "Loan & Finance"),
    ("mortgage payment commercial", "Loan & Finance"),
    ("overdraft repayment", "Loan & Finance"),
    ("interest charges bank", "Loan & Finance"),

    # Taxes
    ("income tax advance payment", "Taxes"),
    ("gst payment challan", "Taxes"),
    ("tds payment government", "Taxes"),
    ("professional tax payment", "Taxes"),
    ("property tax payment", "Taxes"),
    ("customs duty payment", "Taxes"),
    ("service tax payment", "Taxes"),
    ("quarterly tds challan", "Taxes"),
    ("corporate tax payment", "Taxes"),
    ("advance tax q3 payment", "Taxes"),

    # Refund
    ("refund from vendor", "Refund"),
    ("gst input credit refund", "Refund"),
    ("excess payment refund", "Refund"),
    ("cancelled order refund", "Refund"),
    ("deposit refund received", "Refund"),
    ("insurance claim refund", "Refund"),
    ("credit note adjustment", "Refund"),
    ("reversal of charge", "Refund"),
    ("overcharge refund customer", "Refund"),

    # Transfer
    ("inter account transfer", "Transfer"),
    ("neft transfer own account", "Transfer"),
    ("rtgs own account transfer", "Transfer"),
    ("internal fund transfer", "Transfer"),
    ("petty cash transfer office", "Transfer"),
    ("current to savings transfer", "Transfer"),
    ("self transfer business account", "Transfer"),
    ("imps transfer own account", "Transfer"),
    ("fund sweep savings", "Transfer"),

    # Other
    ("bank charges debit", "Other"),
    ("atm cash withdrawal", "Other"),
    ("cheque book request fee", "Other"),
    ("locker rent annual", "Other"),
    ("miscellaneous charges", "Other"),
    ("penalty charges late payment", "Other"),
    ("stamp duty registration", "Other"),
    ("notary fee legal", "Other"),
    ("donation charitable trust", "Other"),
    ("membership fee association", "Other"),
    ("insurance premium payment", "Other"),
    ("security deposit refundable", "Other"),
    ("annual maintenance charge", "Other"),
    ("noc certificate fee", "Other"),
]


def get_training_data() -> Tuple[List[str], List[str]]:
    """Return (X, y) for model training."""
    X = [ex[0] for ex in TRAINING_EXAMPLES]
    y = [ex[1] for ex in TRAINING_EXAMPLES]
    return X, y
