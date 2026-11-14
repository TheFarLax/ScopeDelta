"""Verify ScopeDelta on Studionet and optionally run the live AI workflow."""

import argparse
import json

from genlayer_py import create_account
from genlayer_py.abi import calldata
from genlayer_py.types import TransactionHashVariant, TransactionStatus

from deploy_studionet import ROOT, rpc, studio_client, verify_deployment

ADDRESS = "0x45a63Aa2E7F34C3767D2FaecD99AA62b379AE37C"
DEPLOY_TX = "0x52829fc542d097b1eaff4a8d7d40a5218618a0cd1f17ccb6fdce1dd09215efb8"
CASES = (
    ("Set the body font size to 18px.", "WITHIN_SCOPE", "INCLUDED_WORK"),
    ("Add user registration and login.", "CHANGE_ORDER_REQUIRED", "EXCLUDED_OR_ADDITIONAL_WORK"),
    ("Make it better.", "AMBIGUOUS", "INSUFFICIENT_OR_CONFLICTING_TERMS"),
)
TERMS = (
    "Studionet test fixture. Deliver a landing page and contact form. "
    "User accounts, registration and login are explicitly excluded. "
    "Changes to the landing page's typography are included."
)


def read_finalized(client, method, *args):
    return client.read_contract(
        address=ADDRESS, function_name=method, args=list(args),
        transaction_hash_variant=TransactionHashVariant.LATEST_FINAL,
    )


def write_finalized(client, report, account, method, *args):
    tx = client.write_contract(
        address=ADDRESS, function_name=method, args=list(args), account=account,
        leader_only=False,
    )
    entry = {"method": method, "tx_hash": tx}
    report["transactions"].append(entry)
    print(f"Submitted {method} {tx}", flush=True)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx, status=TransactionStatus.FINALIZED,
        retries=100, full_transaction=True,
    )
    entry.update(status=receipt["status_name"], consensus=receipt["result_name"])
    leaders = receipt["consensus_data"]["leader_receipt"]
    leader = leaders[-1] if isinstance(leaders, list) else leaders
    execution = leader["execution_result"]
    entry["execution_result"] = execution
    genvm_result = leader.get("genvm_result") or {}
    if genvm_result.get("error_code"):
        entry["error_code"] = genvm_result["error_code"]
    if (
        entry["status"] != "FINALIZED"
        or entry["consensus"] != "MAJORITY_AGREE"
        or execution != "SUCCESS"
        or leader["result"]["status"] != "return"
    ):
        raise RuntimeError(f"{method} failed: {entry}")
    print(f"Finalized {method} {tx}", flush=True)
    return calldata.decode(bytes(leader["result"]["payload"]["raw"]))


def run_live_workflow(client, report):
    creator = client.local_account
    counterparty = create_account()
    for account in (creator, counterparty):
        address = account.address
        rpc(client, "sim_fundAccount", [address, 10**20])
        if client.w3.eth.get_balance(address) == 0:
            raise RuntimeError("Studionet test wallet has no balance after faucet")

    scope_id = write_finalized(client, report, creator, "create_scope", counterparty.address, TERMS)
    report["scope_id"] = scope_id
    scope = read_finalized(client, "get_scope", scope_id)
    if scope["accepted"] or scope["terms"] != TERMS or scope["counterparty"] != counterparty.address.lower():
        raise RuntimeError("Created scope does not match the fixture")
    write_finalized(client, report, counterparty, "accept_scope", scope_id)
    if read_finalized(client, "get_scope", scope_id)["accepted"] is not True:
        raise RuntimeError("Counterparty acceptance is missing from finalized state")

    for request, decision, reason_code in CASES:
        change_id = write_finalized(client, report, creator, "submit_change", scope_id, request)
        change = read_finalized(client, "get_change", change_id)
        if change["scope_id"] != scope_id or change["request"] != request or change["status"] != "PENDING":
            raise RuntimeError(f"Unexpected pending state for change {change_id}")
        verdict = write_finalized(client, report, counterparty, "evaluate_change", change_id)
        saved = read_finalized(client, "get_change", change_id)
        expected = {"decision": decision, "reason_code": reason_code}
        case = {
            "change_id": change_id,
            "request": request,
            "evaluation_tx": report["transactions"][-1]["tx_hash"],
            "expected": expected,
            "returned": verdict,
            "saved": {key: saved[key] for key in expected},
            "status": saved["status"],
        }
        report["verdicts"].append(case)
        if verdict != expected or case["saved"] != expected or saved["status"] != "EVALUATED":
            raise RuntimeError(f"Unexpected verdict for change {change_id}: {case}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Create public test records and evaluate all three verdicts on Studionet",
    )
    args = parser.parse_args()
    client = studio_client()
    receipt = client.get_transaction(DEPLOY_TX)
    if receipt["data"]["contract_address"].lower() != ADDRESS.lower():
        raise RuntimeError("Deployment receipt address does not match ScopeDelta")
    report = verify_deployment(client, receipt, DEPLOY_TX)
    if args.live:
        report["finalized_get_counts_before_run"] = report.pop("finalized_get_counts")
        report["live_ai"] = {"status": "IN_PROGRESS", "transactions": [], "verdicts": []}
        try:
            run_live_workflow(client, report["live_ai"])
        except Exception as exc:
            report["live_ai"].update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
            write_report(report, "test_report.json")
            raise
        report["live_ai"]["status"] = "PASSED"
        write_report(report, "test_report.json")
    else:
        report["verification"] = "Read-only Studionet checks"
        print(json.dumps(report, indent=2))


def write_report(report, filename):
    output = json.dumps(report, indent=2) + "\n"
    (ROOT / filename).write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
