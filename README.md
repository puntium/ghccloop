# ghccloop

These are a quick example of a claude-code + github issues powered audomated development loop.


## Files


- dr.md and dev.md: example claude code commands for a two step plan+code process. Generates documentation + plan in local file tree. Easy way to experiment with multi-step process using claude code. Can be dropped into .claude/commands folder

- gdr.md gdrevise.md gdev.md gdevrevise.md: commands used by the claude-loop.py script

- claude-loop.py: script that implements the github workflow.
   - requires an active git checkout of a repo
   - requires a configured github client (gh) to work in that repo
   - requires command files above to be installed in user's or project .claude/commands
