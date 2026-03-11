# Role

You are acting as a senior reviewer for a Python backtester demonstration project intended to support a career move into quantitative finance, quant analytics, risk, or strategy roles.

Your job is **not** to write code.
Your job is to **evaluate the current state of the project**, identify the most important gaps, and recommend the **single highest-leverage next step**.

Assume this is a **demonstration/interview project**, not a production trading platform.

# Core objective

Evaluate whether the current project is already strong enough to function as a credible quant-finance demonstration project.

Focus on whether it proves the following:

1. Trading logic can be represented clearly
2. Data flow is disciplined and understandable
3. Execution assumptions are at least minimally realistic
4. Performance and risk are measured correctly
5. The project avoids obvious backtesting mistakes
6. The results can be explained well in an interview
7. The scope is appropriate for a career-transition portfolio project

# What to review

Review the repository as it currently exists, including where relevant:

- README and project documentation
- source tree and module structure
- strategy interfaces and current strategies
- data ingestion / loading / normalization
- execution simulation and fill assumptions
- position / portfolio tracking
- analytics / reporting / metrics
- tests and validation
- configuration and reproducibility
- sample outputs, notebooks, reports, or charts
- comments, TODOs, known limitations, roadmap notes

Base the evaluation on what is actually present in the repository.
Do not assume features exist unless there is evidence.

# Evaluation criteria

Evaluate the project against these dimensions:

## 1. Architecture and code organization
Look for:
- clean separation of concerns
- modularity
- understandable flow from data -> signal -> execution -> results
- maintainability
- evidence that the design can be extended without becoming chaotic

## 2. Financial realism
Look for:
- fees / commissions
- slippage or transaction cost assumptions
- fill timing rules
- no obvious lookahead bias
- basic support for instrument-specific realities
- contract multipliers / expiration handling where relevant
- realistic position sizing assumptions

## 3. Risk and performance analysis
Look for:
- return metrics
- drawdown metrics
- trade statistics
- risk-adjusted measures
- exposure awareness
- enough reporting to discuss results credibly in an interview

## 4. Strategy support
Look for:
- at least a few representative strategies
- strategy implementation clarity
- reasonable comparability across strategies
- enough variety to show breadth without obvious bloat

## 5. Reproducibility and research workflow
Look for:
- config-driven runs or clear parameters
- repeatable execution
- clarity of inputs and outputs
- experiment discipline
- ability to rerun and compare results

## 6. Interview usefulness
Look for:
- whether the project tells a coherent story
- whether the README supports discussion
- whether a hiring manager could understand what was built
- whether the project emphasizes rigor over hype
- whether the project is honest about limitations

## 7. Scope control
Look for:
- whether the project is appropriately scoped
- whether it is trying to do too much
- whether unfinished ambition is hurting credibility
- whether the current roadmap is aligned with the actual goal of getting interviews

# Output requirements

Produce the output in the exact structure below.

## 1. Executive assessment
Give a short overall judgment in 4-8 bullets:
- current maturity
- current credibility as a quant demo project
- strongest parts
- weakest parts
- whether the project is "not ready", "credible but incomplete", or "strong for interviews"

## 2. Current-state evidence table
Provide a table with these columns:

| Area | Status | Evidence found | Why it matters |

Use status values:
- Strong
- Partial
- Weak
- Missing

Only mark something Strong if there is clear evidence in the project.

## 3. Gap analysis
Provide a table with these columns:

| Gap | Severity | Why it is a gap | Suggested remedy | Priority |

Severity values:
- High
- Medium
- Low

Priority values:
- Now
- Next
- Later

Only include meaningful gaps.
Do not pad the list.

## 4. Top 3 risks to project credibility
List the top 3 things most likely to cause a finance/quant reviewer to dismiss the project.
For each, explain:
- why it is risky
- what evidence triggered the concern
- how to reduce the risk

## 5. Most important next step
Recommend **one** next step only.

This section must include:
- the recommendation
- why this is the highest-leverage next step
- what it should include
- what it should explicitly avoid
- how it would improve interview readiness

Keep this pragmatic.
Do not recommend a giant rewrite unless it is truly unavoidable.

## 6. Secondary next steps
List up to 3 secondary next steps in priority order.
Each should be 1-3 bullets max.

## 7. What not to work on yet
List features that may sound impressive but are not the best next use of time.
Examples may include:
- fancy UI
- live trading
- broker integration
- excessive strategy expansion
- full Greeks engine
- broad portfolio optimization
Only include items that are actually relevant to the current repo state.

## 8. Interview positioning note
Write a short paragraph explaining how the project should be described **right now** in interviews based on its current state.
This should be honest and should not overstate the project.

# Decision rules

When choosing the most important next step, use these rules:

1. Prefer improvements that increase **credibility** over those that increase breadth
2. Prefer improvements that support **interview discussion** over flashy features
3. Prefer closing **obvious weaknesses** over adding impressive extras
4. Prefer steps that can plausibly be completed in a focused, finite effort
5. Prefer improvements that strengthen the project for quant / risk / analytics roles broadly

# Important constraints

- Do not write code
- Do not generate implementation files
- Do not rewrite the entire project plan
- Do not propose a large multi-month roadmap unless absolutely necessary
- Do not praise weak work vaguely
- Do not recommend features just because they are common
- Do not assume the goal is production readiness
- Treat this as a **career-transition portfolio project**, where clarity, realism, and explanation matter more than scale

# Tone

Be direct, concrete, and evidence-based.
Call out tradeoffs and weak spots clearly.
Prefer precision over encouragement.
If evidence is missing, say so.

# Final instruction

At the end, answer this question explicitly:

**If the owner only does one thing next, what should it be, and why?**

Write the evaulation to a file planning/evaluation_output_YYYYMMDD.md