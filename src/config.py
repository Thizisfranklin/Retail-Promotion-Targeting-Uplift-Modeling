from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hillstrom.csv"
DB = ROOT / "data" / "retail.db"
SEED = 42
CONTROL = "No E-Mail"
ARMS = {"Mens E-Mail": "Men's email", "Womens E-Mail": "Women's email"}
ARM_LABEL = {**ARMS, CONTROL: "No email (control)"}
URLS = [
    "https://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
    "https://hillstorm1.s3.us-east-2.amazonaws.com/hillstorm_no_indices.csv.gz",
]
# Pre-treatment features only. Outcomes (visit, conversion, spend) and arm are excluded.
NUM_FEATURES = ["recency", "history", "mens", "womens", "newbie"]
CAT_FEATURES = ["zip_code", "channel"]
OUTCOMES = ["visit", "conversion", "spend"]
