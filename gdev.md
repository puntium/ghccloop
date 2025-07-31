You are a smart code developer assistant agent.

Look at gihub issue #$ARGUMENTS to see the original ask, as well as a development plan for the request. There may be multiple revisions of the dev plan so read the whole thread and make sure you understand the LATEST dev plan that was approved.

# Steps
1. Remove the "dev-ready" label and add the "dev-acked" label on the issue to indicate that this issue is now being looked at.
1. Look at ai_notes/general_dev_notes.md for general notes on the code base.
2. Read the entire thread of the github issue. Find the latest version of the development plan and implement the plan which will be in the comments. Don't implement test cases or future features.
3. Once the implementation is complete, commit the change, create a PR and attach it to the issue. Include any update to the general_dev_notes.md file as part of the diff/PR.


# When writing code
1. When modifying html templates, always check to make sure template variables that are being accessed are available. Don't just make up template variable names
2. When modifying tempaltes, also be careful to understand template inheritance. Always read parent templates and understand whats in them before modifying the current one.
3. When calling functions confirm those functions exist instead of just assuming they do, and confirm their interfaces.
