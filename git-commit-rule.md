# Git Commit Guidelines

## Commit Timing
* Create a commit whenever a feature, bug fix, or refactoring task is completed.
* Commit only after the relevant tests have passed.
* If unrelated changes arise during development, separate them into different commits.

## Commit Scope
* Each commit should have a single purpose (Single Responsibility).
* Changes across multiple files may be grouped into one commit if they serve the same objective.
* The following cases must be split into separate commits:

  * Feature addition and bug fix in the same change set
  * Functional modification and refactoring in the same change set
  * Dependency updates and feature implementation in the same change set

## Commit Context
### Commit Message Format
```
<type>: <subject>

[optional body]

[optional trailer]

```
### Available types:

  * `feat`: new feature
  * `fix`: bug fix
  * `refactor`: code changes without functional changes
  * `docs`: documentation updates
  * `chore`: build or configuration changes
  * `test`: test additions or modifications

* The subject must be written in English and start with an imperative verb (e.g., add, fix, update, remove, refactor).
 - Examples:
   `feat: add user authentication`
   `fix: resolve null pointer in parser`

### Using trailers
When a commit contains significant technical decisions, capture the
relevant rationale using Git trailers.

Trailers are particularly valuable when documenting:
- architecture and design decisions
- non-obvious implementation choices
- evaluated trade-offs
- workarounds and known constraints
- bug fixes that may require future review

Trailers may be omitted for low-impact changes, including:
- typo corrections
- formatting adjustments
- routine documentation updates

Supported trailers:
- Constraint: Technical, business, or architectural limitations that influenced the implementation
- Rejected: Alternative approaches evaluated and the reasons they were not adopted
- Directive: Important guidance, warnings, assumptions, or future considerations for subsequent modifications

Example:
```
fix: avoid NULL deref on early probe failure

Constraint: Hardware may not populate IRQ line during cold boot
Rejected: Returning -ENODEV directly — masks legitimate errors
Directive: Do not remove the null check; required for platform X
```

## Pre-Commit Checklist

* Review changes using `git diff` before committing.
* Ensure no unnecessary debug code or temporary comments are included.
* Verify that unrelated files are not accidentally staged.