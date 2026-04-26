"""Generate extra mock-up data for 7 days (2026-04-27 to 2026-05-03), 24 hrs per day."""

import csv
import os
import random
from datetime import date, timedelta

# Seed for reproducibility
random.seed(42)

# Output folder
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "extra-mock-up")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Date range
START_DATE = date(2026, 4, 27)
END_DATE = date(2026, 5, 3)

# Dimensions (same cross-product as original)
PRODUCTS = ["Fixed", "Saving", "Current"]
CHANNELS = [
    ("ATM", "Offline"),
    ("BCMS", "Online"),
    ("ENET", "Online"),
    ("TELL", "Offline"),
]
TRANSACTION_TYPES = ["On-Us", "Off-Us"]

# 48 half-hour windows covering 24 hours
TIME_WINDOWS = []
for h in range(24):
    for m in (0, 30):
        start_h, start_m = h, m
        end_m = start_m + 30
        end_h = start_h
        if end_m == 60:
            end_m = 0
            end_h += 1
        label = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
        tag = f"{start_h:02d}{start_m:02d}_{end_h:02d}{end_m:02d}"
        TIME_WINDOWS.append((label, tag))

HEADER = [
    "Date", "Time", "Product", "Channel", "Channel_Group",
    "Transaction_Type", "Credit_Amount", "Debit_Amount", "Net_Amount",
    "Credit_Txn", "Debit_Txn", "Total_Txn",
]

file_count = 0
row_count = 0

current_date = START_DATE
while current_date <= END_DATE:
    date_str = current_date.isoformat()  # e.g. 2026-04-27

    for time_label, time_tag in TIME_WINDOWS:
        filename = f"mock_{time_tag}.csv"
        filepath = os.path.join(OUTPUT_DIR, date_str, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)

            for product in PRODUCTS:
                for channel, channel_group in CHANNELS:
                    for txn_type in TRANSACTION_TYPES:
                        credit_amount = random.randint(0, 1_010_000)
                        debit_amount = random.randint(0, 1_010_000)
                        net_amount = credit_amount - debit_amount
                        credit_txn = random.randint(12, 300)
                        debit_txn = random.randint(11, 300)
                        total_txn = credit_txn + debit_txn

                        writer.writerow([
                            date_str,
                            time_label,
                            product,
                            channel,
                            channel_group,
                            txn_type,
                            credit_amount,
                            debit_amount,
                            net_amount,
                            credit_txn,
                            debit_txn,
                            total_txn,
                        ])
                        row_count += 1

        file_count += 1

    current_date += timedelta(days=1)

print(f"Generated {file_count} files with {row_count} total rows in {OUTPUT_DIR}")
print(f"Date range: {START_DATE} to {END_DATE}")
print(f"Days: {(END_DATE - START_DATE).days + 1}")
print(f"Time windows per day: {len(TIME_WINDOWS)}")
print(f"Rows per file: {len(PRODUCTS) * len(CHANNELS) * len(TRANSACTION_TYPES)}")
