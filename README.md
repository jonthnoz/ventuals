# vHYPE Vault

vHYPE is a liquid staking token (LST) for HYPE on Hyperliquid, by Ventuals. Deposit HYPE → receive vHYPE → earn validator staking yield automatically.

## Exchange Rate

1 vHYPE = X HYPE, where X starts at 1.0 and grows as staking rewards accrue. Your vHYPE quantity stays constant; its value in HYPE increases. Yield % = `(rate - 1) * 100`.

## On-chain Values Explained

| Function | What it returns | Notes |
|----------|----------------|-------|
| `totalBalance()` | Net user deposits in HYPE | **TVL shown on the app.** Only counts HYPE backing active vHYPE holders. |
| `stakingAccountBalance()` | HYPE in HyperCore staking account | = `totalBalance` + HYPE being unstaked in batch lockups. |
| `spotAccountBalance()` | HYPE in HyperCore spot account | = unclaimed withdrawals (unstaking finished, awaiting user claim). |
| `exchangeRate()` | vHYPE→HYPE rate (18 decimals) | Should only increase. Decrease = slashing. |
| `getWithdrawQueueLength()` | Total withdrawal requests ever created | Cumulative — includes completed/cancelled. |
| `getBatchesLength()` | Total batches ever created | Cumulative. Incrementing = vault actively processing. |
| `minimumStakeBalance()` | Floor for staking balance | Currently 500,000 HYPE. |

**Accounting identity** (verified on-chain):

```
stakingAccountBalance = totalBalance + HYPE in active batch lockups
spotAccountBalance    = HYPE finished unstaking, waiting for users to claim
staking + spot - totalBalance = total HYPE in the withdrawal pipeline
```

## Withdrawal Queue

Withdrawals take **~7-8.5 days** due to Hyperliquid's native staking lockup.

```
Request → QUEUED → IN BATCH (unstaking, 7-8.5d lockup) → CLAIMABLE → CLAIMED
              |                                                          |
              |  can cancel before batch assignment           HYPE lands in
              → CANCELLED                                   HyperCore spot account
```

Where HYPE lives at each stage:
- **QUEUED**: still in `stakingAccountBalance` (earning yield)
- **IN BATCH**: still in `stakingAccountBalance` (locked, unstaking)
- **CLAIMABLE**: moved to `spotAccountBalance` (lockup finished)
- **CLAIMED**: gone from vault entirely

- **FIFO**: first-come, first-served
- **While queued**: still earns staking yield (no points)
- **Cancellable**: before batch processing starts
- **No fees**
- **Claim destination**: HyperCore spot account (not HyperEVM wallet)

### Batches

Queued withdrawals are grouped into batches. Each batch triggers an unstaking operation on HyperCore, waits the lockup period, then becomes claimable.

### Minimum Stake: 500,000 HYPE

If `stakingAccountBalance` drops to this floor, **all withdrawals pause** until new deposits push it back above.

### Queue Length Caveat

`getWithdrawQueueLength()` is **stale** — it only tracks entries from the original withdrawal function. The newer `queueWithdraw()` creates entries beyond this counter. `getWithdraw(i)` works for all entries regardless. The monitor finds the true queue end by scanning forward until it hits an empty entry (wallet=0x0, amount=0).

### Pending Detection

New entries from `queueWithdraw()` have `batchId = MAX_UINT256` (0xfff…f) = **pending**. When the admin calls `processBatch()`, pending entries get assigned a real batchId and HyperCore unstaking starts. The monitor counts entries with `batchId == MAX_UINT256` as pending — these are future TVL drops that haven't been batched yet.

## Exit Safety

`totalBalance` drops when the admin **seals a batch** and initiates HyperCore unstaking. When you request a withdrawal, vHYPE is burned and a queue entry is created, but `totalBalance` is unaffected until the admin batches.

Queued withdrawals (created after the last unstaking) are an **early warning** — they represent future TVL drops that haven't happened yet.

**If `totalBalance - queuedHYPE - 500K > 0`, all current requests can be processed.**

The metric to watch: **`totalBalance - queuedHYPE - 500,000`** = remaining withdrawal capacity (exit capacity).

## Health Signals

- **Healthy**: rate increasing, staking well above 500K, low pending count
- **Pressure**: pending count/amount growing = withdrawal demand building
- **Critical**: `totalBalance` approaching 500K = new withdrawals may freeze
- **Abnormal**: rate decrease = slashing event (extremely rare)

## Monitor

`monitor.py` polls the vault every 15 minutes and sends Telegram alerts for:

- **Startup** — current vault state on service (re)start
- **New withdrawals** — wallet, amount, pending/batch status
- **Batch created** — admin sealed a new batch (TVL will drop)
- **TVL change** — totalBalance moved by more than 5,000 HYPE

Runs as a systemd user service (`vhype-monitor`). Config via `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Use `python3 monitor.py --test` to verify Telegram delivery.

## Contract

- **Proxy**: `0x88888880793F89cE85777FF2e0e2d366bf05b20c` (ERC1967)
- **Implementation**: StakingVaultManager at `0x0000000c21e635b59edff54e70fe21315fa9b245`
- **HyperCore staking address**: `0x8888888192a4a0593c13532ba48449fc24c3beda`
- **Chain**: HyperEVM
- **RPC**: `https://rpc.hyperliquid.xyz/evm` (not archival — always returns latest state regardless of requested block)
