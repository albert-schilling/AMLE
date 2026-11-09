# Stranger-Runnable README Checklist

Use this checklist from the perspective of an unfamiliar technical reviewer. A checked item
must be specific, current, and testable.

## Purpose and scope

- [ ] Names the intended user and problem.
- [ ] States the primary workflow and expected outcome.
- [ ] Defines supported and unsupported use.
- [ ] Identifies the release/version the README describes.

## Setup

- [ ] Lists OS/runtime/tool prerequisites and tested versions.
- [ ] Gives exact clone, install, and initialization commands.
- [ ] States the working directory for commands.
- [ ] Covers data/model/bootstrap steps and expected artifacts.
- [ ] Includes a clean reset or uninstall path where relevant.

## Configuration

- [ ] Lists every required environment variable/config key.
- [ ] Explains purpose, format, allowed values, and safe default.
- [ ] Points to the secret source without exposing values.
- [ ] Distinguishes required, optional, local, test, and production settings.
- [ ] Documents external-service access and permissions.

## Run, test, and deploy

- [ ] Gives one exact primary run command.
- [ ] Shows a representative input and expected success signal.
- [ ] Gives exact test and eval commands.
- [ ] Explains where reports appear and how to interpret pass/fail.
- [ ] Gives deploy and post-deploy verification commands, or states why unavailable.
- [ ] Documents recovery, rollback, or local fallback where relevant.

## Architecture

- [ ] Diagram and explanation match the system as built.
- [ ] Names core components, responsibilities, and data/control flow.
- [ ] Marks external dependencies and trust/data boundaries.
- [ ] Explains important agent/tool/human handoffs.
- [ ] Links major architecture and context decisions.

## Evaluation

- [ ] States dataset/suite, version, configuration, and evaluators.
- [ ] Defines metrics, thresholds, and relevant uncertainty.
- [ ] Reports current results with artifact links.
- [ ] Includes representative failures or regressions, not only averages.
- [ ] Separates measured evidence from future goals.

## Safety and limitations

- [ ] Describes preventive, detective, and response controls.
- [ ] Explains refusal, escalation, approval, or rollback behavior.
- [ ] States residual risks and their evidence.
- [ ] Lists known limitations, failure modes, and unavailable paths.
- [ ] Avoids claims broader than the tested scope.

## Stranger verification

- [ ] Verifier started from a clean clone/environment or documented equivalent.
- [ ] Verifier followed only the README.
- [ ] Hidden prerequisites and ambiguous steps were recorded and fixed.
- [ ] Final outcome, environment, commit, and evidence were saved.
- [ ] Any unverified instruction is labeled unverified.

## Final quality gate

- [ ] Links resolve and refer to the release being demonstrated.
- [ ] Commands are copyable and ordered.
- [ ] Secret values, private data, and unsafe examples are absent.
- [ ] Headings let a reviewer find setup, run, test, deploy, architecture, eval, safety, and
  limitations quickly.
- [ ] A stranger can determine both what works and what does not.

> “Clear” is not the bar. The bar is whether a stranger can reproduce or independently
> verify each important release claim.
