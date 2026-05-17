"""Opportunity source categories."""

from __future__ import annotations

SUPPORTED_SOURCE_CATEGORIES = {
    "bounty": {
        "label": "Paid open-source bounty",
        "expected_payment_method": "project payout",
        "risk_notes": [],
    },
    "documentation": {
        "label": "Documentation bounty",
        "expected_payment_method": "project payout",
        "risk_notes": [],
    },
    "contest": {
        "label": "Contest or hackathon",
        "expected_payment_method": "contest payout",
        "risk_notes": [],
    },
    "small_gig": {
        "label": "Small freelance gig",
        "expected_payment_method": "platform payout",
        "risk_notes": [],
    },
    "grant": {
        "label": "Grant",
        "expected_payment_method": "grant payout",
        "risk_notes": [],
    },
    "micro_product": {
        "label": "Micro-product idea",
        "expected_payment_method": "direct sales",
        "risk_notes": [],
    },
    "affiliate": {
        "label": "Affiliate program",
        "expected_payment_method": "affiliate payout",
        "risk_notes": ["Requires TOS/legal review for marketing restrictions."],
    },
}

UNSUPPORTED_SOURCE_CATEGORIES = {
    "trading",
    "gambling",
    "prediction_markets",
    "airdrop_farming",
    "fake_account_schemes",
    "grey_market_arbitrage",
}
