# ScopeDelta

ScopeDelta is a GenLayer Intelligent Contract that checks a change request against terms accepted by two parties. Validators independently evaluate the same scope and request. The contract records one verdict with its reason code.

| Verdict | Meaning |
|---|---|
| `WITHIN_SCOPE` | The accepted terms cover the requested work. |
| `CHANGE_ORDER_REQUIRED` | The request clearly adds work or is covered by an exclusion. |
| `AMBIGUOUS` | The terms or request lack enough detail for a decision. |

## Contract

`contracts/scope_delta.py` is the deployable file. In [GenLayer Studio](https://studio.genlayer.com/), it takes no constructor arguments.

1. Call `create_scope(counterparty, terms)` and record the returned scope ID.
2. From the counterparty account, call `accept_scope(scope_id)`.
3. Either party calls `submit_change(scope_id, request)` and records the change ID.
4. Either party calls `evaluate_change(change_id)`. Use `get_scope`, `get_change` and `get_counts` to inspect records.

## Studionet deployment

| Field | Value |
|---|---|
| Chain ID | `61999` |
| Contract | [`0x45a63Aa2E7F34C3767D2FaecD99AA62b379AE37C`](https://explorer-studio.genlayer.com/address/0x45a63Aa2E7F34C3767D2FaecD99AA62b379AE37C) |
| Deployment transaction | `0x52829fc542d097b1eaff4a8d7d40a5218618a0cd1f17ccb6fdce1dd09215efb8` |
| Status | Finalized, constructor successful |

## Setup and checks

Use Python 3.12 or later.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
genvm-lint check contracts/scope_delta.py
python -m pytest tests/direct/ -q
python test_deployed.py
```

The nine direct tests exercise consent, caller permissions, the three mocked verdicts, validator disagreement, invalid output and duplicate evaluation. The pinned GenVM runner downloads on the first local run.

`python test_deployed.py` checks the finalized deployment receipt, compares the deployed source against the included Python file byte-for-byte, and reads finalized state.

## Live Studionet tests

Two test wallets created and accepted scope `1`. All eight writes finalized with majority agreement and successful execution. The evaluation return values and the verdicts saved in finalized state matched for all three cases.

| Change | Request | Stored verdict |
|---|---|---|
| `1` | Set the body font size to 18px. | `WITHIN_SCOPE` |
| `2` | Add user registration and login. | `CHANGE_ORDER_REQUIRED` |
| `3` | Make it better. | `AMBIGUOUS` |

See [test_report.json](test_report.json) for the receipts, transaction hashes and reason codes. To repeat the workflow, run `python test_deployed.py --live`. This creates a new public test scope and three change records on the existing Studionet instance.

## Deploy another instance

`python deploy_studionet.py` creates a separate instance using an in-memory Studionet test wallet. Pass `--resume <deployment-tx>` to verify a previously submitted deployment.
