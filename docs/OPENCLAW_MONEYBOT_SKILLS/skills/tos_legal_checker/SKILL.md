# Skill: tos_legal_checker

## Purpose

`tos_legal_checker` reviews platform terms, contest rules, bounty scope, marketplace policies, payment requirements, and obvious legal/TOS red flags before the MoneyBot executes an opportunity.

This skill is not a substitute for legal advice. It is a conservative risk screener that prevents the bot from executing actions when terms are unclear, platform rules prohibit automation, or the activity resembles regulated, deceptive, abusive, or unlawful conduct.

## When To Use

Call this skill before:

- Account creation.
- Form submission.
- Public posting.
- Sending business or cold outreach email.
- Spending money.
- Entering bounties, contests, grants, affiliate programs, or marketplace programs.
- Scraping, browser automation, data collection, or user-data handling.
- Security bounty work or anything involving testing a third-party system.

## Inputs

```json
{
  "check_id": "string",
  "opportunity_id": "string|null",
  "action_description": "string",
  "platform": "string|null",
  "source_urls": ["string"],
  "terms_urls": ["string"],
  "rules_text": "string|null",
  "planned_actions": ["string"],
  "requires_account": false,
  "requires_automation": false,
  "requires_email_outreach": false,
  "requires_scraping": false,
  "requires_payment": false,
  "requires_crypto": false,
  "requires_user_data_collection": false,
  "requires_security_testing": false,
  "requires_public_claims": false,
  "geography": "US|null",
  "notes": "string"
}
```

## Required Review Questions

The skill must answer:

1. What platform, program, or counterparty controls the opportunity?
2. Are the relevant rules/terms available?
3. Do the terms allow the planned action?
4. Do the terms prohibit bots, scraping, automation, bulk messaging, account farming, or resale?
5. Is the payment mechanism clear and legitimate?
6. Does the action require KYC, identity claims, or regulated financial activity?
7. Does the action require handling funds for others?
8. Does the action require collecting, storing, or processing personal data?
9. Does the action include public advertising, income claims, legal/financial claims, health claims, security claims, or other claims that require substantiation?
10. Does the action involve security testing, vulnerability reporting, or exploit reproduction?
11. Are there regional restrictions or eligibility requirements?
12. Is human review required before proceeding?

## Output Schema

Return strict JSON:

```json
{
  "check_id": "string",
  "opportunity_id": "string|null",
  "decision": "proceed | reject | human_review | insufficient_information",
  "confidence": "low | medium | high",
  "risk_level": "low | medium | high | critical",
  "terms_available": false,
  "terms_summary": "string",
  "allowed_by_terms": "yes | no | unclear",
  "legal_red_flags": ["string"],
  "tos_red_flags": ["string"],
  "privacy_red_flags": ["string"],
  "payment_red_flags": ["string"],
  "automation_red_flags": ["string"],
  "required_mitigations": ["string"],
  "must_call_policy_guard": true,
  "must_create_ledger_record": true,
  "evidence": [
    {
      "url": "string",
      "type": "terms | rules | faq | payment | privacy | other",
      "relevant_excerpt_or_summary": "string"
    }
  ],
  "notes": "string"
}
```

## Decision Rules

### `proceed`

Use only when:

- Relevant terms/rules are available or not needed for the action.
- The planned action is clearly permitted or ordinary.
- No prohibited category applies.
- No account deception, spam, fake identity, fake engagement, or scraping violation is present.
- Payment/revenue mechanism is reasonably clear.
- Any required mitigations are simple and enforceable.

`proceed` does not mean execute immediately. The caller still needs `moneybot_policy_guard`, budget approval, and ledger recording.

### `reject`

Use when:

- Terms prohibit the planned action.
- The opportunity requires fake accounts, fake reviews, fake traffic, referral abuse, scraping against terms, or spam.
- The opportunity involves regulated financial activity, gambling, prediction markets, trading, money transmission, or handling funds for others.
- Payment is deceptive, impossible to verify, or structured like a scam.
- The activity requires unauthorized security testing or exploit deployment.
- The opportunity is likely illegal or materially deceptive.

### `human_review`

Use when:

- Terms are complex or ambiguous.
- The activity is legal but reputationally risky.
- The action involves public claims that may need substantiation.
- The activity involves personal data, user tracking, affiliate marketing, advertising, or cold outreach.
- The opportunity has meaningful financial, tax, contractual, or account-ban consequences.

### `insufficient_information`

Use when:

- Terms/rules/payment details are not accessible.
- Source URLs are missing.
- The action is too vague to evaluate.
- The bot cannot verify whether the planned action is permitted.

Do not allow execution on `insufficient_information`.

## Red-Flag Taxonomy

Use these labels consistently:

```text
regulated_finance
gambling_or_prediction_market
autonomous_trading
money_transmission
third_party_funds
kyc_evasion
fake_identity
fake_accounts
fake_reviews
spam
bulk_outreach
scraping_prohibited
automation_prohibited
captcha_bypass
account_farming
unauthorized_security_testing
malware_or_credential_theft
copyright_or_ip_issue
privacy_issue
unsupported_claims
unclear_payment
recurring_charge_risk
refund_or_chargeback_risk
unknown_counterparty
regional_restriction
```

## Required Evidence Handling

For every proceed/human_review decision, provide at least one evidence object when possible. Evidence can be a summarized policy section, bounty rules page, FAQ, marketplace rules, or payment terms.

Do not quote long copyrighted passages. Summarize relevant sections.

## Integration

- `opportunity_scout` calls this skill for candidates worth further research.
- `moneybot_policy_guard` consumes this skill's output.
- `budget_and_roi_planner` must not create an executable experiment unless this skill returns `proceed` or an explicitly reviewed `human_review` result.
- `receipt_and_evidence_archiver` stores the source pages and terms summary.

## Failure Behavior

If the bot cannot load the terms page:

```json
{
  "decision": "insufficient_information",
  "confidence": "high",
  "risk_level": "medium",
  "terms_available": false,
  "allowed_by_terms": "unclear",
  "required_mitigations": ["Retrieve platform terms or use a different opportunity"],
  "must_call_policy_guard": true,
  "must_create_ledger_record": false
}
```

## Test Cases

### Allowed: Clear Contest Rules

Input: Contest rules state solo submissions are allowed, no entry fee, clear prize, no prohibited automation.

Expected: `proceed`, low/medium risk depending on claims and submission requirements.

### Rejected: Scraping Against Terms

Input: Planned action requires scraping a site whose terms prohibit automated scraping.

Expected: `reject`, red flag `scraping_prohibited`.

### Human Review: Affiliate Marketing

Input: Affiliate program allows promotion but requires disclosure and prohibits spam.

Expected: `human_review` or `proceed` with strict mitigations depending on planned channel.

### Rejected: Security Testing Without Scope

Input: Bot proposes finding bugs on a live service without a bounty program scope.

Expected: `reject`, red flag `unauthorized_security_testing`.
