#!/usr/bin/env python3
"""vHYPE Vault Monitor — detects new withdrawal requests before they hit totalBalance."""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# === Load .env ===
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# === Config ===
CONTRACT = "0x88888880793F89cE85777FF2e0e2d366bf05b20c"
STAKING_ADDR = "0x8888888192a4a0593c13532ba48449fc24c3beda"
HYPERCORE_API = "https://api.hyperliquid.xyz/info"
RPCS = [
    "https://rpc.hyperliquid.xyz/evm",
    "https://hyperliquid-json-rpc.stakely.io",
    "https://rpc.countzero.xyz/evm",
]
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://app.ventuals.com",
    "User-Agent": "Mozilla/5.0",
}
SELECTORS = {
    "totalBalance": "0xad7a672f",
    "stakingBalance": "0x3b3dbb0f",
    "spotBalance": "0x2ccb5ba7",
    "exchangeRate": "0x3ba0b9a9",
    "batchesLength": "0x05d2db54",
    "getWithdraw": "0x18eaae05",
}
MAX_UINT256 = "f" * 64
STATE_FILE = Path(__file__).parent / ".monitor-state.json"
POLL_INTERVAL = 900  # seconds between polls (15min)
TVL_CHANGE_THRESHOLD = 5000  # HYPE — only alert if TVL moves more than this

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception as e:
        print(f"  [telegram] send failed: {e}", file=sys.stderr)


def fmt_tg(n):
    return f"{n:,.0f}" if n is not None else "—"


# === RPC ===
rpc_idx = 0
rpc_fail_until = [0.0] * len(RPCS)  # backoff per endpoint


def eth_call(selector, retries=6):
    global rpc_idx
    for attempt in range(retries):
        idx = rpc_idx % len(RPCS)
        if time.monotonic() < rpc_fail_until[idx]:
            rpc_idx += 1
            continue
        url = RPCS[idx]
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": CONTRACT, "data": selector}, "latest"],
            "id": 1,
        }).encode()
        req = urllib.request.Request(url, data=payload, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read())
                if "result" in body:
                    return body["result"]
                err = body.get("error", {}).get("message", "")
                if "rate" in err.lower():
                    rpc_fail_until[idx] = time.monotonic() + 10
                    rpc_idx += 1
                    continue
                if "revert" in err.lower():
                    rpc_idx += 1
                    continue
                raise Exception(err)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            rpc_fail_until[idx] = time.monotonic() + 5
            rpc_idx += 1
            continue
    raise Exception("all RPCs failed")


def hex18(h):
    return int(h, 16) / 1e18


def hex0(h):
    return int(h, 16)


# === HyperCore API ===
def hypercore_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        HYPERCORE_API, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def fetch_hypercore():
    """Get staking state from HyperCore."""
    summary = hypercore_post({"type": "delegatorSummary", "user": STAKING_ADDR})
    return {
        "unstaking": float(summary.get("totalPendingWithdrawal", "0")),
        "nUnstaking": int(summary.get("nPendingWithdrawals", 0)),
    }


# === Withdrawal parsing ===
def get_withdraw(idx):
    sel = SELECTORS["getWithdraw"] + hex(idx)[2:].zfill(64)
    d = eth_call(sel)[2:]
    slots = [d[i : i + 64] for i in range(0, len(d), 64)]
    return {
        "idx": int(slots[0], 16),
        "wallet": "0x" + slots[1][24:],
        "amount": hex18("0x" + slots[2]),
        "timestamp": int(slots[3], 16),
        "batchId": int(slots[4], 16) if slots[4] != MAX_UINT256 else -1,
        "isPending": slots[4] == MAX_UINT256,
    }


def find_true_queue_length(known_length):
    """Scan forward from known_length to find the true end of the queue.
    getWithdrawQueueLength() is stale — the new queueWithdraw function adds
    entries beyond it. Empty entries have wallet=0x000...0, amount=0, timestamp=0."""
    # First check if known_length itself is valid (entry at index known_length exists)
    try:
        w = get_withdraw(known_length)
        if w["timestamp"] == 0 and w["amount"] == 0:
            return known_length  # no new entries beyond last known
    except Exception:
        return known_length

    # Entry at known_length is valid, scan forward to find the end
    idx = known_length
    step = 64
    while step >= 1:
        try:
            w = get_withdraw(idx + step)
            if w["timestamp"] == 0 and w["amount"] == 0:
                step //= 2
            else:
                idx += step
        except Exception:
            step //= 2
        time.sleep(0.1)
    return idx + 1  # length = last valid index + 1


def count_pending(queue_length, first_pending_idx=None):
    """Count pending withdrawals (batchId == MAX_UINT256).
    Scans backwards from queue end to find pending entries."""
    if queue_length == 0:
        return 0, 0.0, queue_length

    # If we have a cached boundary, scan forward from it
    if first_pending_idx is not None and first_pending_idx < queue_length:
        try:
            w = get_withdraw(first_pending_idx)
            if w["isPending"]:
                count = 0
                total = 0.0
                for i in range(first_pending_idx, queue_length):
                    try:
                        w = get_withdraw(i)
                    except Exception:
                        break
                    if w["isPending"]:
                        count += 1
                        total += w["amount"]
                    # Don't break on non-pending — there can be gaps (cancelled entries)
                    time.sleep(0.1)
                return count, total, first_pending_idx
        except Exception:
            pass

    # Scan backwards to find where pending entries start
    first_pending = queue_length
    count = 0
    total = 0.0
    for i in range(queue_length - 1, max(queue_length - 500, -1), -1):
        try:
            w = get_withdraw(i)
        except Exception:
            break
        if w["isPending"]:
            count += 1
            total += w["amount"]
            first_pending = i
        elif count > 0:
            # Hit a non-pending entry after seeing pending ones — we've found the boundary
            break
        time.sleep(0.1)

    return count, total, first_pending


# === State persistence ===
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


# === Display ===
def fmt(n):
    return f"{n:,.0f}" if n is not None else "—"


def display(data, new_requests=None):
    ts = time.strftime("%H:%M:%S", time.localtime())
    rate = data["rate"]
    yld = (rate - 1) * 100

    print(f"\033[1m[{ts}] vHYPE Vault\033[0m")
    print(f"  TVL (delegated):  {fmt(data['totalBalance'])} HYPE")
    print(f"  Rate:             {rate:.6f} (+{yld:.3f}%)")
    print(f"  Staking:          {fmt(data['stakingBalance'])} HYPE")
    print(f"  Spot:             {fmt(data['spotBalance'])} HYPE")
    print(f"  Queue:            {data['queueLength']}  (batches: {data['batchCount']})")
    print(f"  Unstaking:        {fmt(data['unstaking'])} HYPE  ({data['nUnstaking']} ops)")
    print(f"  Pending:          {data['pendingCount']} reqs, {fmt(data['pendingHype'])} HYPE")

    safe = data["totalBalance"] - data.get("pendingHype", 0) - 500_000
    print(f"  Exit capacity:    {fmt(safe)} HYPE")

    if new_requests:
        print(f"\n  \033[93m⚠ {len(new_requests)} NEW withdrawal request(s):\033[0m")
        for w in new_requests:
            ts_str = time.strftime("%m-%d %H:%M", time.gmtime(w["timestamp"]))
            pending = "pending" if w["isPending"] else f"batch {w['batchId']}"
            print(f"    #{w['idx']}  {w['wallet']}  {w['amount']:>10,.1f} HYPE  {ts_str}  ({pending})")
        total_new = sum(w["amount"] for w in new_requests)
        print(f"    Total new: {total_new:,.1f} HYPE")

    print()


# === Telegram notifications ===
VAULT_EVM = "0x88888880793F89cE85777FF2e0e2d366bf05b20c"
HYPURRSCAN = "https://hypurrscan.io/address"
HYPEREVMSCAN = "https://hyperevmscan.io/address"


def wallet_links(addr):
    return f"[hypurrscan]({HYPURRSCAN}/{addr}) | [evmscan]({HYPEREVMSCAN}/{addr})"


def vault_recap(data):
    yld = (data["rate"] - 1) * 100
    safe = data["totalBalance"] - data.get("pendingHype", 0) - 500_000
    return (
        f"\n———————————————\n"
        f"*TVL* {fmt_tg(data['totalBalance'])} HYPE\n"
        f"*Rate* {data['rate']:.6f} (+{yld:.3f}%)\n"
        f"*Unstaking* {fmt_tg(data['unstaking'])} HYPE ({data['nUnstaking']} ops)\n"
        f"*Pending* {data['pendingCount']} reqs · {fmt_tg(data['pendingHype'])} HYPE\n"
        f"*Exit capacity* {fmt_tg(safe)} HYPE\n"
        f"Queue {data['queueLength']} · Batches {data['batchCount']}\n"
        f"[vault]({HYPEREVMSCAN}/{VAULT_EVM})"
    )


def notify_startup(data):
    msg = "*vHYPE Monitor started*" + vault_recap(data)
    send_telegram(msg)


def fmt_age(ts):
    """Format entry age as human-readable string."""
    age = time.time() - ts
    if age < 120:
        return "just now"
    if age < 3600:
        return f"{int(age / 60)}m ago"
    if age < 86400:
        return f"{int(age / 3600)}h ago"
    return f"{int(age / 86400)}d ago"


def notify_new_requests(new_requests, data):
    n = len(new_requests)
    total_new = sum(w["amount"] for w in new_requests)
    lines = [f"*{n} new withdrawal{'s' if n > 1 else ''}* · {total_new:,.1f} HYPE\n"]
    for w in new_requests[:10]:
        age = fmt_age(w["timestamp"])
        status = "pending" if w["isPending"] else f"batch {w['batchId']}"
        lines.append(
            f"▸ `{w['wallet']}`\n"
            f"  {w['amount']:,.1f} HYPE · {age} · {status}\n"
            f"  {wallet_links(w['wallet'])}"
        )
    if n > 10:
        lines.append(f"\n_… and {n - 10} more_")
    lines.append(vault_recap(data))
    send_telegram("\n".join(lines))


def notify_batch_created(old_count, new_count, data):
    msg = (
        f"*New batch created* (#{new_count})"
        + vault_recap(data)
    )
    send_telegram(msg)


def notify_tvl_change(old_tvl, new_tvl, data):
    delta = new_tvl - old_tvl
    arrow = "+" if delta > 0 else ""
    msg = (
        f"*TVL {arrow}{fmt_tg(delta)} HYPE*\n"
        f"{fmt_tg(old_tvl)} → {fmt_tg(new_tvl)}"
        + vault_recap(data)
    )
    send_telegram(msg)


def notify_error(err, consecutive):
    msg = f"*Monitor error* ({consecutive} consecutive)\n`{err}`"
    send_telegram(msg)


# === Main loop ===
def fetch_snapshot():
    results = {}
    for name, sel in SELECTORS.items():
        if name == "getWithdraw":
            continue
        results[name] = eth_call(sel)
        time.sleep(0.15)

    return {
        "rate": hex18(results["exchangeRate"]),
        "totalBalance": hex18(results["totalBalance"]),
        "stakingBalance": hex18(results["stakingBalance"]),
        "spotBalance": hex18(results["spotBalance"]),
        "batchCount": hex0(results["batchesLength"]),
    }


def run():
    state = load_state()
    last_queue_len = state.get("lastQueueLength", 0)
    last_total_bal = state.get("lastTotalBalance")
    last_batch_count = state.get("lastBatchCount")
    first_pending_idx = state.get("firstPendingIdx")
    first_run = True  # always send startup notification on service (re)start
    consecutive_errors = 0

    print("\033[1mvHYPE Vault Monitor\033[0m")
    tg_status = "enabled" if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID else "disabled"
    print(f"Polling every {POLL_INTERVAL}s. Telegram: {tg_status}. Ctrl+C to stop.\n")

    while True:
        try:
            data = fetch_snapshot()
            consecutive_errors = 0

            # Find true queue length (getWithdrawQueueLength is stale)
            ql = find_true_queue_length(last_queue_len if last_queue_len > 0 else 3139)
            data["queueLength"] = ql

            # HyperCore: unstaking state
            hc = fetch_hypercore()
            data["unstaking"] = hc["unstaking"]
            data["nUnstaking"] = hc["nUnstaking"]

            # Detect new withdrawal requests
            new_requests = []
            if not first_run and ql > last_queue_len:
                for i in range(last_queue_len, ql):
                    try:
                        w = get_withdraw(i)
                        if w["amount"] > 0 and w["timestamp"] > 0:
                            new_requests.append(w)
                    except Exception:
                        pass
                    time.sleep(0.15)

            # Count pending (batchId == MAX_UINT256)
            p_count, p_hype, first_pending_idx = count_pending(
                ql, first_pending_idx
            )
            data["pendingCount"] = p_count
            data["pendingHype"] = p_hype

            # Display
            os.system("clear" if os.name == "posix" else "cls")
            display(data, new_requests if new_requests else None)

            # Telegram notifications
            if first_run:
                notify_startup(data)
            if new_requests:
                notify_new_requests(new_requests, data)
            if not first_run and last_batch_count is not None and data["batchCount"] > last_batch_count:
                notify_batch_created(last_batch_count, data["batchCount"], data)
            if not first_run and last_total_bal is not None:
                if abs(data["totalBalance"] - last_total_bal) > TVL_CHANGE_THRESHOLD:
                    notify_tvl_change(last_total_bal, data["totalBalance"], data)

            # Persist
            last_queue_len = ql
            last_total_bal = data["totalBalance"]
            last_batch_count = data["batchCount"]
            first_run = False
            save_state({
                "lastQueueLength": ql,
                "firstPendingIdx": first_pending_idx,
                "lastTotalBalance": data["totalBalance"],
                "lastBatchCount": data["batchCount"],
            })

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            consecutive_errors += 1
            print(f"\033[91mError: {e}\033[0m")
            if consecutive_errors == 3:
                notify_error(str(e), consecutive_errors)

        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


def test_telegram():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars first.")
        sys.exit(1)
    print(f"Sending test message to chat {TELEGRAM_CHAT_ID}...", flush=True)
    send_telegram("*vHYPE Monitor* — test message received")
    print("Done. Check your Telegram.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_telegram()
    else:
        run()
