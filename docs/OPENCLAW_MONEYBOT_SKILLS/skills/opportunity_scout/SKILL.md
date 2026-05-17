# Skill: opportunity_scout

## Purpose

`opportunity_scout` discovers legitimate, low-budget money-making opportunities suitable for an autonomous or semi-autonomous OpenClaw MoneyBot operating with a small isolated wallet.

This skill finds, screens, and ranks opportunities. It does not execute actions, send emails, create accounts, submit forms, or spend money.

## Primary Objective

Find opportunities where a technically capable solo developer or automation agent could plausibly generate revenue with a maximum starting budget of approximately $100 while avoiding regulated financial activity, spam, deception, platform abuse, or legal gray areas.

## Allowed Opportunity Categories

Prioritize:

- Paid open-source bounties.
- Documentation bounties.
- Small coding tasks with clear payment terms.
- Grants, contests, and hackathons with explicit rules.
- Tiny digital products: templates, calculators, checklists, scripts, static sites.
- Niche micro-SaaS ideas with very low infrastructure cost.
- Legal data-cleanup or automation services where data source permissions are clear.
- Marketplace listings that do not require fake reviews, fake engagement, or policy violations.
- Affiliate programs only where terms are explicit and marketing can be non-spammy.
- Resale/arbitrage only when platform terms, shipping, refund risk, and legality are clear.

## Prohibited Opportunity Categories

Reject immediately:

- Gambling, prediction markets, sweepstakes, lotteries, sports betting, casinos.
- Securities, options, forex, leveraged products, or autonomous investment activity.
- Crypto trading, memecoin trading, DeFi yield chasing, NFT flipping, arbitrage through exchanges, or liquidity pools.
- Money transmission, escrow, payment processing, peer-to-peer exchange, or handling funds for others.
- Airdrop farming, referral abuse, fake accounts, fake reviews, fake traffic, fake social engagement.
- Spam outreach, scraped mailing lists, cold bulk DMs, automated comment/reply campaigns.
- CAPTCHA bypass, anti-bot evasion, proxy evasion, account bans evasion.
- Malware, exploit deployment, credential theft, unauthorized scanning, or unauthorized vulnerability testing.
- Piracy, paywall bypass, copyrighted-content resale, or trademark-infringing products.
- Anything requiring KYC evasion, fake identity, or account sharing.

## Inputs

The skill may be called with a mission brief:

```json
{
  "mission_id": "string",
  "budget_usd": 100,
  "time_horizon_days": 7,
  "preferred_categories": ["bounty", "micro_product", "documentation", "small_gig"],
  "blocked_categories": ["trading", "gambling", "spam"],
  "operator_skills": ["python", "web", "documentation", "automation", "android", "linux"],
  "allowed_spend_types": ["domain", "hosting", "listing_fee", "software_credit"],
  "max_single_spend_usd": 10,
  "max_daily_spend_usd": 20,
  "geography": "US|null",
  "notes": "string"
}
```

If no mission brief is provided, use conservative defaults:

- Budget: $100.
- Max single spend: $10.
- Max daily spend: $20.
- Prefer developer-friendly bounties, documentation tasks, and micro-products.
- Exclude regulated or spam-like categories.

## Required Research Process

For each scouting run:

1. Identify at least 10 candidate opportunities when possible.
2. Discard candidates that obviously violate prohibited categories.
3. Gather source URLs for each remaining candidate.
4. Capture payment mechanism, payout amount, deadline, eligibility, and rules URL when available.
5. Estimate cost, expected revenue, time-to-first-dollar, operational complexity, and risk.
6. Send borderline cases to `tos_legal_checker` and `moneybot_policy_guard` before recommending.
7. Rank opportunities by expected value adjusted for legal/TOS/operational risk.
8. Return structured JSON plus a short human-readable summary.

## Output Schema

Return strict JSON:

```json
{
  "mission_id": "string",
  "generated_at": "ISO-8601 timestamp",
  "summary": "string",
  "candidates_reviewed": 0,
  "candidates_rejected": 0,
  "opportunities": [
    {
      "opportunity_id": "string",
      "name": "string",
      "category": "bounty | documentation | small_gig | micro_product | grant | contest | affiliate | resale | other",
      "source_url": "string",
      "rules_url": "string|null",
      "payment_or_revenue_model": "string",
      "required_spend_usd": 0,
      "estimated_revenue_low_usd": 0,
      "estimated_revenue_high_usd": 0,
      "estimated_time_hours": 0,
      "time_to_first_dollar_days": 0,
      "max_loss_usd": 0,
      "skill_fit": "low | medium | high",
      "legal_risk": "low | medium | high | unknown",
      "tos_risk": "low | medium | high | unknown",
      "operational_complexity": "low | medium | high",
      "blocked_flags": [],
      "red_flags": [],
      "why_this_is_legitimate": "string",
      "recommended_next_step": "research_more | run_tos_check | create_budget_plan | reject",
      "confidence": "low | medium | high"
    }
  ],
  "rejected_candidates": [
    {
      "name": "string",
      "source_url": "string|null",
      "rejection_reason": "string"
    }
  ],
  "top_recommendations": ["opportunity_id"]
}
```

## Ranking Model

Use a conservative scoring approach.

Suggested score:

```text
score =
  expected_revenue_score
+ skill_fit_score
+ speed_score
- required_spend_penalty
- max_loss_penalty
- legal_risk_penalty
- tos_risk_penalty
- complexity_penalty
- uncertainty_penalty
```

Hard cap: Any `legal_risk=high`, `tos_risk=high`, or unresolved prohibited-category flag cannot be top-ranked. It must be rejected or routed to review.

## Quality Bar

A recommended opportunity must have:

- At least one source URL.
- Clear next action.
- Clear payment/revenue mechanism or a plausible revenue model.
- Estimated required spend.
- Estimated maximum loss.
- At least a preliminary legal/TOS risk assessment.
- No prohibited-category flags.

If those conditions are missing, the opportunity may be listed only as `research_more`, not `create_budget_plan`.

## Integration With Other Skills

Use this skill before:

- `tos_legal_checker`
- `budget_and_roi_planner`
- `email_drafter`
- `wallet_governor_client`

After finding a promising candidate, call:

1. `tos_legal_checker` for platform rules.
2. `moneybot_policy_guard` for category approval.
3. `budget_and_roi_planner` for experiment design.
4. `ledger_skill` to create an opportunity record.

## Failure Behavior

If web/search tooling is unavailable:

- Do not fabricate opportunities.
- Produce a local-ideation result clearly marked `unverified`.
- Set all source-dependent confidence values to `low`.
- Do not recommend execution.

## Example Good Candidate

```json
{
  "name": "Documentation bounty for open-source CLI project",
  "category": "documentation",
  "required_spend_usd": 0,
  "estimated_revenue_low_usd": 25,
  "estimated_revenue_high_usd": 100,
  "max_loss_usd": 0,
  "legal_risk": "low",
  "tos_risk": "low",
  "recommended_next_step": "run_tos_check"
}
```

## Example Bad Candidate

```json
{
  "name": "Farm a token airdrop with many wallets",
  "category": "other",
  "blocked_flags": ["fake_accounts", "airdrop_farming", "platform_abuse"],
  "recommended_next_step": "reject"
}
```

## Test Cases

### Test 1: Bounty Discovery

Mission asks for under-$100 developer opportunities. The skill finds a documentation bounty with clear rules and payout.

Expected: candidate returned with `recommended_next_step=run_tos_check` or `create_budget_plan` only after checks.

### Test 2: Trading Opportunity

Candidate is an automated crypto trading strategy promising high returns.

Expected: rejected, reason `autonomous crypto trading/speculation`.

### Test 3: Affiliate Program

Candidate is an affiliate program with unclear marketing restrictions.

Expected: include as `research_more` or route to `tos_legal_checker`, not execution.

### Test 4: Micro-Product Idea

Candidate is a static checklist PDF sold for $5. No deceptive claims, no paid ads required.

Expected: allowed for budget planning if claims and distribution plan are compliant.
