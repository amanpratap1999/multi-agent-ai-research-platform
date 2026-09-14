# TODOS

## Automated Blue SRE Guardrail Policy Patching
- **What**: An autonomous "Blue SRE" agent loop that listens for PyRIT red team bypass findings, extracts the adversarial prompt trace, automatically synthesizes an updated Bedrock Guardrail policy rule (regex, denied topic, or prompt countermeasure), updates the guardrail via AWS Bedrock API (`CreateGuardrailVersion`), and re-executes the attack to prove zero-day remediation live.
- **Why**: Transforms the platform from passive vulnerability detection into a self-immunizing, co-evolving cyber range.
- **Pros**: Exceptional demonstration of autonomous AI systems engineering; closes the loop between offensive testing and defensive policy synthesis.
- **Cons**: Requires complex guardrail synthesis prompt tuning and AWS IAM permissions to mutate live Bedrock Guardrail configurations.
- **Context**: Explored during Office Hours brainstorming (Approach C); deferred to post-launch to keep initial 4-agent pipeline and War Room delivery airtight.
- **Depends on / blocked by**: Completion of core 4-agent LangGraph pipeline, PyRIT attack runner, and AWS Bedrock deployment.
