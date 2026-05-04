# ADR-002: Synology and AWS layouts mirror 1:1 with deliberate AZ divergence

**Status:** Accepted
**Date:** April 2026
**Stage:** 1 (Conceptual Design)

## Context

pandyaHomeLab is designed to run on Synology NAS (primary) and AWS (mirror, for cloud parity demonstration). An early design version had different shapes on each platform — six Docker networks on Synology versus eleven AWS subnets — based on the reasoning that "AWS subnets are free, so pre-carve them."

This created a structural divergence between the two platforms that would ripple through every downstream artifact: Compose files would not match Terraform modules, CI/CD promotion (Synology → AWS) would require translation rather than diff, and the mental model would have two distinct shapes that the operator would need to keep straight.

## Decision

**Synology and AWS use the same six logical networks with the same names. The only deliberate divergence is multi-AZ on the AWS side, which exists because the platforms have genuinely different failure modes.**

Each logical network exists once on Synology (one Docker network) and twice on AWS (one subnet per Availability Zone, for HA). Subnets follow a `+10` convention in the third octet between AZs — `10.1.3.0/24` (AZ-A) and `10.1.13.0/24` (AZ-B) both implement the logical `ml-network`. The mirror principle holds at the *logical* layer; only the *physical* implementation accounts for AZ.

| Logical network    | Synology CIDR    | AWS AZ-A CIDR  | AWS AZ-B CIDR   |
|--------------------|------------------|-----------------|-----------------|
| proxy-network      | 172.18.0.0/24    | 10.1.0.0/24     | 10.1.10.0/24    |
| data-network       | 172.18.1.0/24    | 10.1.1.0/24     | 10.1.11.0/24    |
| mlops-network      | 172.18.2.0/24    | 10.1.2.0/24     | 10.1.12.0/24    |
| ml-network         | 172.19.0.0/24    | 10.1.3.0/24     | 10.1.13.0/24    |
| dl-network         | 172.20.0.0/24    | 10.1.4.0/24     | 10.1.14.0/24    |
| nlp-network        | 172.21.0.0/24    | 10.1.5.0/24     | 10.1.15.0/24    |
| agentic-network    | 172.22.0.0/24    | 10.1.6.0/24     | 10.1.16.0/24    |

## Alternatives considered

**Different shapes per platform (rejected).** The "subnets are free in AWS" argument is technically true but ignores cognitive cost. Empty subnets in a console are clutter. Translation between platforms creates ongoing maintenance burden — every change must be made twice, in different shapes, with different naming. The operational cost of divergence outweighs the theoretical flexibility.

**Single-AZ AWS deployment (rejected for design, kept as a deployment option).** Single-AZ is simpler and cheaper, but it violates the cloud-architecture-savvy positioning of the platform. The *design* should reflect production readiness even if the *running cost* is initially single-AZ. ADR-002 establishes the design as multi-AZ; deployment can begin in AZ-A only and bring up AZ-B for HA demos.

**Pure Synology (rejected).** Defeats the platform's hybrid cloud demonstration purpose.

## Consequences

**Positive:**

- IaC promotion (Synology Compose → AWS Terraform) becomes a structural diff rather than a translation. Same names, same number of networks, same logical relationships.
- The mental model is singular: one architecture, two implementations. Debugging a production issue does not require translating concepts between platforms.
- Multi-AZ topology is captured in design from day one. When deployed multi-AZ, no architectural rework is needed.
- The `+10 octet per AZ` convention makes subnet IDs self-describing: `10.1.13.0/24` is recognizable at a glance as the AZ-B mirror of `ml-network`.

**Negative:**

- AWS deployment is more expensive when fully multi-AZ (NAT gateways in two AZs, RDS Multi-AZ, cross-AZ data transfer). For a non-commercial lab, deploying both AZs continuously is uneconomical. Mitigation: deploy AZ-A always, bring up AZ-B for demos and tear down.
- The design carries multi-AZ complexity even when the platform is running on Synology only, where AZ has no meaning. This is acceptable because the design is the contract for both platforms.

**Forecloses:**

- Highly platform-specific optimizations on AWS (using AWS-native services that have no Synology equivalent) would require deviating from the mirror. Such deviations are allowed but must be ADR'd individually.
