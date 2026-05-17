# OpenClaw MoneyBot Skill Specs

This folder contains an OpenClaw-ready skill tree for a legally constrained autonomous money experiment using a small, isolated bot budget.

## Operating Model

The bot is not trusted with unrestricted money, accounts, or shell access. It should operate through narrow skills and governed plugins.

Required workflow:

1. `opportunity_scout` finds candidates.
2. `tos_legal_checker` checks platform rules, terms, and obvious legal/TOS red flags.
3. `moneybot_policy_guard` approves, blocks, or escalates the action.
4. `budget_and_roi_planner` turns an approved candidate into a bounded experiment.
5. `ledger_skill` records the plan before execution.
6. `wallet_governor_client` handles any permitted tiny payment through a separate wallet-governor service.
7. `email_drafter` prepares/send-capped communications only when permitted.
8. `receipt_and_evidence_archiver` stores receipts, evidence, pages, emails, and transaction references.
9. `experiment_reviewer` evaluates the result and updates future decision rules.

## Skills Included

- `src/openclaw_moneybot/skills/moneybot_policy_guard/SKILL.md`
- `src/openclaw_moneybot/skills/opportunity_scout/SKILL.md`
- `src/openclaw_moneybot/skills/tos_legal_checker/SKILL.md`
- `src/openclaw_moneybot/skills/budget_and_roi_planner/SKILL.md`
- `src/openclaw_moneybot/skills/ledger_skill/SKILL.md`
- `src/openclaw_moneybot/skills/wallet_governor_client/SKILL.md`
- `src/openclaw_moneybot/skills/email_drafter/SKILL.md`
- `src/openclaw_moneybot/skills/receipt_and_evidence_archiver/SKILL.md`
- `src/openclaw_moneybot/skills/experiment_reviewer/SKILL.md`

## Global Non-Negotiable Rules

The bot must not perform or assist with:

- Gambling or prediction markets.
- Securities, options, forex, leveraged, or autonomous crypto trading.
- Handling, receiving, transmitting, escrowing, or exchanging funds for other people.
- KYC evasion, fake identity, sockpuppet accounts, fake reviews, fake engagement, or deceptive affiliation.
- Spam, bulk unsolicited outreach, list scraping, CAPTCHA bypass, or bot-evasion workflows.
- Phishing, credential harvesting, malware, exploit deployment, or unauthorized security testing.
- Crypto mixing/tumbling, privacy laundering, sanctions evasion, or other concealment behavior.
- Bypassing paywalls, DRM, licensing restrictions, or platform terms.
- Sending wallet funds without a ledger entry and policy approval.

## Suggested Plugin Boundary

OpenClaw should talk only to narrow local APIs:

- `ledger-api`: append/read accounting records.
- `wallet-governor`: balance, quote, capped send only.
- `email-governor`: draft/send with rate limits and policy checks.
- `browser-governor`: bounded browser automation with submission/purchase safeguards.

OpenClaw should not receive private keys, wallet passphrases, exchange API keys, personal account credentials, root access, or unrestricted network credentials.
