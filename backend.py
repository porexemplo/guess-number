from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS
from solcx import compile_standard, install_solc, set_solc_version
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = BASE_DIR / "contracts"
SOLC_VERSION = "0.8.20"
EVM_VERSION = "paris"

app = Flask(__name__)
CORS(app)


# ---------- helpers ----------

def ok(**kwargs):
    return jsonify({"ok": True, **kwargs})


def fail(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def require_json() -> Dict[str, Any]:
    data = request.get_json(silent=True) or {}
    return data


def w3_from_rpc(rpc_url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Impossible de se connecter a Ganache via {rpc_url}")
    return w3


def account_from_privkey(w3: Web3, privkey: str):
    try:
        return w3.eth.account.from_key(privkey)
    except Exception as exc:
        raise RuntimeError(f"Clé privée invalide: {exc}") from exc


def build_tx(w3: Web3, account, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tx = {
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "gasPrice": w3.eth.gas_price,
    }
    if extra:
        tx.update(extra)
    return tx


def sign_and_send(w3: Web3, tx: Dict[str, Any], privkey: str):
    signed = w3.eth.account.sign_transaction(tx, private_key=privkey)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError("Transaction reverted")
    return receipt


def as_checksum(address: str) -> str:
    return Web3.to_checksum_address(address)


def parse_eth(value: Any) -> int:
    return Web3.to_wei(str(value), "ether")


def wei_to_eth(value: int) -> str:
    return str(Web3.from_wei(value, "ether"))


def result_label(code: int) -> str:
    return {1: "plus petit", 0: "correct", -1: "plus grand", 2: "aucun"}.get(code, f"inconnu({code})")


def _leaf_bytes(guess: int, result_code: int) -> bytes:
    return Web3.solidity_keccak(["uint8", "int8"], [guess, result_code])


def _pair_hash(left: bytes, right: bytes) -> bytes:
    a, b = (left, right) if left <= right else (right, left)
    return Web3.keccak(a + b)


def _result_code_for_secret(secret: int, guess: int) -> int:
    if guess == secret:
        return 0
    return 1 if guess < secret else -1


def build_merkle_package(secret: int) -> Dict[str, Any]:
    if not (1 <= secret <= 100):
        raise RuntimeError("Le secret doit etre entre 1 et 100")

    leaves = [_leaf_bytes(g, _result_code_for_secret(secret, g)) for g in range(1, 101)]
    levels: List[List[bytes]] = [leaves]
    while len(levels[-1]) > 1:
        prev = levels[-1]
        nxt: List[bytes] = []
        for i in range(0, len(prev), 2):
            left = prev[i]
            right = prev[i + 1] if i + 1 < len(prev) else prev[i]
            nxt.append(_pair_hash(left, right))
        levels.append(nxt)

    def proof_for_guess(guess: int) -> List[str]:
        idx = guess - 1
        proof: List[str] = []
        for level in levels[:-1]:
            sibling_idx = idx ^ 1
            sibling = level[sibling_idx] if sibling_idx < len(level) else level[idx]
            proof.append(Web3.to_hex(sibling))
            idx //= 2
        return proof

    proofs = {str(g): proof_for_guess(g) for g in range(1, 101)}
    hints = {str(g): _result_code_for_secret(secret, g) for g in range(1, 101)}
    return {
        "root": Web3.to_hex(levels[-1][0]),
        "hints": hints,
        "proofs": proofs,
    }


# ---------- compilation ----------

@lru_cache(maxsize=1)
def compiled_contracts() -> Dict[str, Dict[str, Any]]:
    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)

    sources = {}
    for path in CONTRACTS_DIR.glob("*.sol"):
        sources[path.name] = {"content": path.read_text(encoding="utf-8")}

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": sources,
            "settings": {
                "optimizer": {"enabled": False, "runs": 200},
                "evmVersion": EVM_VERSION,
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_version=SOLC_VERSION,
    )

    out: Dict[str, Dict[str, Any]] = {}
    for filename, contracts in compiled["contracts"].items():
        for cname, artifact in contracts.items():
            out[cname] = {
                "abi": artifact["abi"],
                "bytecode": artifact["evm"]["bytecode"]["object"],
            }
    return out


def contract_instance(w3: Web3, version: str, address: str):
    name = {
        "v1": "GuessNumberV1",
        "v2": "GuessNumberV2",
        "v3": "GuessNumberV3",
        "v4": "GuessNumberV4",
    }[version]
    artifact = compiled_contracts()[name]
    return w3.eth.contract(address=as_checksum(address), abi=artifact["abi"])


def deploy_contract(w3: Web3, version: str, privkey: str, constructor_args: List[Any], value_wei: int = 0):
    name = {
        "v1": "GuessNumberV1",
        "v2": "GuessNumberV2",
        "v3": "GuessNumberV3",
        "v4": "GuessNumberV4",
    }[version]
    artifact = compiled_contracts()[name]
    account = account_from_privkey(w3, privkey)
    contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = contract.constructor(*constructor_args).build_transaction(
        build_tx(w3, account, {"value": value_wei, "gas": 6_500_000})
    )
    receipt = sign_and_send(w3, tx, privkey)
    return receipt.contractAddress, receipt


# ---------- state serializers ----------

def get_v1_state(c) -> Dict[str, Any]:
    return {
        "playerA": c.functions.playerA().call(),
        "playerB": c.functions.playerB().call(),
        "maxAttempts": c.functions.maxAttempts().call(),
        "attempts": c.functions.attempts().call(),
        "attemptsLeft": c.functions.attemptsLeft().call(),
        "gameOver": c.functions.gameOver().call(),
        "wonByB": c.functions.wonByB().call(),
        "lastGuess": c.functions.lastGuess().call(),
        "lastResultCode": c.functions.lastResultCode().call(),
        "lastResultLabel": result_label(c.functions.lastResultCode().call()),
    }


def get_v2_state(c, w3: Web3) -> Dict[str, Any]:
    return {
        "playerA": c.functions.playerA().call(),
        "playerB": c.functions.playerB().call(),
        "stakeEth": wei_to_eth(c.functions.stake().call()),
        "contractBalanceEth": wei_to_eth(w3.eth.get_balance(c.address)),
        "joined": c.functions.joined().call(),
        "maxAttempts": c.functions.maxAttempts().call(),
        "attempts": c.functions.attempts().call(),
        "attemptsLeft": c.functions.attemptsLeft().call(),
        "gameOver": c.functions.gameOver().call(),
        "wonByB": c.functions.wonByB().call(),
        "lastGuess": c.functions.lastGuess().call(),
        "lastResultCode": c.functions.lastResultCode().call(),
        "lastResultLabel": result_label(c.functions.lastResultCode().call()),
    }


def get_v3_game(c, game_id: int) -> Dict[str, Any]:
    g = c.functions.getGame(game_id).call()
    return {
        "gameId": game_id,
        "playerA": g[0],
        "playerB": g[1],
        "maxAttempts": g[2],
        "attempts": g[3],
        "attemptsLeft": g[2] - g[3],
        "stakeEth": wei_to_eth(g[4]),
        "joined": g[5],
        "gameOver": g[6],
        "wonByB": g[7],
        "lastResultCode": g[8],
        "lastResultLabel": result_label(g[8]),
        "lastGuess": g[9],
    }


def get_v4_state(c, w3: Web3) -> Dict[str, Any]:
    return {
        "playerA": c.functions.playerA().call(),
        "playerB": c.functions.playerB().call(),
        "merkleRoot": c.functions.merkleRoot().call(),
        "stakeEth": wei_to_eth(c.functions.stake().call()),
        "contractBalanceEth": wei_to_eth(w3.eth.get_balance(c.address)),
        "joined": c.functions.joined().call(),
        "maxAttempts": c.functions.maxAttempts().call(),
        "attempts": c.functions.attempts().call(),
        "attemptsLeft": c.functions.attemptsLeft().call(),
        "gameOver": c.functions.gameOver().call(),
        "wonByB": c.functions.wonByB().call(),
        "pendingGuess": c.functions.pendingGuess().call(),
        "hasPendingGuess": c.functions.hasPendingGuess().call(),
        "lastResolvedGuess": c.functions.lastResolvedGuess().call(),
        "lastResultCode": c.functions.lastResultCode().call(),
        "lastResultLabel": result_label(c.functions.lastResultCode().call()),
    }


# ---------- generic routes ----------

@app.get("/health")
def health():
    return ok(service="guess-number-backend", solc=SOLC_VERSION, evm=EVM_VERSION)


@app.post("/account/info")
def account_info():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["private_key"])
        balance = wei_to_eth(w3.eth.get_balance(account.address))
        return ok(address=account.address, balance_eth=balance)
    except Exception as exc:
        return fail(str(exc))


# ---------- v1 ----------

@app.post("/v1/deploy")
def v1_deploy():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        address, receipt = deploy_contract(
            w3,
            "v1",
            data["playerA_private_key"],
            [as_checksum(data["playerB_address"]), int(data["secret_number"]), int(data["max_attempts"])],
        )
        return ok(contract_address=address, tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v1/state")
def v1_state():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        c = contract_instance(w3, "v1", data["contract_address"])
        return ok(state=get_v1_state(c))
    except Exception as exc:
        return fail(str(exc))


@app.post("/v1/guess")
def v1_guess():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v1", data["contract_address"])
        guess_ = int(data["guess"])
        predicted = c.functions.previewGuess(guess_).call({"from": account.address})
        tx = c.functions.guess(guess_).build_transaction(build_tx(w3, account, {"gas": 300_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex(), result_code=predicted, result_label=result_label(predicted))
    except Exception as exc:
        return fail(str(exc))


# ---------- v2 ----------

@app.post("/v2/deploy")
def v2_deploy():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        address, receipt = deploy_contract(
            w3,
            "v2",
            data["playerA_private_key"],
            [as_checksum(data["playerB_address"]), int(data["secret_number"]), int(data["max_attempts"])],
            parse_eth(data["stake_eth"]),
        )
        return ok(contract_address=address, tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v2/state")
def v2_state():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        c = contract_instance(w3, "v2", data["contract_address"])
        return ok(state=get_v2_state(c, w3))
    except Exception as exc:
        return fail(str(exc))


@app.post("/v2/join")
def v2_join():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v2", data["contract_address"])
        stake = c.functions.stake().call()
        tx = c.functions.join().build_transaction(build_tx(w3, account, {"value": stake, "gas": 300_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v2/guess")
def v2_guess():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v2", data["contract_address"])
        guess_ = int(data["guess"])
        predicted = c.functions.previewGuess(guess_).call({"from": account.address})
        tx = c.functions.guess(guess_).build_transaction(build_tx(w3, account, {"gas": 400_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex(), result_code=predicted, result_label=result_label(predicted))
    except Exception as exc:
        return fail(str(exc))


# ---------- v3 ----------

@app.post("/v3/deploy")
def v3_deploy():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        address, receipt = deploy_contract(w3, "v3", data["deployer_private_key"], [])
        return ok(contract_address=address, tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v3/create_game")
def v3_create_game():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerA_private_key"])
        c = contract_instance(w3, "v3", data["contract_address"])
        tx = c.functions.createGame(
            as_checksum(data["playerB_address"]),
            int(data["secret_number"]),
            int(data["max_attempts"]),
        ).build_transaction(build_tx(w3, account, {"value": parse_eth(data["stake_eth"]), "gas": 600_000}))
        receipt = sign_and_send(w3, tx, data["playerA_private_key"])
        game_id = c.functions.totalGames().call() - 1
        return ok(game_id=game_id, tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v3/list_games")
def v3_list_games():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        c = contract_instance(w3, "v3", data["contract_address"])
        total = c.functions.totalGames().call()
        games = [get_v3_game(c, i) for i in range(total)]
        return ok(total_games=total, games=games)
    except Exception as exc:
        return fail(str(exc))


@app.post("/v3/state")
def v3_state():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        c = contract_instance(w3, "v3", data["contract_address"])
        game_id = int(data["game_id"])
        return ok(state=get_v3_game(c, game_id))
    except Exception as exc:
        return fail(str(exc))


@app.post("/v3/join_game")
def v3_join_game():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v3", data["contract_address"])
        game = c.functions.getGame(int(data["game_id"])).call()
        stake = game[4]
        tx = c.functions.joinGame(int(data["game_id"])).build_transaction(build_tx(w3, account, {"value": stake, "gas": 350_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v3/guess")
def v3_guess():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v3", data["contract_address"])
        game_id = int(data["game_id"])
        guess_ = int(data["guess"])
        predicted = c.functions.previewGuess(game_id, guess_).call({"from": account.address})
        tx = c.functions.guess(game_id, guess_).build_transaction(build_tx(w3, account, {"gas": 450_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex(), result_code=predicted, result_label=result_label(predicted))
    except Exception as exc:
        return fail(str(exc))


# ---------- v4 ----------

@app.post("/v4/prepare")
def v4_prepare():
    data = require_json()
    try:
        package = build_merkle_package(int(data["secret_number"]))
        return ok(merkle_root=package["root"], hints=package["hints"])
    except Exception as exc:
        return fail(str(exc))


@app.post("/v4/deploy")
def v4_deploy():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        address, receipt = deploy_contract(
            w3,
            "v4",
            data["playerA_private_key"],
            [as_checksum(data["playerB_address"]), data["merkle_root"], int(data["max_attempts"])],
            parse_eth(data["stake_eth"]),
        )
        return ok(contract_address=address, tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v4/state")
def v4_state():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        c = contract_instance(w3, "v4", data["contract_address"])
        return ok(state=get_v4_state(c, w3))
    except Exception as exc:
        return fail(str(exc))


@app.post("/v4/join")
def v4_join():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v4", data["contract_address"])
        stake = c.functions.stake().call()
        tx = c.functions.join().build_transaction(build_tx(w3, account, {"value": stake, "gas": 300_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v4/submit_guess")
def v4_submit_guess():
    data = require_json()
    try:
        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerB_private_key"])
        c = contract_instance(w3, "v4", data["contract_address"])
        guess_ = int(data["guess"])
        tx = c.functions.submitGuess(guess_).build_transaction(build_tx(w3, account, {"gas": 350_000}))
        receipt = sign_and_send(w3, tx, data["playerB_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex())
    except Exception as exc:
        return fail(str(exc))


@app.post("/v4/resolve_guess")
def v4_resolve_guess():
    data = require_json()
    try:
        secret = int(data["secret_number"])
        guess_ = int(data["guess"])
        package = build_merkle_package(secret)
        result_code = package["hints"][str(guess_)]
        proof = package["proofs"][str(guess_)]

        w3 = w3_from_rpc(data["rpc_url"])
        account = account_from_privkey(w3, data["playerA_private_key"])
        c = contract_instance(w3, "v4", data["contract_address"])
        tx = c.functions.resolveGuess(guess_, result_code, proof).build_transaction(build_tx(w3, account, {"gas": 500_000}))
        receipt = sign_and_send(w3, tx, data["playerA_private_key"])
        return ok(tx_hash=receipt.transactionHash.hex(), result_code=result_code, result_label=result_label(result_code), proof=proof)
    except Exception as exc:
        return fail(str(exc))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2020, debug=True)
