---
name: self-calibrating-autonomy
version: 1.0.0
description: |
  Learns your actual escalation preferences over time from approval/rejection patterns.
  Builds a dynamic policy that determines which decisions auto-approve vs escalate.
  Minimizes interruptions while respecting revealed preferences. The policy is
  versioned, auditable, and continuously refined.
when_to_use: |
  Automatically before any decision that could be escalated. Also on manual
  "calibrate autonomy", "review autonomy policy", "show escalation rules",
  "update autonomy settings". Periodic policy review every 2 weeks.
tags: [self-learning, autonomy, policy, calibration, escalation, preferences]
---

# Self-Calibrating Autonomy

Static autonomy levels (`auto-high`) treat every decision the same. They shouldn't.
This skill learns what you actually care about and auto-approves the rest.

## Activation

- **Auto-trigger**: Before making any potentially escalable decision
- **Manual trigger**: "calibrate autonomy", "show escalation rules", "update autonomy"
- **Learning trigger**: Every time you approve or reject an escalated decision
- **Periodic review**: Every 2 weeks, review and refine policy

## Step 1 — Decision Classification

Every decision that could be escalated falls into one of these classes:

| Decision Class          | Examples                                              | Default Risk |
|--------------------------|-------------------------------------------------------|-------------|
| `credential_write`       | Writing to Doppler secrets, Bitwarden update          | high        |
| `credential_read`        | Reading Doppler secrets, Bitwarden for lookup         | medium      |
| `library_choice`         | Choosing between OSS libraries (recycler protocol)    | medium      |
| `architecture_decision`   | API design, data flow, component boundaries           | high        |
| `deployment_action`      | Pushing code, deploying to Cloudflare/Vercel          | high        |
| `config_change`          | Modifying skill files, MCP config, settings           | medium      |
| `skill_creation`         | Creating or modifying skills, droids, templates       | low         |
| `file_write_project`     | Creating/modifying project files in working repos     | low         |
| `file_write_system`      | Creating/modifying files in ~/.factory or system-wide | medium      |
| `external_api_call`      | Calling external APIs (non-destructive)                | low         |
| `external_api_mutation`  | Calling external APIs that create/update/delete       | high        |
| `tool_install`           | Installing new tools, MCPs, npm/pip packages          | medium      |

## Step 2 — Learn From History

Analyze `knowledge/decisions.jsonl` for patterns:

### Approval Ratio Per Class
For each decision class, compute:
```
approval_ratio = approved / (approved + rejected) over last 30 days
```

### Escalation Outcome Tracking
When a decision IS escalated to you:
- Record the decision class, context, and your response
- Update the approval ratio for that class
- If you modified the proposal: note what you changed (this is the most valuable signal)

### Automatic Policy Adjustment

| Approval Ratio | Action                                      |
|----------------|---------------------------------------------|
| >= 90% (N>=10) | Auto-approve this class (silent)            |
| >= 80% (N>=5)  | Auto-approve with brief notification        |
| 50-80%         | Keep escalating, but pre-fill with best guess |
| < 50%          | Always escalate with clear alternatives     |
| Insufficient N | Keep default risk-based policy              |

## Step 3 — Build Autonomy Policy

Store in `~/.factory/knowledge/autonomy-policy.json`:

```json
{
  "version": 3,
  "generated": "ISO-8601",
  "based_on": "30 days, 24 decisions",
  "rules": [
    {
      "class": "credential_write",
      "auto_approve": false,
      "mode": "escalate_always",
      "reason": "Approval ratio 20% (2/10), user consistently rejects or modifies"
    },
    {
      "class": "file_write_project",
      "auto_approve": true,
      "mode": "silent",
      "reason": "Approval ratio 100% (15/15), user never rejects"
    },
    {
      "class": "skill_creation",
      "auto_approve": true,
      "mode": "notify",
      "reason": "Approval ratio 88% (7/8), user modifies occasionally"
    },
    {
      "class": "library_choice",
      "auto_approve": false,
      "mode": "escalate_always",
      "reason": "Approval ratio 33% (2/6), user wants input on library decisions"
    }
  ],
  "safety_overrides": {
    "always_escalate": ["credential_write", "deployment_action", "external_api_mutation"],
    "never_auto_if": "decision involves production systems or user data"
  }
}
```

## Step 4 — Apply Policy at Decision Time

Before making a decision:

1. Classify the decision
2. Look up policy in autonomy-policy.json
3. Apply:

```
if rule.auto_approve:
    if rule.mode == "silent":
        proceed, log decision
    if rule.mode == "notify":
        proceed, add brief note in output
else:
    escalate with:
    - Clear context (what we're doing, why)
    - Best-guess recommendation
    - One specific question to answer
```

4. Log the decision outcome (approved/rejected/modified) for future learning

## Step 5 — Safety Overrides (Immutable)

These rules CANNOT be overridden by learned policy:

- **Always escalate**: credential writes, deployment actions, destructive API calls
- **Never auto if**: action involves production systems, user personal data, or financial transactions
- **Risk floor**: no decision above `medium` default risk can be auto-approved without 10+ successful approvals
- **Reversion trigger**: if any auto-approved decision is later reverted or causes an error, immediately revert that class to `escalate_always` for 14 days

## Step 6 — Periodic Policy Review

Every 2 weeks:
1. Compute new approval ratios from last 30 days
2. Generate proposed policy changes
3. Show diff from current policy
4. Ask: "Apply these autonomy updates?" (one question, one yes/no)

The policy file is versioned — each update creates a new version with timestamp.

## Step 7 — Transparency

At any time, the user can ask:
- "What decisions are you auto-approving?" → list silent + notify rules
- "What are you escalating?" → list escalate_always rules
- "Why is X being escalated?" → show the approval ratio and rule
- "Stop auto-approving Y" → override specific class to escalate_always

## Output Contract

- Updated `knowledge/autonomy-policy.json`
- At decision time: auto-proceed or escalate
- Bi-weekly review: proposed policy diff
- On user command: transparency report

## Guardrails

- Safety overrides are immutable and visible in the policy file
- Every auto-approved decision is still logged (auditable)
- Policy changes are versioned with timestamps
- A bad auto-approval triggers immediate reversion
- Never auto-approve anything involving: credentials, deployments, production, money, user data

## Integration Points

- **decision-log**: Source of approval/rejection data
- **readiness-gate**: Uses autonomy policy for pre-task decisions
- **session-postmortem**: Post-session review may surface incorrect auto-approvals
- **tool-auto-provisioner**: Uses autonomy to decide whether to auto-build
