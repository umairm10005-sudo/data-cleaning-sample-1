"""Clean a messy customer CSV.

Usage:
    python clean_data.py messy_customers.csv cleaned_customers.csv

What it fixes: name casing/spaces, phone formats (+91, dashes, spaces), email
typos/case, mixed date formats, city spelling variants, currency symbols in
amounts, and duplicate customers. Rows that still have a missing/invalid phone
or email are kept but flagged in a `needs_review` column.
"""
import sys

import pandas as pd

CITY_MAP = {
    "mumbai": "Mumbai", "bombay": "Mumbai", "mum": "Mumbai",
    "pune": "Pune", "poona": "Pune",
    "thane": "Thane",
    "nagpur": "Nagpur",
    "nashik": "Nashik", "nasik": "Nashik",
}


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    report = {"rows_in": len(df)}

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Names: trim, collapse repeated spaces, Title Case
    df["name"] = (
        df["name"].astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    )

    # Phones: keep digits, take last 10 (drops +91 / 0 / 091), must look like an Indian mobile
    digits = df["phone"].astype("string").str.replace(r"\D", "", regex=True).str[-10:]
    valid_phone = digits.str.fullmatch(r"[6-9]\d{9}").fillna(False)
    report["invalid_or_missing_phone"] = int((~valid_phone).sum())
    df["phone"] = digits.where(valid_phone)

    # Emails: trim, lowercase, fix ',com' typo, blank out anything that isn't a valid address
    email = df["email"].astype("string").str.strip().str.lower().str.replace(",com", ".com", regex=False)
    valid_email = email.str.fullmatch(r"[\w.+-]+@[\w-]+\.[a-z.]+").fillna(False)
    report["invalid_or_missing_email"] = int((~valid_email).sum())
    df["email"] = email.where(valid_email)

    # Dates: parse mixed formats (day first), output ISO yyyy-mm-dd
    parsed = pd.to_datetime(
        df["signup_date"].astype("string").str.strip(), format="mixed", dayfirst=True, errors="coerce"
    )
    report["missing_dates"] = int(parsed.isna().sum())
    df["signup_date"] = parsed.dt.strftime("%Y-%m-%d")

    # City: standardise spelling variants
    c = df["city"].astype("string").str.strip().str.lower()
    df["city"] = c.map(CITY_MAP).fillna(c.str.title())

    # Amount: pull out the number from "Rs. 1,200.00", "1200/-", "₹1,200" etc.
    num = (
        df["amount"].astype("string").str.extract(r"(\d[\d,]*\.?\d*)")[0].str.replace(",", "", regex=False)
    )
    df["amount"] = pd.to_numeric(num, errors="coerce")
    report["missing_amounts"] = int(df["amount"].isna().sum())

    # Duplicates: same person after cleaning
    before = len(df)
    df = df.drop_duplicates(subset=["name", "phone", "email", "signup_date"], keep="first")
    report["duplicates_removed"] = before - len(df)

    df["needs_review"] = df["phone"].isna() | df["email"].isna()
    df = df.sort_values("name").reset_index(drop=True)
    report["rows_out"] = len(df)
    report["rows_needing_review"] = int(df["needs_review"].sum())
    return df, report


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    raw = pd.read_csv(src, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")
    cleaned, rep = clean(raw)
    cleaned.to_csv(dst, index=False, encoding="utf-8-sig")
    print("Cleaning report")
    for k, v in rep.items():
        print(f"  {k}: {v}")
