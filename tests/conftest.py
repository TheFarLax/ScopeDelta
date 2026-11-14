from pathlib import Path
from unittest.mock import patch

import pytest
from genvm_linter.validate.artifacts import download_artifacts
from gltest.direct import VMContext, deploy_contract, sdk_loader

SOURCE = Path(__file__).resolve().parents[1] / "contracts" / "scope_delta.py"
RUNNER_RELEASE = "v0.3.0-rc7"
CREATOR = "0x" + "11" * 20
COUNTERPARTY = "0x" + "22" * 20
TERMS = "Landing page and contact form. No user accounts. One typography revision included."


@pytest.fixture(scope="session")
def initial_scope():
    # The linter resolves the current runner asset name for the pinned SDK.
    vm = VMContext()
    vm.sender = CREATOR
    with patch.object(sdk_loader, "download_artifacts", download_artifacts):
        contract = deploy_contract(SOURCE, vm, sdk_version=RUNNER_RELEASE)
    scope_id = contract.create_scope(COUNTERPARTY, TERMS)
    return vm, contract, scope_id, vm.snapshot()


@pytest.fixture
def scope(initial_scope):
    vm, contract, scope_id, baseline = initial_scope
    vm.revert(baseline)
    return vm, contract, scope_id


@pytest.fixture
def accepted_scope(scope):
    vm, contract, scope_id = scope
    with vm.prank(COUNTERPARTY):
        contract.accept_scope(scope_id)
    return vm, contract, scope_id


@pytest.fixture
def mock_model():
    from genlayer.gl import nondet

    def respond(payload):
        return patch.object(nondet, "exec_prompt", return_value=payload)

    return respond
