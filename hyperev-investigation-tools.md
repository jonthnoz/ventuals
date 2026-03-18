# HyperEVM Investigation Tools & Techniques

## Working APIs

### Blockscout (Hyperscan) — best for decoded tx data
```
Base: https://www.hyperscan.com/api/v2

# Address transactions (50/page, decoded function names)
GET /addresses/{addr}/transactions
GET /addresses/{addr}/transactions?next_page_params=...

# Token transfers
GET /addresses/{addr}/token-transfers

# Internal transactions (contract-to-contract calls)
GET /addresses/{addr}/internal-transactions

# Address info/labels
GET /addresses/{addr}

# Transaction detail
GET /transactions/{txhash}
```

### HyperEVM RPC — for direct contract reads
```
POST https://rpc.hyperliquid.xyz/evm
Fallbacks:
  - https://hyperliquid-json-rpc.stakely.io (needs Origin header)
  - https://rpc.countzero.xyz/evm (needs Origin header)

Headers:
  Content-Type: application/json
  Origin: https://app.ventuals.com
  User-Agent: Mozilla/5.0
```

Note: RPCs are NOT archival — always return latest state regardless of requested block.
`eth_getLogs` returns 0 results for most contracts (not supported or events not indexed).

### HyperCore API — for staking/delegation data
```
POST https://api.hyperliquid.xyz/info
Content-Type: application/json

# Delegator summary (staked amount, pending withdrawals)
{"type": "delegatorSummary", "user": "0x..."}

# Delegation history (all unstaking/finalization events)
{"type": "delegatorHistory", "user": "0x..."}
```

### Hypurrscan API — HyperCore-side data
```
Base: https://api.hypurrscan.io
Docs: https://api.hypurrscan.io/ui (Swagger)
Rate limit: 1000 req/min per IP

# Address details (labels, info)
GET /addressDetails/{address}

# Address tags/labels
GET /tags/{address}

# Bulk address labels
POST /tags/addresses  (body: array of addresses)

# Token holders
GET /holders/{token}
GET /holdersWithLimit/{token}/{limit}

# Global known labels
GET /globalAliases

# Search
GET /search/{query}
```

Note: Hypurrscan has no per-address transaction history endpoint.
Use `hypurrscan.io/address/{addr}` via browser for full HyperCore tx history.
The site renders client-side (Vue.js) — WebFetch won't work, use agent-browser.

### HyperCore API — Wallet Profiling
```
POST https://api.hyperliquid.xyz/info
Content-Type: application/json

# Referral info (code used, referrer, cumulative volume)
{"type": "referral", "user": "0x..."}
→ referredBy: {referrer, code} | null
→ cumVlm: total trading volume (0 = never traded)
→ referrerState.data.nReferrals: how many people used this code

# Subaccounts (reveals wallet relationships!)
{"type": "subAccounts", "user": "0x..."}
→ [{name, subAccountUser, master, clearinghouseState, spotState}]
→ Matching subaccount names across wallets = strong sybil signal

# Delegator info (staking)
{"type": "delegatorSummary", "user": "0x..."}
{"type": "delegatorHistory", "user": "0x..."}

# Account state
{"type": "clearinghouseState", "user": "0x..."}  → perp positions, margin
{"type": "spotClearinghouseState", "user": "0x..."}  → spot balances

# Trading history
{"type": "userFills", "user": "0x..."}  → trade fills
{"type": "userNonFundingLedgerUpdates", "user": "0x..."}  → ledger events
```

### Etherscan V2 API — verified source code (requires API key)
```
# Works for HyperEVM (chainid=999) via unified Etherscan V2 endpoint
# Requires ETHERSCAN_KEY in .env

# Get verified source code + ABI
GET https://api.etherscan.io/v2/api?chainid=999&module=contract&action=getsourcecode&address={addr}&apikey={key}

# Get ABI only
GET https://api.etherscan.io/v2/api?chainid=999&module=contract&action=getabi&address={addr}&apikey={key}
```

For proxy contracts (like vHYPE `0x8888...b20c`), the proxy itself is just ERC1967.
Query the **implementation address** to get the actual logic source code.
Find implementation via Blockscout: `GET /smart-contracts/{proxy_addr}` → `implementations[0].address`

### Function Selector Computation
```python
# Ethereum uses keccak-256 (NOT NIST SHA3-256)
from Crypto.Hash import keccak
k = keccak.new(digest_bits=256)
k.update(b"functionName(uint256)")
selector = "0x" + k.hexdigest()[:8]
```

Gotcha: Python's `hashlib.sha3_256` is NOT keccak-256. Use `pycryptodome` (`Crypto.Hash.keccak`).

### Function Selector Decoding (unknown selectors)
```
# 4byte.directory
GET https://www.4byte.directory/api/v1/signatures/?hex_signature=0xd2dbb0b0

# Openchain
GET https://api.openchain.xyz/signature-database/v1/lookup?function=0xd2dbb0b0
```

## Block Explorers (for manual browsing)

| Explorer | URL | Notes |
|----------|-----|-------|
| Hypurrscan | `https://hypurrscan.io/address/{addr}` | No `app.` prefix |
| HyperEVMScan | `https://hyperevmscan.io/address/{addr}` | Alternative explorer |
| Hyperscan (Blockscout) | `https://www.hyperscan.com/address/{addr}` | Has working API |

## Reading vHYPE Withdrawal Queue

The contract uses a linked list internally. Legacy `getWithdraw(index)` still works for reading entries, but `getWithdrawQueueLength()` is stale. Use `nextWithdrawId()` and `lastProcessedWithdrawId()` for accurate counts.

```python
# getWithdraw(uint256 index) — selector 0x18eaae05
# Response ABI slots (each 64 hex chars):
#   slot 0: index
#   slot 1: wallet address (last 40 chars)
#   slot 2: amount in wei (÷ 1e18 for HYPE)
#   slot 3: timestamp (unix)
#   slot 4: batchId (0xfff...f = pending/MAX_UINT256)

# Key selectors (keccak-256):
#   nextWithdrawId()           0x77ae46e5  — next ID to assign
#   lastProcessedWithdrawId()  0x8a8ef4e4  — last entry processed in a batch
#   currentBatchIndex()        0x6090b30e  — current/next batch
#   totalHypeProcessed()       0x46194d6c  — cumulative HYPE through batches
#   totalHypeClaimed()         0xf8379728  — cumulative HYPE claimed by users
#   lastFinalizedBatchTime()   0x1a28c0b5  — timestamp of last finalizeBatch
#   getBatch(uint256)          0x5ac44282  — batch struct (vhypeProcessed, rate, slashed, finalizedAt)
```

The monitor finds the true queue end by scanning forward from the last known position until it hits an empty entry (wallet=0x0, amount=0).

## Curl Example

```bash
# Read withdrawal entry at index 3200
curl -s -X POST https://rpc.hyperliquid.xyz/evm \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{
    "to":"0x88888880793F89cE85777FF2e0e2d366bf05b20c",
    "data":"0x18eaae050000000000000000000000000000000000000000000000000000000000000c80"
  },"latest"],"id":1}' | python3 -c "
import json,sys
d=json.load(sys.stdin)['result'][2:]
slots=[d[i:i+64] for i in range(0,len(d),64)]
print(f'wallet: 0x{slots[1][24:]}')
print(f'amount: {int(slots[2],16)/1e18:.2f} HYPE')
print(f'timestamp: {int(slots[3],16)}')
print(f'batchId: {\"PENDING\" if slots[4]==\"f\"*64 else int(slots[4],16)}')
"
```

## Investigation Patterns

### Tracing wallet behavior
1. Get tx history from Blockscout API (decoded function names)
2. Look for: deposit/withdraw calls, approve patterns, swap activity
3. Identify contracts they interact with — search contract addresses on Blockscout for labels
4. Check token transfers for flow of funds
5. Cross-reference with known protocol contracts (see below)

### Identifying wallet clusters
- **HyperCore subaccounts**: `subAccounts` API reveals named sub-wallets. Sequential names (e.g. "IL", "IL2") across wallets = same operator
- **Referral codes**: `referral` API shows which code a wallet used. Shared non-generic codes can indicate clusters, but large codes (WEB3: 1,391 refs, DEFILLAMAO: 6,177, MMREFCSI: 34,174) are NOT clustering signals
- **Zero trading volume**: `referral.cumVlm == "0.0"` means wallet never traded on HyperCore — suspicious if the wallet only does vHYPE deposits
- Same timestamps (within seconds) = likely same operator or bot
- Exact same amounts across different wallets
- Common contract interactions beyond the target contract
- Sequential address prefixes (vanity addresses or CREATE2)
- Dust amounts (0.1 ETH) sent to activate wallets
- **Funding chain analysis**: Trace EVM token transfers back to find the original source. Common funding source across multiple wallets = sybil evidence. Use Hypurrscan browser for HyperCore-side transfer history (deposits from CEXes, bridges)

### Known HyperEVM Protocol Contracts

| Protocol | Category | Key Contracts | Notes |
|----------|----------|---------------|-------|
| vHYPE (Ventuals) | LST | `0x88888880793F89cE85777FF2e0e2d366bf05b20c` | ~0.9% yield, 7-8d unbonding |
| Kinetiq (kHYPE) | LST | Look for kHYPE token address | 2.37% APY, no unbonding, #1 by TVL ($833M) |
| Kinetiq sKNTQ | Staking | `0x696238e0` (Staked KNTQ) | KNTQ governance staking |
| LoopedHYPE (LHYPE) | Leveraged LST | TBD | 3.7% APY, 3x-15x leverage, $136M |
| Valantis (stHYPE) | LST | `0xB96f0736` (mint), tokenUri "hyperstakevalantis" | #2 LST, acquired by Valantis |
| Morpho Blue | Lending | `0x2900ABd7` (MetaMorphoV1_1) | $500M+ TVL on HyperEVM |
| Morpho Bundler3 | Helper | `0xa3F50477` | Multicall bundles for Morpho |
| Aave | Lending | `0x00A89d7a` (Pool), `0x49558c79` (Gateway) | borrow/lend, leveraged staking |
| HyperLend | Lending | TBD | $540M, Aave-like, HPL airdrop |
| Felix | CDP/Lending | Uses Morpho underneath | feUSD stablecoin, Vanilla Markets |
| HypurrFi | Lending | TBD | Euler-powered, USDXL, 8-20% APY |
| KittenSwap | DEX | TBD | ve(3,3), largest HyperEVM DEX, KITTEN airdrop |
| HyperSwap | DEX | TBD | Uniswap v2/v3 fork, xSWAP rewards |
| Pendle | Yield | TBD | $300M TVL, yield tokenization on kHYPE/stHYPE |
| Veda/BoringVault | Yield | Various proxy contracts | Automated yield vaults, $54M on HL |
| Hyperbeat | Yield | TBD | Multi-asset vaults, Veda-powered |
| RedSnwapper | DEX | `0xAC4c6e212A361c968F1725b4d055b47E63F80b75` | Token swaps |
| CCTP/Circle | Bridge | `0x81D40F21` (MessageTransmitter) | Cross-chain USDC |
| WCTC | Wrapped | `0x5555555555...` | Wrapped native token |

### Web Research Targets
- DeFiLlama: `https://defillama.com/chain/Hyperliquid` — TVL by protocol
- Kinetiq docs: `https://docs.kinetiq.xyz/`
- Morpho on HyperEVM: MIP-118 governance proposal
- Valantis/stHYPE docs: `https://docs.valantis.xyz/stakedhype/`
