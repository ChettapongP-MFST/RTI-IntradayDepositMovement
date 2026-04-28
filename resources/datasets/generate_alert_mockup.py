"""
Generate mock deposit movement CSVs for 4 dates (2026-04-27 to 2026-04-30).
Each date hits ALL 3 alert tiers within a single intraday:
  🟡 Low   ≤ -5,000 M Baht  (cumulative)
  🟠 Medium ≤ -10,000 M Baht
  🔴 High   ≤ -15,000 M Baht

Each CSV = 24 rows (3 Products × 4 Channels × 2 Transaction Types).
48 CSVs per date = 48 half-hour slots (00:00-24:00).
"""

import csv, os, random, math

random.seed(42)

# ── Configuration ────────────────────────────────────
OUT_DIR = "extra-mock-up"

TIME_SLOTS = [
    f"{h:02d}:{m:02d}-{(h + (m+30)//60):02d}:{(m+30)%60:02d}"
    for h in range(24) for m in (0, 30)
]
# Fix the last slot: "23:30-24:00" not "23:30-00:00"
TIME_SLOTS[-1] = "23:30-24:00"

PRODUCTS = ["Fixed", "Saving", "Current"]
CHANNELS = [
    ("ATM",  "Offline"),
    ("BCMS", "Online"),
    ("ENET", "Online"),
    ("TELL", "Offline"),
]
TXN_TYPES = ["On-Us", "Off-Us"]

# 24 dimension combos per slot
COMBOS = [
    (prod, ch, cg, tt)
    for prod in PRODUCTS
    for ch, cg in CHANNELS
    for tt in TXN_TYPES
]

# ── Alert tier design ────────────────────────────────
# Each date: dict mapping slot_index → target cumulative net (in M Baht).
# Between anchor points, we linearly interpolate the per-slot net contribution.
# Final slot has some extra decline to end around -16,000 to -17,000M.

DATE_CONFIGS = {
    "2026-04-27": {
        # Low @ 10:00 (slot 20), Medium @ 14:30 (slot 29), High @ 19:00 (slot 38)
        "anchors": [
            (0,   0),
            (10, -1500),      # mild overnight
            (20, -5100),      # 🟡 Low breached at slot 20 = 10:00-10:30
            (29, -10200),     # 🟠 Medium breached at slot 29 = 14:30-15:00
            (38, -15300),     # 🔴 High breached at slot 38 = 19:00-19:30
            (47, -16500),     # taper off
        ],
    },
    "2026-04-28": {
        # Low @ 09:30 (slot 19), Medium @ 13:00 (slot 26), High @ 17:30 (slot 35)
        "anchors": [
            (0,   0),
            (10, -1800),
            (19, -5200),      # 🟡 Low
            (26, -10100),     # 🟠 Medium
            (35, -15400),     # 🔴 High
            (47, -17000),
        ],
    },
    "2026-04-29": {
        # Low @ 11:00 (slot 22), Medium @ 15:30 (slot 31), High @ 20:30 (slot 41)
        "anchors": [
            (0,   0),
            (12, -1200),
            (22, -5300),      # 🟡 Low
            (31, -10400),     # 🟠 Medium
            (41, -15200),     # 🔴 High
            (47, -16800),
        ],
    },
    "2026-04-30": {
        # Low @ 08:30 (slot 17), Medium @ 12:00 (slot 24), High @ 16:00 (slot 32)
        "anchors": [
            (0,   0),
            (8,  -1000),
            (17, -5400),      # 🟡 Low
            (24, -10300),     # 🟠 Medium
            (32, -15100),     # 🔴 High
            (47, -17200),
        ],
    },
}


def interpolate_cumulative(anchors, n_slots=48):
    """Build a list of 48 cumulative values (M Baht) from anchor points."""
    cum = [0.0] * n_slots
    for i in range(len(anchors) - 1):
        s0, c0 = anchors[i]
        s1, c1 = anchors[i + 1]
        for s in range(s0, s1 + 1):
            frac = (s - s0) / (s1 - s0) if s1 != s0 else 1.0
            cum[s] = c0 + frac * (c1 - c0)
    return cum


def cum_to_slot_nets(cum):
    """Convert cumulative list to per-slot net (M Baht)."""
    nets = [cum[0]]
    for i in range(1, len(cum)):
        nets.append(cum[i] - cum[i - 1])
    return nets


def generate_rows_for_slot(date_str, time_label, target_net_m):
    """
    Generate 24 rows for one time slot.
    target_net_m = desired net in M Baht for this slot.
    Returns list of dicts.
    """
    target_net_baht = target_net_m * 1_000_000  # convert M → Baht
    n = len(COMBOS)  # 24

    # Distribute target net across 24 rows with some randomness
    # Base allocation per row
    base_net = target_net_baht / n
    # Add noise: ±40% variation
    raw_nets = [base_net * (1 + random.uniform(-0.4, 0.4)) for _ in range(n)]
    # Scale to match target exactly
    raw_sum = sum(raw_nets)
    if abs(raw_sum) > 0:
        scale = target_net_baht / raw_sum
        row_nets = [r * scale for r in raw_nets]
    else:
        row_nets = [target_net_baht / n] * n

    rows = []
    for idx, (prod, ch, cg, tt) in enumerate(COMBOS):
        net = round(row_nets[idx])
        # Generate credit and debit that produce this net
        # Base credit: random realistic value (200M - 800M Baht range)
        credit = round(random.uniform(200_000_000, 800_000_000))
        debit = credit - net  # so net = credit - debit

        # Ensure debit is positive; if not, adjust
        if debit < 0:
            credit = abs(net) + round(random.uniform(50_000_000, 200_000_000))
            debit = credit - net

        # Transaction counts
        credit_txn = random.randint(800, 5000)
        debit_txn = random.randint(800, 5000)
        total_txn = credit_txn + debit_txn

        rows.append({
            "Date": date_str,
            "Time": time_label,
            "Product": prod,
            "Channel": ch,
            "Channel_Group": cg,
            "Transaction_Type": tt,
            "Credit_Amount": credit,
            "Debit_Amount": debit,
            "Net_Amount": credit - debit,  # recalculate to ensure consistency
            "Credit_Txn": credit_txn,
            "Debit_Txn": debit_txn,
            "Total_Txn": total_txn,
        })

    return rows


def slot_index_to_file_times(idx):
    """Slot index → (HHMM_start, HHMM_end) for filename."""
    h = idx // 2
    m = (idx % 2) * 30
    h2 = h + (m + 30) // 60
    m2 = (m + 30) % 60
    if h2 == 24:
        return f"{h:02d}{m:02d}", "2400"
    return f"{h:02d}{m:02d}", f"{h2:02d}{m2:02d}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for date_str, cfg in DATE_CONFIGS.items():
        date_prefix = date_str.replace("-", "_")
        anchors = cfg["anchors"]
        cum = interpolate_cumulative(anchors)
        slot_nets = cum_to_slot_nets(cum)

        # Track actual cumulative for verification
        actual_cum = 0
        print(f"\n{'='*70}")
        print(f"  {date_str}  —  Alert Timeline")
        print(f"{'='*70}")
        print(f"  {'Slot':<6} {'Time':<14} {'Slot Net (M)':>14} {'Cum Net (M)':>14}  Alert")
        print(f"  {'-'*6} {'-'*14} {'-'*14} {'-'*14}  {'-'*20}")

        for i in range(48):
            t_start, t_end = slot_index_to_file_times(i)
            time_label = TIME_SLOTS[i]
            target_net_m = slot_nets[i]

            rows = generate_rows_for_slot(date_str, time_label, target_net_m)

            # Write CSV
            fname = f"{date_prefix}_mock_{t_start}_{t_end}.csv"
            fpath = os.path.join(OUT_DIR, fname)
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "Date", "Time", "Product", "Channel", "Channel_Group",
                    "Transaction_Type", "Credit_Amount", "Debit_Amount",
                    "Net_Amount", "Credit_Txn", "Debit_Txn", "Total_Txn",
                ])
                writer.writeheader()
                writer.writerows(rows)

            # Actual net for this slot
            slot_actual = sum(r["Net_Amount"] for r in rows)
            actual_cum += slot_actual
            actual_cum_m = actual_cum / 1_000_000

            # Alert status
            if actual_cum_m <= -15000:
                alert = "🔴 HIGH"
            elif actual_cum_m <= -10000:
                alert = "🟠 MEDIUM"
            elif actual_cum_m <= -5000:
                alert = "🟡 LOW"
            else:
                alert = "✅ Normal"

            # Print key slots
            is_breach = (
                (i > 0 and actual_cum_m <= -5000 and (actual_cum - slot_actual) / 1_000_000 > -5000) or
                (i > 0 and actual_cum_m <= -10000 and (actual_cum - slot_actual) / 1_000_000 > -10000) or
                (i > 0 and actual_cum_m <= -15000 and (actual_cum - slot_actual) / 1_000_000 > -15000)
            )
            marker = " ◄◄◄ BREACH" if is_breach else ""
            if is_breach or i % 4 == 0 or i == 47:
                print(f"  {i:<6} {time_label:<14} {slot_actual/1_000_000:>14,.1f} {actual_cum_m:>14,.1f}  {alert}{marker}")

        print(f"\n  Final cumulative: {actual_cum/1_000_000:,.1f} M Baht")
        print(f"  Files generated: 48")

    print(f"\n✅ Done — {4 * 48} CSV files written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
