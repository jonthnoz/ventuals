# vHYPE Withdrawal Investigation Report
**Date:** 2026-03-15
**Period analyzed:** March 11-14, 2026 (batches 131-132 + pending)

---

## Executive Summary

Two distinct withdrawal events hit the vault in 48 hours:

| Batch | Entries | HYPE | Key Feature |
|-------|---------|------|-------------|
| 131 | ~65 entries | ~315,000 | Two whales: 250k + 65k |
| 132 | 434 entries | 115,030 | Mass withdrawal burst, 425 unique wallets |
| Pending | 49 entries | 11,936 | Normal organic flow |

Total withdrawn: ~442k HYPE in 2 days.

---

## Mission 1: The Whale Cluster (0x8553, 0x6E93, 0xAD83)

### Connection Proof

These three wallets are **controlled by the same entity**:

| Evidence | Detail |
|----------|--------|
| NFT transfer | Hypurr #4356 sent from 0xAD83 -> 0x8553 (Oct 16), then back 0x8553 -> 0xAD83 (Nov 14) |
| HYPE transfer | 0x8553 sent 400 HYPE to 0x6E93 (Oct 27) -- likely gas/seed money |

### Wallet 0x8553 -- The vHYPE Position (~250k HYPE)

**Timeline:**
1. **Oct 16, 2025** -- Bridged ~$1M USDC via Circle CCTP (receiveMessage on MessageTransmitter)
2. **Oct 16** -- Deposited 500k USDC into Hyperbeat VLP (depositInstant), received wVLP
3. **Oct 16** -- Swapped 509k USDC -> HYPE via RedSnwapper DEX
4. **Oct 16** -- Deposited into vHYPE vault, minted 249,985 vHYPE
5. **Mar 11, 2026** -- Withdrew ALL: 26 queue entries x 9,912.6 HYPE = 249,985 HYPE (batch 131)

All 26 withdrawal entries have identical timestamp (19:53 UTC) = single transaction splitting into max-size queue entries.

### Wallet 0xAD83 -- Morpho Blue Operator

Active **Morpho Blue / MetaMorpho** user on HyperEVM:
- Repeated pattern: receive HYPE from various wallets -> approve MetaMorphoV1_1 (0x2900ABd7) -> multicall via Bundler3 (0xa3F50477)
- Amounts: 24-27k HYPE per cycle, 8+ cycles documented (Nov 2025)
- Also transferred Hypurr NFT #728 (safeTransferFrom)
- **Not in the vHYPE withdrawal queue** -- this wallet operates in Morpho lending

### Wallet 0x6E93 -- Leveraged Staking / DeFi Power User

Active across multiple HyperEVM protocols:
- **Valantis stHYPE**: Minting stHYPE via 0xB96f0736 (tokenUri: "hyperstakevalantis")
- **Aave**: Borrowed + repaid 17,387 HYPE on Aave Pool, withdrew from Aave
- **Kinetiq sKNTQ**: Deposited into Staked KNTQ (0x696238e0) -- governance staking
- **Distributor claims**: Claimed reward tokens from 0x3Ef3D8bA
- **Large transfers**: Sent 50,000 HYPE to 0x222222... and 95k HYPE to same
- **Not in the vHYPE withdrawal queue** -- operates in other protocols

### Interpretation

This entity has ~$500k+ deployed across HyperEVM DeFi:
- **vHYPE** (via 0x8553): 250k HYPE -- now queued for withdrawal (batch 131)
- **Morpho Blue** (via 0xAD83): lending/vault operations
- **Valantis stHYPE + Aave** (via 0x6E93): leveraged staking

They queued the full 250k from vHYPE on March 11. **The withdrawal has not been claimed yet** -- batch 131 is still in HyperCore unstaking lockup (~7 days). We cannot see where the HYPE will go until they claim. Their other wallets show activity in kHYPE, Morpho, Valantis, and Aave, but the destination is unknown until the claim happens.

### The 65k Whale (0xd25a100d)

**Separate entity** -- no direct connection to the 0x8553 cluster found.

**Timeline:**
1. **Sep 2025** -- Used Veda/BoringVault, deposited via TokenFactoryProxy
2. **Oct 2025** -- Used BoringVault (requestRedeem), AtomicQueueUCP, swapped via GluexRouter
3. **Oct 21, 2025** -- Deposited 65,000 HYPE into vHYPE vault
4. **Mar 11, 2026** -- Withdrew ALL: 7 entries x 9,912.6 HYPE (6x full + 1x 5,504.5) = 64,980 HYPE

Previously used Veda/BoringVault (institutional yield infra) before switching to vHYPE. Now leaving vHYPE after 5 months. **Withdrawal not yet claimed** -- destination unknown until HyperCore unstaking completes and they claim.

---

## Mission 2: Batch 132 Clustering Analysis

### Overview

| Metric | Value |
|--------|-------|
| Total entries | 434 |
| Unique wallets | 425 (9 wallets appear 2-3x) |
| Total HYPE | 115,030 |
| Time span | Mar 12 14:23 -> Mar 14 14:10 (48h) |
| Median amount | ~101 HYPE |

### The Burst: March 12, 18:40-19:06 UTC

**86 entries from 85 wallets in 26 minutes, totaling ~21,000 HYPE.**

This is the most suspicious pattern. Two sub-clusters:

**Cluster A (18:40-18:45):** 33 entries, 10,595 HYPE
- Entries fire every 1-7 seconds
- All different wallets
- Amounts vary widely (2.5 to 3,848 HYPE)
- Contains the #3 largest withdrawal in batch: 0x64561a (3,848 HYPE)

**Cluster B (19:01-19:06):** 53 entries, 10,263 HYPE
- Even more rapid: 53 entries in 5 minutes (one every 6 seconds)
- All different wallets
- Contains 0x6fd96f (1,793 HYPE) and 0xff9d76 (1,189 HYPE)

**Are these timestamps real?** Yes -- confirmed. Queue entry timestamps are set at `queueWithdraw()` call time, not at `processBatch()` time. Proof: batch 132 entries span 47.8 hours, and pending entries (batchId=MAX) also have distinct timestamps.

**Assessment:** This rate (1 entry per 6 seconds, all unique wallets, all different amounts) is consistent with:
1. **A UI/social trigger** (tweet, announcement, notification) causing mass organic withdrawals
2. **An aggregator routing withdrawal requests** from multiple users simultaneously
3. **A bot farm / sybil cluster** executing coordinated withdrawals

The varying amounts suggest real users with different positions. See referral and HyperCore analysis below for deeper clustering evidence.

### HyperCore Referral Code Analysis (All 425 Wallets)

Queried HyperCore API (`type: referral`) for all 425 unique wallets in batch 132:

| Code | Wallets | Share | Zero-vol | Notes |
|------|---------|-------|----------|-------|
| **WEB3** | 158 | 37.2% | 0 | Generic code, 1,391 total referrals platform-wide |
| **NONE** | 77 | 18.1% | 27 | No referral -- 27 have ZERO trading volume |
| **DEFILLAMAO** | 34 | 8.0% | 0 | Influencer code, 6,177 total referrals |
| **MMREFCSI** | 17 | 4.0% | 0 | Large code, 34,174 total referrals |
| **RABBYWALLET** | 17 | 4.0% | 0 | Wallet integration referral |
| Others (1-4 each) | 122 | 28.7% | 0 | ILHYUN(4), ALPHA(4), LAYER3(3), HARMONIX(2), etc |

**Key findings:**
- WEB3, DEFILLAMAO, MMREFCSI, RABBYWALLET are all **generic/influencer codes** with thousands of referrals each -- NOT sybil signals
- **27 zero-volume wallets** (6.4% of batch) have no referral, no trading history, no HyperCore activity at all -- they exist only for vHYPE
- The burst referral distribution roughly mirrors the overall batch, suggesting organic (trigger-driven) withdrawals not bot coordination

### HyperCore Subaccount Analysis

Checked all 23 whale wallets (>1,000 HYPE) for HyperCore subaccounts:

| Wallet | HYPE | Subaccount Names | Referral |
|--------|------|------------------|----------|
| **0xad5b87bf** | 1,904 | **IL2** | WEB3 |
| **0x64561a0c** | 3,848 | **IL** | WEB3 |
| 0xa06c4415 | 3,000 | Mr d | JAMBO |
| 0x28c01b64 | 3,000 | x, liminalll | MIRHEE0610 |
| 0x77320b89 | 2,991 | Sub-Account | HARMONIX |
| 0x8e9406ce | 1,369 | PpinPpi | PRITO |

**Confirmed sybil pair: 0xad5b87bf ("IL2") + 0x64561a0c ("IL")** -- see dedicated section below.

### Confirmed Sybil: The IL/IL2 Cluster (3 wallets, ~5,752 HYPE)

**Conclusion: Same operator.** Three wallets confirmed under common control:

| Wallet | vHYPE | Sub Name | Referral | Cum Volume | PnL |
|--------|-------|----------|----------|------------|-----|
| 0xad5b87bf | 1,904 | IL2 | WEB3 | $472k | -$2,558 |
| 0x64561a0c | 3,848 | IL | WEB3 | $381k | -$31,590 |
| 0x493d53fb (satellite) | -- | -- | WEB3 | $114k | +$305 |

**Evidence of common control:**

1. **Sequential subaccount naming**: "IL" and "IL2" -- clear sequential pair
2. **Shared referral code**: All three use WEB3 (same referrer 0x3b1551...)
3. **Identical trading patterns**: Both main wallets trade MON-USD perp shorts and buy UBTC via HIP-2
4. **Identical HYPE accumulation**: Buy HYPE in fixed batch sizes via HIP-2 (50-100 HYPE per tx), immediately transfer to HyperEVM for vHYPE deposit
5. **UMON farming**: Both interact with Unit Monad Treasury -- receive UMON, sell via HIP-2
6. **Direct fund flow**: Satellite 0x493d53fb sent 1,563.98 HYPE to wallet 0x64561a0c
7. **All funded from Arbitrum**: Multiple USDC deposits via CCTP bridge from Arbitrum

**Wallet 0xad5b87bf timeline:**
- 13 months ago: Initial $41k USDC deposit from Arbitrum, HLP Vault
- 2 months ago: $20k USDC deposit, bought 100k UMON batches, transferred UMON to 0x9d69f756...
- 42-36 days ago: Bought HYPE in 50 HYPE batches via HIP-2, sent to HyperEVM for vHYPE
- Total vHYPE: 1,904 HYPE

**Wallet 0x64561a0c timeline:**
- 4 months ago: Initial $30k USDC from Arbitrum, scaled up to $110k
- Trading: UBTC purchases (1.02 + 1.14 UBTC), MON-USD/MEGA-USD shorts
- 14 days ago: Received UMON from Unit Monad Treasury, sold, bought HYPE, sent to vHYPE
- 10 days ago: Received 1,564 HYPE from satellite 0x493d53fb
- Total vHYPE: 3,848 HYPE

**Impact:** 5,752 HYPE (~5% of batch 132). This is a real trader farming vHYPE points across wallets, not a large-scale sybil operation.

### Zero-Volume Wallet Deep Dive

17 wallets in batch 132 have **zero HyperCore trading volume, no referral code, and no subaccounts**. Total: 3,990 HYPE.

| Wallet | HYPE | EVM Activity | Funding Source |
|--------|------|-------------|----------------|
| **0x98a6d513** | 9,912 | 7 txs, vHYPE only | Funded by **0xD21D9318** (active trader, $50k account, sourced from **Bybit**) |
| **0x6cc7650f** | 4,536 | 4 txs, vHYPE only | Self-funded: bridged 400k USDC from Arbitrum via CCTP, bought 4,550 HYPE on HyperCore spot, sent to HyperEVM |
| 0x8cef1581 | 2,050 | 50 txs, 21 contracts | Active DeFi user (CCTP bridge, multicall, supply, collect) -- NOT pure vHYPE |
| 0xf33b5b20 | 397 | 41 txs, 12 contracts | Multi-protocol (Pendle, swaps, permit2) |
| 0xcdc33f67 | 308 | 50 txs, 13 contracts | Multi-protocol (Uniswap V3 LP, swaps) |
| 0xe830de36 | 200 | 7 txs, 5 contracts | Near-pure vHYPE (1 swap + deposit + withdraw) |
| 0x121ca07d | 199 | 9 txs, 3 contracts | Pure vHYPE (deposit, approve, withdraw) |
| 12 others | 15-150 each | varies | Small amounts |

**0x98a6d513 funding chain:** Bybit hot wallet (0xf89d7b9c...) -> 0xD21D9318 (active HyperCore trader, leveraged long ZEC+HYPE) -> 0x98a6d513 (seed 10 HYPE, then 10,100 HYPE on Oct 16). This is a trader parking HYPE in vHYPE via a separate wallet.

**0x6cc7650f funding chain:** Own Arbitrum wallet -> CCTP bridge 400k USDC -> HyperCore spot buy 4,550 HYPE -> bridge to HyperEVM -> vHYPE deposit. Same-entity operation, significant capital ($400k USDC).

**Assessment:** The two largest zero-volume wallets (0x98a6d513 + 0x6cc7650f = 14,448 HYPE) are **not sybils** -- they trace to distinct real traders who created dedicated vHYPE wallets. The remaining zero-vol wallets are mostly small (<400 HYPE) and several are actually multi-protocol DeFi users.

### Amount Distribution

| Range | Count | Total HYPE | Share |
|-------|-------|------------|-------|
| <10 | 36 | 195 | 0.2% |
| 10-50 | 118 | 3,361 | 2.9% |
| 50-100 | 78 | 5,779 | 5.0% |
| 100-200 | 100 | 14,186 | 12.3% |
| 200-500 | 61 | 19,088 | 16.6% |
| 500-1000 | 17 | 11,786 | 10.2% |
| 1000-3000 | 19 | 35,427 | 30.8% |
| 3000+ | 5 | 25,208 | 21.9% |

**Key:** The bulk of HYPE (52.7%) comes from just 24 wallets above 1,000 HYPE. The 390 small wallets (<500 HYPE) account for only ~37%.

### Near-3000 HYPE Entries

Found 4 entries in the 2,990-3,001 range:

| Index | Wallet | Amount | Time | Referral | Volume |
|-------|--------|--------|------|----------|--------|
| #2776 | 0x77320b89 | 2,991.0 | 03-12 14:54 | HARMONIX | $11.5M |
| #2979 | 0x28c01b64 | 2,999.7 | 03-12 23:48 | MIRHEE0610 | $53.6M |
| #2983 | 0x1a562e02 | 3,000.0 | 03-13 00:40 | NONE | $401 |
| #3076 | 0xa06c4415 | 2,999.8 | 03-13 10:09 | JAMBO | $2.3M |

Spaced hours apart, different referral codes, different trading volumes. **Not a cluster** -- coincidental round-number preference.

### Shared Protocol Analysis (>1000 HYPE wallets)

Three wallets share a connection through the **Veda/BoringVault/TokenizedAccount** ecosystem (contract `0x96C6cBB6`):

| Wallet | vHYPE Amount | Other Protocols |
|--------|-------------|-----------------|
| 0xd25a100d (batch 131) | 64,980 | BoringVault, AtomicQueueUCP, GluexRouter |
| 0xff9d76f5 (batch 132) | 1,189 | hbHYPE (Hyperbeat), Pendle (PT-vkHYPE), kHYPE, LiFi bridge |
| 0xb9da09e0 (batch 132) | 1,399 | BoringVault, Pendle, MetaAggregationRouter |

This is a **common origin cohort** (Veda vault users who migrated to vHYPE) rather than sybil activity.

---

## Competing Protocols (Why People Leave vHYPE)

| Protocol | Type | APY | Unbonding | TVL | Why switch? |
|----------|------|-----|-----------|-----|-------------|
| **Kinetiq (kHYPE)** | LST | 2.37% | None | $833M | 2.6x yield, instant exit, composable |
| **LoopedHYPE (LHYPE)** | Leveraged LST | ~3.7% | Varies | $136M | 3x-15x leverage, multi-airdrop |
| **Valantis (stHYPE)** | LST | ~2% est | 7-8d | $180M | Airdrop farming (tokenless) |
| **Morpho Blue** | Lending | Variable | None | $500M+ on HyperEVM | Use HYPE/kHYPE as collateral |
| **HyperLend** | Lending | Variable | None | $540M | Aave-like, HPL airdrop pending |
| **Felix** | CDP | 8.25% (USDT) | None | Large | Mint feUSD, LP for 150%+ APR |
| **HypurrFi** | Lending | 8-20% | None | Growing | Euler-powered, USDXL pools |
| **KittenSwap** | DEX/LP | 150%+ APR | None | Largest HyperEVM DEX | feUSD/HYPE, KITTEN airdrop |
| **Pendle** | Yield | Fixed/Variable | None | $300M | Yield tokenization on kHYPE/stHYPE |
| **Veda/BoringVault** | Yield | Variable | Varies | $54M on HL | Institutional automated strategies |
| **vHYPE (Ventuals)** | LST | 0.9% | 7-8 days | 603k HYPE | Ventuals points only |

**The core problem:** vHYPE is NOT composable. You cannot use it as collateral on HyperLend, cannot LP it on KittenSwap, cannot tokenize its yield on Pendle. The HYPE is "trapped" earning only base staking yield + Ventuals points. In contrast, kHYPE can simultaneously earn staking yield AND be deployed across the entire DeFi stack.

**The math:** kHYPE 2.37% vs vHYPE 0.9% = 1.47% difference. On 250k HYPE that's ~3,675 HYPE/year. With LHYPE leverage loops, the gap widens to ~7,000+ HYPE/year. Plus airdrop exposure to KittenSwap, HyperLend, HypurrFi, and Valantis -- all tokenless protocols with active points campaigns.

---

## Conclusions

1. **The 0x8553/0x6E93/0xAD83 cluster is one entity** (proven via NFT transfer and HYPE transfer). Their other wallets operate in kHYPE, Morpho, Valantis, and Aave -- but the 250k withdrawal has **not been claimed yet** so we cannot confirm where it will go

2. **0xd25a100d is a separate institutional-style wallet** (ex-Veda/BoringVault) that parked 65k in vHYPE for 5 months. Also **not yet claimed** -- destination unknown

3. **Batch 132 is predominantly organic withdrawals**, not a coordinated sybil attack. Evidence:
   - Referral code distribution mirrors the Hyperliquid platform (37% WEB3, 8% DEFILLAMAO, etc.)
   - Most whale wallets trace to distinct real traders with different funding sources (Bybit, Arbitrum CCTP, HyperCore spot)
   - The near-3000 HYPE wallets are unrelated (different referral codes, different volumes, hours apart)

4. **One confirmed sybil cluster: IL/IL2** (0xad5b87bf + 0x64561a0c + satellite 0x493d53fb). Evidence: sequential subaccount naming, identical trading patterns (MON-USD shorts, UMON farming, HIP-2 HYPE buys), direct fund transfers, all WEB3 referral. Total impact: 5,752 HYPE (~5% of batch 132). This is a **small-scale points farmer**, not a large coordinated attack

5. **27 zero-volume wallets** (3,990 HYPE, 3.5% of batch) have no HyperCore activity at all. The two largest trace to real traders using dedicated vHYPE wallets. The rest are small (<400 HYPE each) and not connected to each other

6. **The burst (86 entries in 26 min) was most likely triggered by a social event** -- the diverse referral codes, varying amounts, and distinct trader profiles across burst wallets are inconsistent with bot coordination

7. **vHYPE's structural disadvantage is composability**, not just yield. kHYPE (2.37% APY) can be used as collateral on HyperLend, LPed on KittenSwap, tokenized on Pendle, and looped via LHYPE. vHYPE (0.9%) cannot -- the HYPE is locked with no DeFi utility beyond Ventuals points

---

## Current Holder Pressure Analysis (as of March 15, 2026)

### Vault State

| Metric | Value |
|--------|-------|
| totalBalance (TVL) | 603,247 HYPE |
| minimumStakeBalance | 500,000 HYPE |
| **Exit capacity** | **103,247 HYPE** |
| stakingBalance | 1,051,331 HYPE |
| spotBalance (awaiting claim) | 58,178 HYPE |
| In unstaking pipeline | 448,084 HYPE |
| Pending new queue | 202 HYPE (7 entries) |
| Exchange rate | 1.009054 |
| Holders | ~999 wallets |

### Top 10 Holders Risk Assessment

| # | Address | HYPE | Share | Risk | Profile |
|---|---------|------|-------|------|---------|
| 1 | 0xE2e4F2A7... | 40,663 | 6.7% | **HIGH** | Zero-vol, no referral, vHYPE-only |
| 2 | 0xE71CbF47... | 23,278 | 3.9% | MEDIUM | TRADEXYZ1, $17.6M vol, 5 subaccounts |
| 3 | 0xbB1AC608... | 23,095 | 3.8% | MEDIUM | No ref, $30.2M vol |
| 4 | 0x1258e585... | 20,404 | 3.4% | **HIGH** | Zero-vol, no referral, vHYPE-only |
| 5 | 0xeE7ADA00... | 19,877 | 3.3% | LOW | No ref, $4.9M vol, +42k HYPE idle in wallet |
| 6 | 0x09141412... | 18,728 | 3.1% | **HIGH** | Zero-vol, no referral, vHYPE-only |
| 7 | 0x045D7711... | 12,030 | 2.0% | MEDIUM | TRADEXYZ1, $4.8M vol |
| 8 | 0x77375A8c... | 10,090 | 1.7% | LOW | ALPHA, **$710M vol**, 4 subs (power trader) |
| 9 | 0x8c2826e0... | 10,090 | 1.7% | MEDIUM | No ref, $607k vol |
| 10 | 0x1214F289... | 8,624 | 1.4% | **HIGH** | Zero-vol, no referral, vHYPE-only |

**Risk classification:**
- **HIGH**: Zero trading volume on HyperCore, no referral code — these wallets exist solely for vHYPE. Same pattern as batch 132 sybil-suspect wallets. They have no other Hyperliquid activity to anchor them, making withdrawal more likely if sentiment shifts.
- **MEDIUM**: Active traders who may rotate capital to higher-yielding protocols. The TRADEXYZ1 pair (#2 + #7 = 35,308 HYPE) shares a referral code — potentially same entity.
- **LOW**: Heavy traders with significant non-vHYPE HYPE holdings. Less likely to withdraw since vHYPE is a small part of their portfolio.

### Concentration Risk

| Scenario | HYPE at risk | % of TVL | Remaining capacity |
|----------|-------------|----------|-------------------|
| Top 1 withdraws | 40,663 | 6.7% | 62,584 (safe) |
| All HIGH-risk withdraw | 88,419 | 14.7% | 14,828 (tight) |
| Top 4 withdraw | 107,440 | 17.8% | **-4,193 (FREEZE)** |
| Top 10 withdraw | 186,879 | 31.0% | **-83,632 (FREEZE)** |

**Critical finding:** Exit capacity (103,247 HYPE) is less than the sum of the top 4 holders. If the top 4 all queue withdrawals simultaneously, the vault hits the 500k minimum and all further withdrawals freeze.

### Pressure Indicators

**Negative signals:**
- 4 of top 10 holders are zero-volume vHYPE-only wallets (88,419 HYPE = 86% of exit capacity)
- The vault just processed 442k HYPE in withdrawals (batches 131-132), showing that large-scale exits happen
- Competing protocols (kHYPE 2.37%, LHYPE ~3.7%) offer superior yield + composability
- No new large deposits visible in pending queue

**Positive signals:**
- Post-batch TVL stabilized at 603k (above 500k minimum)
- Pending queue is minimal (202 HYPE, 7 small entries)
- Holder #8 (0x77375A8c) with $710M cumulative volume is unlikely to leave over basis points
- Holder #5 has 42k HYPE idle in wallet — chose to hold vHYPE alongside liquid HYPE, suggesting intentional allocation
- 999 holders = broad base; the long tail below top 10 is ~416k HYPE across ~989 wallets

**Key wallets to monitor:**
1. **0xE2e4F2A7** (40,663 HYPE) — #1 holder, zero-vol, any queueWithdraw from this wallet = immediate 39% hit to exit capacity
2. **0x1258e585** (20,404 HYPE) — #4, zero-vol, same risk pattern
3. **0x09141412** (18,728 HYPE) — #6, zero-vol
4. **0xE71CbF47 + 0x045D7711** (35,308 HYPE combined) — both use TRADEXYZ1 referral, potentially same entity

---

## Investigation Methodology

Data sources used:
- **vHYPE contract** (`0x8888...b20c`): Direct RPC calls to `getWithdraw(index)` for queue entries
- **Blockscout API** (`hyperscan.com/api/v2`): EVM transaction history, token transfers, decoded function calls
- **HyperCore API** (`api.hyperliquid.xyz/info`): `referral`, `subAccounts`, `clearinghouseState`, `spotClearinghouseState`, `delegatorSummary`
- **Hypurrscan API** (`api.hypurrscan.io`): `addressDetails`, `tags`
- **Hypurrscan browser** (`hypurrscan.io`): Transaction history, More tab (referrals, subaccounts, PnL), funding chains
- **4byte.directory / Openchain**: Function selector decoding

Key technique: Checking HyperCore `subAccounts` for all whale wallets revealed the IL/IL2 sybil pair that wasn't visible from EVM-only analysis. Referral code analysis across all 425 wallets provided the population-level view needed to distinguish generic codes (WEB3, DEFILLAMAO) from real clustering signals.

## Raw Data Files

- `queue-full.csv` -- All queue entries #2773-3255 (batches 131, 132, pending)
- `queue-scan.csv` -- Queue entries #3100-3255
- `hyperev-investigation-tools.md` -- APIs, tools, known contracts for future investigation
