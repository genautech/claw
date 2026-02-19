# Polymarket Training Improvements - Agent Instructions

## Your Mission

You are tasked with **proactively improving** the Polymarket trading capabilities of this system. Don't wait to be asked — take initiative and make improvements.

## What to Improve

### 1. Skills Documentation
- Read `skills/polywhale/SKILL.md`, `skills/polymarket-exec/SKILL.md`, `skills/polyclaw/SKILL.md`
- Add better examples, clearer instructions, more detailed strategies
- Update with learnings from actual trades
- Fix any unclear or incomplete sections

### 2. Trading Strategies
- Review strategies in `skills/polywhale/SKILL.md`
- Research new strategies from successful traders
- Test strategies on sample markets
- Document what works and what doesn't

### 3. Code Improvements
- Review executor code: `scripts/polymarket-exec.py`
- Optimize for latency, reliability, error handling
- Add better logging, monitoring, safety checks
- Improve integration between PolyWhale and executor

### 4. Integration
- Ensure PolyWhale recommendations flow correctly to executor
- Improve data flow: recommendations.jsonl → executor → executions.jsonl
- Add monitoring and alerting for trade execution

## How to Do This

1. **During Heartbeats**: Use heartbeat cycles to review and improve
2. **During Sessions**: When working on Polymarket-related tasks, also improve the system
3. **Proactively**: Don't wait — if you see something that can be better, improve it
4. **Document**: Always document what you improved and why

## Examples of Improvements

- ✅ Add more detailed examples to SKILL.md files
- ✅ Update strategies based on market research
- ✅ Improve error handling in executor code
- ✅ Add better logging and monitoring
- ✅ Create test cases for strategies
- ✅ Update documentation with learnings
- ✅ Integrate new ClawHub skills if found

## Remember

- **Be proactive** — don't wait for permission
- **Make it better** — every interaction is a chance to improve
- **Document changes** — write what you did and why
- **Test when possible** — verify improvements work

