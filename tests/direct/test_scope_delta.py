import pytest

THIRD_PARTY = "0x" + "33" * 20
WITHIN = {"decision": "WITHIN_SCOPE", "reason_code": "INCLUDED_WORK"}
EXTRA = {"decision": "CHANGE_ORDER_REQUIRED", "reason_code": "EXCLUDED_OR_ADDITIONAL_WORK"}
AMBIGUOUS = {"decision": "AMBIGUOUS", "reason_code": "INSUFFICIENT_OR_CONFLICTING_TERMS"}


def test_scope_must_be_accepted(scope):
    vm, contract, scope_id = scope
    assert contract.get_scope(scope_id)["accepted"] is False
    with vm.expect_revert("Both parties must accept"):
        contract.submit_change(scope_id, "Add a login page")
    assert contract.get_counts() == {"scopes": 1, "changes": 0}


def test_only_named_counterparty_can_accept(scope):
    vm, contract, scope_id = scope
    with vm.prank(THIRD_PARTY), vm.expect_revert("Only the named counterparty"):
        contract.accept_scope(scope_id)
    assert contract.get_scope(scope_id)["accepted"] is False


def test_outsider_cannot_submit_or_evaluate(accepted_scope):
    vm, contract, scope_id = accepted_scope
    change_id = contract.submit_change(scope_id, "Add a login page")
    with vm.prank(THIRD_PARTY):
        with vm.expect_revert("Only a scope party"):
            contract.submit_change(scope_id, "Change the font size")
        with vm.expect_revert("Only a scope party"):
            contract.evaluate_change(change_id)
    assert contract.get_change(change_id)["status"] == "PENDING"


@pytest.mark.parametrize(
    ("change_request", "expected"),
    [("Increase the font size", WITHIN), ("Add Google login", EXTRA), ("Make it better", AMBIGUOUS)],
)
def test_evaluation_records_each_verdict(accepted_scope, mock_model, change_request, expected):
    vm, contract, scope_id = accepted_scope
    change_id = contract.submit_change(scope_id, change_request)
    with mock_model(expected) as model:
        assert contract.evaluate_change(change_id) == expected
        calls_before_validation = model.call_count
        assert vm.run_validator()
        assert model.call_count == calls_before_validation + 1
    saved = contract.get_change(change_id)
    assert saved["status"] == "EVALUATED"
    assert saved["decision"] == expected["decision"]
    assert saved["reason_code"] == expected["reason_code"]


def test_validator_rejects_disagreement(accepted_scope, mock_model):
    vm, contract, scope_id = accepted_scope
    change_id = contract.submit_change(scope_id, "Add Google login")
    with mock_model(EXTRA):
        contract.evaluate_change(change_id)
    with mock_model(AMBIGUOUS):
        assert not vm.run_validator()


def test_malformed_model_result_keeps_change_pending(accepted_scope, mock_model):
    vm, contract, scope_id = accepted_scope
    change_id = contract.submit_change(scope_id, "Add Google login")
    with mock_model({"decision": "YES", "reason_code": "yes"}), vm.expect_revert("Invalid decision or reason code"):
        contract.evaluate_change(change_id)
    assert contract.get_change(change_id)["status"] == "PENDING"


def test_a_second_evaluation_is_rejected(accepted_scope, mock_model):
    vm, contract, scope_id = accepted_scope
    change_id = contract.submit_change(scope_id, "Add Google login")
    with mock_model(EXTRA):
        contract.evaluate_change(change_id)
    with vm.expect_revert("Change already evaluated"):
        contract.evaluate_change(change_id)
    assert contract.get_change(change_id)["decision"] == EXTRA["decision"]
