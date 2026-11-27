# ADR 0014: Explicit portable packaging and release gates

Status: Accepted for local implementation. Date: 2026-11-26.

## Context

The private working tree contains local agent and planning files.

## Alternatives

Publishing the entire directory or relying only on ignore rules was rejected.

## Decision

Use pyproject/setuptools, one version source, package-data selection, explicit source curation and independent archive inspection.

## Consequences and risks

Wheel, sdist and ZIP are checked for private paths and renamed sensitive content. No runtime dependency on local development tooling.

## Reassessment

Reassess when adding files, metadata, assets, a public repository or a new release format.
