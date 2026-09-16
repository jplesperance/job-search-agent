# Career Knowledge Base v1 — Review Guide
This dataset is the Phase 1 seed knowledge base for the job-agent system. It is designed to be authoritative input for later job-match and resume agents, not a resume itself.
## Dataset summary
- Experiences: **20**
- Evidence items: **251**
- Skills: **77**
- Technologies: **65**
- Frameworks/control concepts: **15**
- Certifications: **5**
- User-verified evidence: **249**
- Source-only evidence: **2**

## Agent rules encoded in the dataset
- **HARD** — Wiscasset Web Development role must not be represented as company ownership. Canonical title is Lead Developer; business_owner=false.
- **HARD** — Hilton “Lead Application Security Architect” was a leveling title, not a people-management or functional-team-lead role.
- **HARD** — TikTok SSDLC handled AI Safety only for approximately the first three months of tenure; it then transitioned to a dedicated Content Assurance team, with ongoing partnership.
- **HARD** — Do not conflate ~40/month on the consolidated Lark/Meegle intake with the separate 40–50/day intake channel.
- **HARD** — Evernote attack evidence concerns large-scale user-account compromise/data-access attempts; do not characterize it as a confirmed compromise of Evernote infrastructure.
- **HARD** — Apixio did not process payment data; do not imply PCI work was driven by payment processing unless later verified.
- **HARD** — Do not attribute post-launch production metrics to Ricoh tenure because user left before public launch.
- **HARD** — Do not state that the CBS unified video pipeline performed transcoding unless later verified; user said it probably did.
- **HARD** — Do not infer people management from titles containing Lead/Principal/Architect; use explicit experience attributes/evidence.

## Unresolved items
- **Compliance framework naming** — Resolved: “HIPAA High Trust” was clarified by the user to mean HIPAA and HITRUST.
- **Tool/product identification** — Resolved: Hilton used Checkmarx for SAST.
- **Pipeline detail** — Video conversion/transcoding may have been part of the unified video pipeline, but user was not certain.
- **Supplemental experience status** — Resolved: CionSystems and Cuemby advisory-board roles were removed from the maintained career record at the user’s direction.

## Evidence by experience

### TikTok USDS JVc — Senior SSDLC Specialist / Tech-Lead
Evidence items: **27**

- `TT-LEAD-001` Technically led a six-person functional security team, defining priorities, team strategy, partnerships, and work assignments. — *6-person functional team*
- `TT-LEAD-002` Performed delegated people-management responsibilities for the functional team, including coaching and performance feedback. [generalize]
- `TT-AI-001` Architected AI-agent security workflows using Gemini and Google Vertex AI.
- `TT-AI-002` Developed Python-based AI-agent integrations with Lark, Meegle, and internal findings-management APIs. [generalize]
- `TT-AI-003` Automated portions of secure-design-review and threat-modeling workflows through agentic systems.
- `TT-TM-001` Automated mapping of identified threats/findings to the MITRE ATT&CK framework.
- `TT-TM-002` Automated generation of remediation guidance mapped to MITRE D3FEND.
- `TT-TM-003` Reduced manual security-assessment effort by approximately 20–30 hours per assessment/review through automated document analysis, threat mapping, and report generation. — *~20–30 hours saved per assessment/review*
- `TT-ARCH-001` Conducted secure-design reviews for infrastructure platforms supporting sale/distribution of AI models. [generalize]
- `TT-ARCH-002` Conducted security reviews for social-media applications and TikTok features/add-ons. [generalize]
- `TT-ARCH-003` Conducted security reviews for standalone applications, frequently involving AI functionality or integrations. [generalize]
- `TT-INTAKE-001` Consolidated five separate Meegle review projects/queues into a unified intake model to simplify request tracking and operational visibility. — *5 queues consolidated* [generalize]
- `TT-INTAKE-002` Designed a Lark-based intake bot that allowed users to initiate security reviews through a single interface and create the corresponding request in a consolidated Meegle queue. [generalize]
- `TT-SSDL-001` Standardized seven SSDLC security-review tracks: Application, Feature, Domain, AI/LLM Security, Chrome Extension, Endpoint Software, and Architectural Reviews. — *7 review tracks* [generalize]
- `TT-AISEC-001` Established AI/LLM security reviews using the OWASP LLM Top 10 and MITRE ATLAS as foundational threat frameworks.
- `TT-AISEC-002` Assessed AI/LLM systems for prompt injection, sensitive-data exposure, insecure output handling, authentication/authorization weaknesses, RAG risks, tool abuse, supply-chain concerns, and inadequate sandboxing.
- `TT-AISAFE-001` Initially participated in both AI/LLM security and AI Safety assessment responsibilities within the SSDLC team. [generalize]
- `TT-AISAFE-002` Continued partnering with the Content Assurance team after AI Safety responsibilities transitioned out of SSDLC. [generalize]
- `TT-OPS-001` The consolidated Lark/Meegle intake channel receives approximately 40 security-review requests per month. — *~40 requests/month* [internal_only]
- `TT-OPS-002` A separate SSDLC intake channel receives approximately 40–50 review requests per day. — *~40–50 requests/day* [internal_only]
- `TT-GOV-001` Identified that security findings previously existed only in reviewer-owned readiness reports, with no centralized vulnerability visibility or remediation tracking. [generalize]
- `TT-GOV-002` Established a process requiring open threats and vulnerabilities from security assessments to be entered into ByteSoc for SLA and remediation tracking. [generalize]
- `TT-GOV-003` Integrated SSDLC findings into the vulnerability-management workflow so findings receive ownership, SLA tracking, follow-up, and remediation accountability.
- `TT-REPORT-001` Defined technical Threat Model Reports for engineering audiences containing detailed findings and remediation-relevant technical context.
- `TT-REPORT-002` Defined Business Risk Reports that translate technical threat findings into business-risk context for leadership decision making.
- `TT-REPORT-003` Business Risk Reports were used by executive leadership, including the CEO, as input to product go/no-go decisions. [generalize]
- `TT-SLA-001` Reduced SSDLC review SLA from 14 business days to 5 business days using standardized report templates and AI-assisted analysis/report automation. — *14 days → 5 days (~64% reduction)*

### Hilton via Romack Inc — Lead Application Security Architect
Evidence items: **31**

- `HLT-SCOPE-001` Served on Hilton’s Application Security team supporting user-facing web applications across the enterprise.
- `HLT-SCOPE-002` Served as the primary AppSec architect for the Oracle OPERA implementation into Hilton’s ecosystem.
- `HLT-SCOPE-003` Provided application-security oversight for payment-related applications and changes.
- `HLT-SCOPE-004` Supported security reviews for Hilton for Business commercial applications. [generalize]
- `HLT-SCOPE-005` Assumed security-review responsibility for Hilton’s internally developed PEP hospitality-management platform near the end of the engagement. [generalize]
- `HLT-SSDLC-001` Embedded with development teams and participated in project meetings to provide security requirements and guidance throughout the development lifecycle.
- `HLT-ARCH-001` Reviewed application architectures, APIs, API payloads, and integration designs for security weaknesses and control requirements.
- `HLT-TEST-001` Incorporated SAST and DAST results into application-security assessments and remediation planning.
- `HLT-RISK-001` Produced project risk reports containing identified findings and estimated likelihood/probability of exploitation.
- `HLT-RISK-002` Partnered with Hilton Risk Management to combine exploitation likelihood with business impact into overall risk ratings.
- `HLT-RISK-003` Presented final application-security risk reports to business owners for formal risk acceptance or remediation decisions.
- `HLT-GOV-001` Hilton Security did not possess unilateral release-blocking authority; unresolved findings were escalated as risks requiring business-owner acceptance or engineering remediation. [generalize]
- `HLT-TOOLS-001` Used AuditBoard to track security reviews and findings.
- `HLT-TOOLS-002` Used ServiceNow as the security-review request/ticketing system, with review tickets automatically creating corresponding AuditBoard projects.
- `HLT-TOOLS-003` Worked in GitLab-based source-control and CI/CD environments.
- `HLT-TOOLS-004` Used Checkmarx for static application security testing (SAST) within Hilton application-security reviews.
- `HLT-OPERA-001` Reviewed bidirectional API flows carrying guest PII and payment data between Oracle OPERA and Hilton reservation systems.
- `HLT-OPERA-002` Assessed whether payment information handled by OPERA was stored and transmitted in accordance with Hilton PCI requirements.
- `HLT-OPERA-003` Reviewed Hilton-developed extensions built against OPERA APIs for unsupported functionality such as shared bookings.
- `HLT-OPERA-004` Evaluated custom booking/payment logic for flaws that could result in incorrect or unauthorized guest charges.
- `HLT-PAY-001` Performed AppSec review for implementation of guest buy-now-pay-later functionality.
- `HLT-PAY-002` Performed AppSec review for a long-term-stay commercial credit/payment capability supporting recurring charges against company credit arrangements. [generalize]
- `HLT-PAY-003` Reviewed payment APIs, cardholder-data flows, PCI scope, tokenization boundaries, encryption at rest/in transit, and API authentication between Hilton and third parties.
- `HLT-FIND-001` Worked with engineering teams throughout development to remediate issues during implementation rather than deferring all findings until release.
- `HLT-FIND-002` Large reviews could contain roughly 30–50 unresolved findings late in the lifecycle before additional remediation and risk reduction. — *~30–50 open findings late in large reviews* [internal_only]
- `HLT-FIND-003` Final risk reports commonly contained approximately 5–10 accepted/unresolved findings after remediation efforts. — *~5–10 residual findings* [internal_only]
- `HLT-FIND-004` Approximately one-third of findings across reviews were typically Critical or High severity. — *~1/3 Critical or High* [internal_only]
- `HLT-FIND-005` Identified payment-data handling concerns in a third-party platform, including a payload capable of transmitting up to 96 non-tokenized card numbers in one request. — *up to 96 non-tokenized card numbers/payload* [internal_only]
- `HLT-TECH-001` Performed manual threat modeling as part of application-security reviews.
- `HLT-TECH-002` Used SAST and DAST findings to drive targeted manual source-code review on large codebases.
- `HLT-TECH-003` Performed manual API security testing and escalated to dedicated penetration testing when initial testing warranted deeper validation.

### InfraGard SF Bay Area Members Alliance — Board Member – Secretary
Evidence items: **0**


### SentiLink — Principal Security Architect
Evidence items: **32**

- `STL-LEAD-001` Joined after approximately nine months without dedicated security personnel and rebuilt the security function.
- `STL-LEAD-002` Served as the primary owner of SentiLink’s security and compliance programs.
- `STL-LEAD-003` Hired a mid-level security engineer after approximately six months, primarily assigning that engineer responsibility for application security.
- `STL-FUNC-001` Owned vulnerability management, incident response/digital forensics, cloud security, DevSecOps, third-party risk, customer security, and compliance.
- `STL-CUST-001` Met directly with customers to address security questions and support customer security reviews.
- `STL-TPRM-001` Conducted and supported third-party security audits and assessments involving external organizations.
- `STL-COMP-001` Served as primary program owner for annual SOC 2 and PCI compliance cycles.
- `STL-COMP-002` Worked directly with external auditors each audit cycle and delegated evidence/control items to internal owners based on function.
- `STL-COMP-003` Maintained PCI and SOC 2 compliance through subsequent audit cycles with no exceptions. — *No audit exceptions during tenure*
- `STL-CLOUD-001` Operated primarily in an AWS environment using Kubernetes and serverless architectures.
- `STL-IAC-001` Used Terraform as the infrastructure-as-code platform.
- `STL-CICD-001` Worked with Jenkins-based CI/CD pipelines in a Python/Go engineering environment.
- `STL-IAM-001` Implemented Okta-based centralized authentication/authorization integration with AWS IAM to consolidate access across tools and environments.
- `STL-VM-001` Operated vulnerability management using Tenable for internal scanning, Clone Systems as the PCI ASV, and Dependabot for dependency vulnerability discovery.
- `STL-VM-002` Built automation that consolidated findings from multiple vulnerability sources into a normalized dataset for processing and deduplication.
- `STL-VM-003` Automated creation of Jira remediation tickets for newly identified, deduplicated vulnerabilities.
- `STL-VM-004` Built dashboards showing open findings, SLA status, overdue remediation, and warnings for vulnerabilities approaching SLA deadlines.
- `STL-VM-005` Shifted routine security patching from DevOps to Security to accelerate remediation; escalated OS upgrades and complex fixes to DevOps.
- `STL-IR-001` Served as Incident Commander and owned the company incident-response program.
- `STL-IR-002` Maintained incident-response runbooks and used Nagios for monitoring and Slack for incident communications.
- `STL-IR-003` Conducted semiannual incident-response and digital-forensics training with engineering teams, including simulated breach investigations. — *Semiannual IR/DFIR training*
- `STL-IR-004` Led two security-incident investigations during tenure; both were ultimately determined to be benign. — *2 investigations* [generalize]
- `STL-BCDR-001` Led annual business-continuity/disaster-recovery exercises. — *Annual BCDR exercises*
- `STL-K8S-001` Hardened Kubernetes with service-to-service mTLS and network policies restricting communication to required workloads/services.
- `STL-K8S-002` Standardized secrets management using AWS Secrets Manager for application secrets and keys.
- `STL-K8S-003` Strengthened container supply-chain governance by controlling how images were built, inventoried, approved, and scanned.
- `STL-K8S-004` Expanded Kubernetes runtime logging and began implementation of workload identity before leaving the company.
- `STL-CICD-002` Implemented pre-merge SAST and SCA security gates; failed security checks prevented merges.
- `STL-CICD-003` Introduced Snyk container-image scanning, including layer-level vulnerability analysis.
- `STL-CICD-004` Used Palo Alto Networks Twistlock for Kubernetes/container runtime monitoring and malicious/abnormal activity detection.
- `STL-CICD-005` Used TruffleHog and GitRob to identify secrets and API credentials committed to source repositories.
- `STL-NET-001` Used Fortinet FortiGate firewalls as an egress-control/proxy layer and AWS-native WAF controls.



### Octarine Security — Technical Advisor
Evidence items: **0**


### Evernote — Senior Security Architect
Evidence items: **29**

- `EVR-SCOPE-001` Served as the security architect responsible for domains outside the dedicated application-security function, including cloud, infrastructure, corporate, network, and data security.
- `EVR-SCOPE-002` Reported to the Director of Security and had authority to require infrastructure/operations changes necessary to protect the Evernote environment.
- `EVR-IAM-001` Identified approximately 30 engineers with GCP Owner-level access to the production cloud environment. — *~30 GCP Owners* [generalize]
- `EVR-IAM-002` Replaced broad GCP primitive roles with custom least-privilege roles based on actual team operational requirements.
- `EVR-IAM-003` Separated infrastructure-management permissions from permissions to read customer data, reinforcing privacy controls for privileged operations staff.
- `EVR-IAM-004` Designed IAM so attempts to elevate access to customer data would generate auditable changes and alerts.
- `EVR-IAM-005` Integrated AWS access with Google identities to centralize authentication and simplify joiner/mover/leaver access lifecycle management.
- `EVR-IAM-006` Enabled manager-driven group membership so employees inherited appropriate access based on organizational role rather than individually assigned privileges.
- `EVR-IAM-007` Reduced IAM configuration errors through centralized identity and group-based access administration. — *Resume source states ~40% reduction in IAM misconfigurations*
- `EVR-K8S-001` Created a Kubernetes Security Maturity roadmap after identifying unmanaged cluster ownership and widespread access to manually encrypted application secrets.
- `EVR-K8S-002` Drove adoption of Istio service mesh, including network policies, mTLS, sidecar traffic proxying/logging, and granular Kubernetes RBAC.
- `EVR-K8S-003` Migrated Kubernetes operational ownership from decentralized engineering teams to Operations to establish stronger governance and support controls.
- `EVR-K8S-004` Deployed Twistlock for Kubernetes/container security monitoring.
- `EVR-SECRET-001` Integrated HashiCorp Vault with Kubernetes to support direct secrets injection into containers and reduce developer access to secret material.
- `EVR-DATA-001` Created a data catalog documenting data locations, classifications, flows, and associated security controls after migration to GCP.
- `EVR-DATA-002` Mapped controls to data classifications to identify gaps in protection of sensitive customer information.
- `EVR-THREAT-001` Supported response to a multi-year credential/account compromise campaign targeting users believed to store cryptocurrency wallet information in Evernote accounts. [generalize]
- `EVR-DETECT-001` Used historical attack telemetry to identify behavioral indicators associated with coordinated account-compromise and data-extraction activity.
- `EVR-DETECT-002` Built SIEM detections for abnormal patterns such as coordinated account searches and search-infrastructure traffic spikes.
- `EVR-SIEM-001` Used GCP BigQuery as the primary SIEM/data-analysis platform, with Logstash forwarding security and infrastructure logs into BigQuery.
- `EVR-ATO-001` Evaluated Shape as an additional anti-automation/account-protection control; removed it after it proved ineffective against the ongoing attack pattern. [internal_only]
- `EVR-TPRM-001` Performed security reviews for prospective third-party vendors in partnership with Legal.
- `EVR-CUST-001` Completed security questionnaires from enterprise customers evaluating Evernote’s security posture.
- `EVR-LEGAL-001` Reviewed and redlined security-related provisions in MSAs and commercial contracts in partnership with Legal.
- `EVR-AWARE-001` Designed and produced a company-wide security-awareness program when the organization declined to purchase a commercial training platform.
- `EVR-AWARE-002` Personally created and recorded training covering phishing, password security, attacker techniques, compliance, secure coding, engineering security, and general best practices.
- `EVR-IR-001` Served in the on-call Security Incident Manager rotation and coordinated triage, investigation, stakeholders, containment, and final reporting.
- `EVR-IR-002` Had authority to shut down individual services during security incidents when necessary, short of causing a complete service outage.
- `EVR-IR-003` Produced post-incident recommendations for management and leadership aimed at preventing recurrence.

### eBay Inc — Sr. DevOps Engineer / Crypto Infrastructure Specialist
Evidence items: **21**

- `EBY-ROLE-001` Joined eBay primarily for DevOps/platform-engineering responsibilities and later took on cross-functional cryptography leadership responsibilities.
- `EBY-CRYPTO-001` Was recruited into eBay’s cross-functional Crypto Vigilantes group and subsequently asked by the enterprise cryptography architect to lead the group. [generalize]
- `EBY-CRYPTO-002` Architected and operated a HashiCorp Vault cluster backed by an HSM.
- `EBY-CRYPTO-003` Designed the Vault/HSM platform to support external international partners handling sensitive information required for e-commerce operations. [generalize]
- `EBY-CRYPTO-004` Cryptographic infrastructure supported approximately $5–10 million in annual revenue. — *$5–10M annual revenue supported*
- `EBY-GOV-001` Worked across organizations to identify cryptography-related infrastructure and bring teams toward a standardized enterprise cryptographic platform.
- `EBY-GOV-002` Led meetings, set agendas, defined strategic priorities, and coordinated execution for the cross-functional cryptography working group.
- `EBY-GOV-003` Expanded the cryptography working group’s senior advisory council to align initiatives with longer-term company strategy.
- `EBY-SECCHAMP-001` Served as a Security Champion, partnering with development teams to provide secure-development guidance and escalate deviations from security policies/best practices.
- `EBY-PRIV-001` Served as a Privacy Champion, partnering with teams on data-privacy practices in a role analogous to the Security Champion function but focused on privacy.
- `EBY-AUTO-001` Introduced SaltStack to automate management of approximately 800 servers used by eBay’s security organization. — *~800 servers*
- `EBY-AUTO-002` Reduced new-server provisioning from hours/days to approximately 20–30 minutes using repeatable configuration automation. — *~20–30 minute provisioning*
- `EBY-DR-001` Reduced HashiCorp Vault recovery time from roughly 8–10 hours to approximately 1 hour after infrastructure automation. — *~8–10 hours → ~1 hour*
- `EBY-SCALE-001` Demonstrated SaltStack scalability to a Marketplace organization managing approximately 1,500 servers after that team encountered Puppet scaling limitations. — *~1,500 servers*
- `EBY-SCALE-002` Helped drive broader SaltStack adoption across eBay Marketplace, eBay Classifieds, and StubHub, contributing to standardization on a common infrastructure-management platform. [generalize]
- `EBY-POL-001` Served as a policy/standards SME for cryptography, key management, hashing/encryption, public cloud security, internal PKI infrastructure, and system lifecycle management.
- `EBY-KEY-001` Co-authored eBay’s encryption key lifecycle policy with the enterprise cryptography architect.
- `EBY-PKI-001` Designed and implemented automated PKI capabilities using HashiCorp Vault backed by HSM infrastructure.
- `EBY-PKI-002` Configured certificate issuance and revocation in Vault, validated service functionality, and supported the first production adopter.
- `EBY-WAZUH-001` Upgraded OSSEC to the Wazuh branch and built SaltStack playbooks to deploy/configure Wazuh consistently across servers.
- `EBY-WAZUH-002` Defined Wazuh file-integrity monitoring and configuration-drift rules for managed servers.

### Apixio Inc — Manager of DevOps
Evidence items: **27**

- `APX-SCOPE-001` Served as the sole DevOps engineer despite the Manager of DevOps title and owned Apixio’s production infrastructure.
- `APX-SCOPE-002` Also owned security responsibilities for production and partnered with the Chief Compliance Officer on audit/control requirements.
- `APX-COMP-001` Supported control implementation for SOC 2, PCI DSS, HIPAA, and HITRUST.
- `APX-DEPLOY-001` Replaced a fully manual, server-by-server WAR deployment process with automated Ansible-based deployment playbooks.
- `APX-DEPLOY-002` Integrated Jenkins and Artifactory so successful builds were automatically published for centralized deployment.
- `APX-DEPLOY-003` Reduced deployment windows from approximately 60 minutes to about 5 minutes while supporting roughly 2–3 production deployments per week. — *~60 min → ~5 min; 2–3 deployments/week*
- `APX-CONFIG-001` Introduced Consul as centralized configuration management to prevent environment-specific configuration drift.
- `APX-SECRET-001` Introduced HashiCorp Vault for centralized secrets and API-key management.
- `APX-PHI-001` Protected a healthcare-data environment containing complete medical histories for hundreds of millions of individuals. — *Hundreds of millions of health histories* [generalize]
- `APX-PHI-002` Implemented application-level encryption in addition to cloud-provider default encryption for sensitive health data.
- `APX-NET-001` Implemented network segmentation and built tooling to manage AWS firewall/Security Group rules controlling service-to-service communication.
- `APX-LOG-001` Ensured security- and access-relevant events were logged to enable detection of anomalous authentication and activity patterns.
- `APX-ARCH-001` Evaluated container/orchestration platforms and selected Mesosphere with Marathon and Chronos.
- `APX-ARCH-002` Designed a container platform using Mesosphere, Marathon, Chronos, Consul, Vault, Terraform, and Ansible.
- `APX-ARCH-003` Used containers and infrastructure-as-code to reduce dependence on heavy EC2 recreation and improve deployment/recovery agility.
- `APX-SCALE-001` Designed the platform to handle capacity changes that previously required scaling by hundreds of EC2 instances. — *Scaling by hundreds of EC2 instances*
- `APX-COST-001` Planned container lifecycle policies so workloads could be torn down when no longer required, reducing unnecessary cloud operating cost.
- `APX-PCI-001` Researched and selected an external PCI scanning provider; initial scan identified 17 issues. — *17 initial PCI scan findings*
- `APX-PCI-002` Personally remediated all 17 PCI scan findings, coordinated a rescan, and achieved a clean result supporting PCI certification/audit outcome. — *17/17 remediated; clean rescan*
- `APX-PCI-003` Apixio did not process payment data; the business reason for pursuing PCI certification was not established in the interview. [internal_only]
- `APX-GATE-001` Created “Gatekeeper,” a Python/SaltStack AWS Security Group governance tool using a canonical allowlist of approved rules.
- `APX-GATE-002` Gatekeeper audited Security Groups on a recurring basis, removed unauthorized rules, restored approved configuration, and reported rule changes.
- `APX-SSH-001` Built a self-service web application for temporary production SSH access using single-use SSH key pairs.
- `APX-SSH-002` Automated creation of temporary Unix accounts, home directories, public-key installation, SSH service activation, and Security Group access using SaltStack.
- `APX-SSH-003` Closed inbound SSH access after the user connected, then removed temporary account/key/home-directory access after disconnect while preserving command history centrally.
- `APX-VM-001` Used Nessus for external and internal authenticated vulnerability scanning and personally reviewed/remediated infrastructure findings.
- `APX-VM-002` Vulnerability remediation was operationally managed rather than governed by a formal SLA framework at that stage. [internal_only]

### Hortonworks Inc — IT Operations Manager
Evidence items: **13**

- `HTW-ORG-001` Joined two weeks after the Director of IT as one of the founding members of the IT organization and helped build Technical Operations and Security Operations from scratch.
- `HTW-ORG-002` Directly managed four team members within an IT organization that also included three additional support staff. — *4 direct reports; 7 total IT staff*
- `HTW-DC-001` Helped build a new office’s IT infrastructure and personally installed/configured approximately 140 rack servers in the data center. — *~140 rack servers*
- `HTW-OPS-001` Shared responsibility for operating data centers, corporate infrastructure, physical security, cybersecurity, and facilities.
- `HTW-LEAD-001` Had substantial influence over IT/security strategy, architecture, operational decisions, and budget, frequently acting as the Director of IT’s trusted hands-on technical decision-maker.
- `HTW-SEC-001` Functioned as the de facto security organization because Hortonworks had no separate security team.
- `HTW-CLOUD-001` Helped select OpenStack as the internal private-cloud platform and defined architecture, configuration, security-control, and monitoring requirements.
- `HTW-CLOUD-002` Operated an OpenStack cluster of approximately 60 physical nodes used for Hadoop development/performance testing in cloud-style environments. — *~60 physical nodes*
- `HTW-CLOUD-003` Expanded the private cloud to support customer POCs/demos with VPN access and tenant-isolation controls preventing cross-customer data exposure.
- `HTW-CHANGE-001` Designed and launched Hortonworks’ formal change-control process and selected/established the Change/Release Advisory committee.
- `HTW-CHANGE-002` Required changes to undergo triage, security-impact review, implementation instructions, rollback plans, and committee approval before execution.
- `HTW-CHANGE-003` Established recurring deployment windows, coordinated status communications, and instituted postmortems following failed changes or rollbacks.
- `HTW-CHANGE-004` Held approval authority through the change-governance process to approve, deny, or defer infrastructure and operational changes.

### Appcelerator Inc — Lead Software / DevOps Engineer
Evidence items: **10**

- `APC-LEAD-001` Managed a five-person web-properties engineering team as direct reports. — *5 direct reports*
- `APC-LEAD-002` Provided technical leadership to a three-person DevOps function, including yourself and two additional engineers. — *3-person DevOps function*
- `APC-ARCH-001` Re-architected Appcelerator’s corporate website from CodeIgniter to Zend Framework.
- `APC-ARCH-002` Used framework-provided logging/authentication/authorization and other scaffolding to reduce application codebase size by approximately 40%. — *~40% fewer lines of code*
- `APC-PERF-001` Improved website performance by approximately 30% after the Zend Framework rearchitecture. — *~30% faster*
- `APC-SDLC-001` Introduced a Git-based source-control workflow using branches, pull requests, code review, and conflict-resolution discipline.
- `APC-TEST-001` Introduced automated unit testing and required tests to cover both success and failure/error conditions.
- `APC-CI-001` Configured Jenkins builds to fail when unit-test coverage fell below 85%. — *85% minimum unit-test coverage*
- `APC-CI-003` Designed a distributed Jenkins architecture with a centralized controller coordinating OS-specific worker/build nodes for multi-platform builds.
- `APC-CI-004` Centralized multi-platform build orchestration to avoid unmanaged, ad hoc builds across different operating systems.

### Taos Mountain / Machine Zone — Technical Consultant
Evidence items: **2**

- `TAO-REDIS-001` Served as a Redis SME supporting load testing, capacity planning, and Redis architecture for Machine Zone.
- `TAO-REDIS-002` Used tcpdump and a Python wrapper around tcpkali to replay captured Redis traffic and shape playback for testing.

### Ricoh Innovations Inc — Director of Engineering – Web Services & Partner Development
Evidence items: **14**

- `RIC-LEAD-001` Joined as the first software engineer for the web-services effort and helped grow the organization from one person to roughly 15 engineers before promotion to Director. — *1 → ~15 before Director promotion*
- `RIC-LEAD-002` As Director, led an organization of approximately 20 people across three engineering teams. — *~20 people / 3 teams*
- `RIC-LEAD-003` Led a five-person contractor UI team, an SDK team with a manager and four engineers, and an API team with a manager and nine engineers.
- `RIC-LEAD-004` Promoted two senior engineers into engineering-manager positions as the organization scaled. — *2 internal manager promotions*
- `RIC-PROD-001` Led engineering for a stylus-enabled electronic writing device designed to digitize paper-based workflows, with healthcare as a primary target market.
- `RIC-PROD-002` Platform incorporated OCR, ICR, signature-validation, device/backend integration, and cloud document storage.
- `RIC-INTEG-001` Designed document-integrity capabilities capable of producing certification that a document had not been altered during its lifecycle.
- `RIC-CLOUD-001` Built the backend platform on AWS/EC2 using PHP, Zend Framework, MySQL, and a distributed microservice-oriented architecture.
- `RIC-ARCH-001` Designed services so individual platform components could scale independently, controlling cost by scaling only constrained functions.
- `RIC-SYNC-001` Used Git-based synchronization between devices and backend services to leverage established conflict-resolution semantics rather than building a proprietary synchronization engine.
- `RIC-MQ-001` Implemented clustered ActiveMQ to improve messaging availability/resiliency and exponential backoff to prevent recovery-time retry storms.
- `RIC-PERF-001` Conducted load/performance testing to identify bottlenecks and validate workflow latency; defined stress, load, and failover testing processes.
- `RIC-SCALE-001` Platform launch planning included approximately 20,000 hardware devices; pre-launch/test traffic reached roughly 150 transactions per minute. — *~20,000 planned devices; ~150 transactions/min test traffic*
- `RIC-LIFE-001` Left Ricoh before the product’s public launch, so post-launch production metrics should not be attributed to this tenure. [internal_only]

- `RIC-COMP-001` Designed the healthcare-focused e-writer platform and AWS backend while working toward HIPAA and HITRUST requirements because the intended workflows included medical information.

### CBS Interactive / TV.com — Senior Software Engineer
Evidence items: **8**

- `CBS-SCALE-001` Worked on TV.com while the platform had approximately 150 million active users. — *~150M active users*
- `CBS-SCALE-002` Supported a data environment containing several terabytes of information, including nationwide television-listing data and a large video library. — *Several TB of data*
- `CBS-WATCH-001` Worked in an environment where the Watch List was a major feature, with typical users tracking approximately 60–75 shows. — *~60–75 shows/watch list* [generalize]
- `CBS-VIDEO-001` Helped build a unified video-ingestion architecture that replaced a substantially manual partner-video onboarding process.
- `CBS-VIDEO-002` Enabled partners to submit content into a centralized intake process for normalization, metadata processing, downstream updates, and publication with substantially less manual effort.
- `CBS-LEAD-001` Served as the most senior engineer on the team and provided informal technical leadership and architectural input on major projects without direct reports.
- `CBS-DB-001` Implemented slow-query logging to identify expensive MySQL queries against multi-terabyte datasets.
- `CBS-DB-002` Analyzed query patterns and underlying datasets, tuned indexes, and decomposed oversized datasets into multiple tables to improve lookup performance.

### Zend Technologies — Senior Software Architect / Technical Consultant
Evidence items: **9**

- `ZND-CONS-001` Delivered four major consulting engagements during a six-month tenure with Zend Technologies. — *4 major engagements / ~6 months*
- `ZND-TRAIN-001` Traveled onsite to train customer developers in Zend Framework usage, unit testing, and application security.
- `ZND-DEV-001` Performed hands-on development for a social-media company, including design and implementation of a search capability.
- `ZND-ARCH-001` Helped design and build customer PHP application infrastructure using Zend Framework.
- `ZND-CI-001` Consulted with customers on continuous integration and unit-testing best practices.
- `ZND-AUDIT-001` Performed architecture and security assessments using architecture diagrams, source-code review, configuration review, and database review.
- `ZND-AUDIT-002` Evaluated gaps between current customer architecture/security posture and desired scale/security/operational goals, then produced recommendations.
- `ZND-PRESALES-001` Participated in pre-sales calls to explain consulting capabilities, answer technical questions, and help customers assess whether the team had the expertise needed for engagements.
- `ZND-EDU-001` Conducted technical webinars on application security, continuous integration, and unit testing.

### Pickspal Inc — Director of Technology
Evidence items: **8**

- `PKP-LEAD-001` Served as Director of Technology for a nine-person technology organization with eight direct reports. — *9-person org; 8 direct reports*
- `PKP-PROD-001` Led technology for Facebook-based social sports games covering football, basketball, soccer, hockey, and special events such as the NCAA Final Four, using non-real-money wagering/prediction mechanics.
- `PKP-INFRA-001` Operated approximately 20 physical servers colocated in a data center. — *~20 physical servers*
- `PKP-DB-001` Designed and operated three MySQL database clusters using master-master replication for high availability and workload distribution. — *3 MySQL HA clusters*
- `PKP-WEB-001` Designed a horizontally scalable web cluster for event-driven traffic spikes.
- `PKP-SCALE-001` Architected the platform for anticipated NCAA Final Four traffic of approximately 10,000 visits per minute. — *~10,000 visits/minute expected*
- `PKP-ARCH-001` Architected Pickspal’s technology platform from the ground up and remained highly hands-on as Director.
- `PKP-DEV-001` Continued writing a substantial portion of production code while leading the technology organization.

### VMware Inc — Senior Web Developer
Evidence items: **8**

- `VMW-ROLE-001` Served as an individual contributor on VMware’s web development team while acting as lead engineer for the Virtual Appliance Marketplace and lead developer for the VMware Technical Network.
- `VMW-SSO-001` Integrated the Virtual Appliance Marketplace with VMware’s standardized SOAP-based SSO ecosystem using Java calls to the authentication service.
- `VMW-SSO-002` Enabled users to move across VMware web properties without repeated authentication.
- `VMW-DEPLOY-001` Built a publishing workflow that exported CMS content, combined it with CVS-managed assets, and prepared versioned production releases.
- `VMW-DEPLOY-002` Replaced rsync-centric publishing with a versioned directory/symlink deployment model enabling near-instantaneous rollback by switching symlink targets.
- `VMW-MKT-001` Helped build the VMware Virtual Appliance Marketplace, allowing vendors to publish preconfigured virtual machines for customers to purchase and run on VMware platforms.
- `VMW-MKT-002` Supported a platform that created an additional commercial/revenue channel for VMware and participating software vendors. [generalize]
- `VMW-IDENT-001` Worked with LDAP and ACL-related functionality for internal user/access-management applications.

### Symantec Corp – Falcon Project — Web Developer
Evidence items: **4**

- `SYM-PROD-001` Worked on Symantec’s Falcon initiative, which moved Norton Antivirus software activation from locally validated CD keys to an online activation model.
- `SYM-PROD-002` The online activation workflow enabled validation of software entitlements and reduced reuse/piracy of previously activated distributions. [generalize]
- `SYM-ROLE-001` Served purely as an individual-contributor web developer on a short-term contract.
- `SYM-WEB-001` Contributed JSP, JavaScript, CSS, XML, AJAX, and web-content development to the Falcon/customer-experience project.

### Wiscasset Web Development — Lead Developer
Evidence items: **8**

- `WIS-ROLE-001` Served as Lead Developer for Wiscasset Web Development; was not the business owner.
- `WIS-BIZ-001` Worked for a small web-development business that grew out of an internet café and primarily served local businesses, especially automobile dealerships.
- `WIS-TECH-001` Developed web applications primarily using PHP and Perl, with MySQL and flat-file data storage.
- `WIS-INFRA-001` Hosted customer applications on rented colocated infrastructure from Rackspace.
- `WIS-TEAM-001` Worked with one additional employee plus contractors brought in as project demand required; led project teams of up to approximately six developers. — *Teams up to ~6 developers*
- `WIS-LEAD-001` Assigned workloads and reviewed developer output for quality prior to customer delivery.
- `WIS-CLIENT-001` Worked directly with customers to understand business and technical requirements and supported estimation, documentation, milestone delivery, and developer training.
- `WIS-PROJ-001` Primarily delivered smaller, non-ecommerce business websites rather than large-scale transactional applications. [internal_only]
