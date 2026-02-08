EOD_INSTRUCTION = """You are wrapping up the trading day. The trading loop has ended.

Reason for stopping: {stop_reason}

Your tasks:
1. Review all trades taken today (check positions and trade diary)
2. For each trade, write a diary entry with:
   - Entry/exit rationale
   - What you learned
   - What mistakes were made (be honest and self-critical)
3. Write a daily summary covering:
   - Market conditions today
   - What worked and what didn't
   - Key takeaways for tomorrow
4. Log the EOD summary as a decision

Be thorough in self-reflection. The diary is your memory for future trading days."""
