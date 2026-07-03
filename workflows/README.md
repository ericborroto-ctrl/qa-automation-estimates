# Workflows

This directory contains markdown-based Standard Operating Procedures (SOPs) that define how the AI agent should execute various tasks.

## Workflow Structure

Each workflow should include:

1. **Objective**: What this workflow accomplishes
2. **Required Inputs**: What information/data is needed to start
3. **Tools Used**: Which scripts from `tools/` are executed
4. **Expected Outputs**: What gets generated (usually cloud deliverables)
5. **Edge Cases**: Known issues, rate limits, error handling approaches

## Creating Workflows

Write workflows in plain language, as if briefing a team member. The AI agent reads these instructions to orchestrate tool execution.

### Example Template

```markdown
# Workflow Name

## Objective
Brief description of what this workflow accomplishes

## Required Inputs
- Input 1: Description
- Input 2: Description

## Tools Used
- `tools/script_name.py`: What it does

## Steps
1. Step one
2. Step two
3. Step three

## Expected Outputs
- Where deliverables are stored
- Format and structure

## Edge Cases
- Known limitations
- Error handling approaches
- Rate limits or timing considerations
```

## Best Practices

- Keep workflows updated as you learn
- Document failures and solutions
- Include rate limits and API constraints
- Specify error recovery approaches
