# Security (summary)

- Use SSH keys for login, disable root/password login.
- UFW: allow SSH, HTTP, HTTPS; default deny incoming.
- Enable Fail2Ban for SSH brute-force protection.
- Never commit `.env` with real secrets.
