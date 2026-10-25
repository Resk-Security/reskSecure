# Changelog

## [0.1.1] - 2026-10-25

### Fixed
- Bias mode crashed on the first matching phrase: the processor received
  pattern modes (strings) where it expected penalties (floats).
- Per-rule `penalty` values from the YAML are now applied; the previous code
  discarded them and hard-coded -5.0.
- Tool trigger rules are collected without rebuilding them as fresh rules,
  keeping the policy definition intact.

### Tests
- Added regression tests for default and custom bias penalties.
