# Phase 4.0.1 Discovery Calibration

Phase 4.0.1 separates **security work** from **software-engineering work**.

## Security-title gate

A candidate title must contain a security-domain signal such as Security, AppSec, Product Security, Cybersecurity, Red Team, Offensive Security, Incident Response, IAM, or GRC. Generic AI, platform, engineering, or strategy titles do not qualify solely because they overlap words in configured target titles.

## Software-engineering exclusion

When `exclude_software_engineering_roles` is enabled, explicit software-development title families are rejected, including Software Engineer, Software Developer, Backend Engineer, Frontend Engineer, and Full Stack Engineer. This also excludes titles such as `Security Software Engineer` because the underlying role family is software engineering.

`Security Engineer` and `Product Security Engineer` remain eligible because those titles are used broadly for security roles that may not be coding-heavy.

## Heavy-coding exclusion

When `exclude_heavy_coding_roles` is enabled, the JD is scanned for multiple strong production-coding signals. A single mention of Python, Go, or security automation is not enough to reject the role. Strong indicators include explicit production-code ownership, required software-engineering tenure, hands-on coding as a core duty, and building/maintaining software services.

## Salary fallback

Salary extraction now compacts whitespace before matching. This supports ATS descriptions where labels and ranges are separated by HTML/newline formatting.

## Duplicate postings

Same-board duplicate external IDs are processed once per run. `surfaced` is therefore a unique-posting count for each source run.
