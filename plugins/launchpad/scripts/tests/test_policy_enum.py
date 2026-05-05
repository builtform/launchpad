"""DA7 lock verification: BootstrapPolicy enum has exactly 4 members.

Phase 4 plan §3.3: 4-policy enum is LOCKED at:
  - overwrite-if-unchanged
  - merge-keys
  - append-only
  - overwrite-with-backup

Adding a 5th policy (e.g. skip-if-exists, overwrite-always) is deferred to
v2.2 BL per §8 out-of-scope. This test fails closed if a 5th member lands
without a plan amendment.
"""
from __future__ import annotations

from lp_bootstrap import BootstrapPolicy


def test_bootstrap_policy_has_exactly_four_members():
    assert len(list(BootstrapPolicy)) == 4


def test_bootstrap_policy_member_values_are_locked():
    values = {member.value for member in BootstrapPolicy}
    assert values == {
        "overwrite-if-unchanged",
        "merge-keys",
        "append-only",
        "overwrite-with-backup",
    }


def test_bootstrap_policy_values_are_kebab_case_strings():
    for member in BootstrapPolicy:
        assert "_" not in member.value, (
            f"policy value {member.value!r} uses underscores; kebab-case required"
        )
        assert member.value.islower(), (
            f"policy value {member.value!r} contains uppercase chars"
        )
