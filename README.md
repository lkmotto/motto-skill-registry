# motto-skills

Portable personal Factory skills bundle for fast agent stand-up on new machines.

## Quick stand-up

```bash
git clone https://github.com/lkmotto/motto-skills.git "$HOME/motto-skills"
cd "$HOME/motto-skills"
bash install.sh
```

Done — skills are installed into `~/.factory/skills/`.

## Fast Agent Standup

Bring a brand-new machine or agent fully online in one step. `standup.sh`
installs the skills, then installs the required CLIs (idempotent — already
present tools are skipped), and prints a readiness summary.

```bash
git clone https://github.com/lkmotto/motto-skills.git "$HOME/motto-skills"
cd "$HOME/motto-skills"
bash standup.sh
```

That's it. See [STANDUP.md](STANDUP.md) for prerequisites and verification.
