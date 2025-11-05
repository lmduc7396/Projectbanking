# Azure SQL Database Schema

_Generated: 2025-11-05T07:24:34Z_

**Server:** `sqls-dclab.database.windows.net`
**Database:** `dclab`

---

## `Banking_Comments`

- **Row Count:** 338
- **Primary Key:** _None detected_

| # | Column | Type | Length/Precision | Nullable | Default |
|---|--------|------|------------------|----------|---------|
| 1 | `TICKER` | nvarchar | 50 | YES | — |
| 2 | `SECTOR` | nvarchar | 50 | YES | — |
| 3 | `DATE` | nvarchar | 50 | YES | — |
| 4 | `COMMENT` | nvarchar | -1 | YES | — |

---

## `Banking_Drivers`

- **Row Count:** 1244
- **Primary Key:** _None detected_

| # | Column | Type | Length/Precision | Nullable | Default |
|---|--------|------|------------------|----------|---------|
| 1 | `TICKER` | nvarchar | 50 | YES | — |
| 2 | `Type` | nvarchar | 50 | YES | — |
| 3 | `DATE` | nvarchar | 50 | YES | — |
| 4 | `TOI` | nvarchar | 50 | YES | — |
| 5 | `Net Interest Income` | nvarchar | 50 | YES | — |
| 6 | `Fees Income` | nvarchar | 50 | YES | — |
| 7 | `OPEX` | nvarchar | 50 | YES | — |
| 8 | `Provision expense` | nvarchar | 50 | YES | — |
| 9 | `PBT` | nvarchar | 50 | YES | — |
| 10 | `Loan` | nvarchar | 50 | YES | — |
| 11 | `NIM` | nvarchar | 50 | YES | — |
| 12 | `Core TOI` | nvarchar | 50 | YES | — |
| 13 | `Core PBT` | nvarchar | 50 | YES | — |
| 14 | `Non-recurring income` | nvarchar | 50 | YES | — |
| 15 | `Core TOI_T12M` | nvarchar | 50 | YES | — |
| 16 | `PBT_T12M` | nvarchar | 50 | YES | — |
| 17 | `OPEX_T12M` | nvarchar | 50 | YES | — |
| 18 | `Provision expense_T12M` | nvarchar | 50 | YES | — |
| 19 | `Non-recurring income_T12M` | nvarchar | 50 | YES | — |
| 20 | `Net Interest Income_T12M` | nvarchar | 50 | YES | — |
| 21 | `Fees Income_T12M` | nvarchar | 50 | YES | — |
| 22 | `Loan_T12M` | nvarchar | 50 | YES | — |
| 23 | `NIM_T12M` | nvarchar | 50 | YES | — |
| 24 | `Core_TOI_Change` | nvarchar | 50 | YES | — |
| 25 | `PBT_Change` | nvarchar | 50 | YES | — |
| 26 | `OPEX_Change` | nvarchar | 50 | YES | — |
| 27 | `Provision_Change` | nvarchar | 50 | YES | — |
| 28 | `Non_Recurring_Change` | nvarchar | 50 | YES | — |
| 29 | `NII_Change` | nvarchar | 50 | YES | — |
| 30 | `Fee_Change` | nvarchar | 50 | YES | — |
| 31 | `Loan_Growth_%` | nvarchar | 50 | YES | — |
| 32 | `Small_PBT_Flag` | bit | — | YES | — |
| 33 | `PBT_Growth_%_T12M` | nvarchar | 50 | YES | — |
| 34 | `Top_Line_Impact_T12M` | nvarchar | 50 | YES | — |
| 35 | `Cost_Cutting_Impact_T12M` | nvarchar | 50 | YES | — |
| 36 | `Non_Recurring_Impact_T12M` | nvarchar | 50 | YES | — |
| 37 | `NII_Impact_T12M` | nvarchar | 50 | YES | — |
| 38 | `Fee_Impact_T12M` | nvarchar | 50 | YES | — |
| 39 | `OPEX_Impact_T12M` | nvarchar | 50 | YES | — |
| 40 | `Provision_Impact_T12M` | nvarchar | 50 | YES | — |
| 41 | `Loan_Impact_T12M` | nvarchar | 50 | YES | — |
| 42 | `NIM_Impact_T12M` | nvarchar | 50 | YES | — |
| 43 | `Total_Impact_T12M` | nvarchar | 50 | YES | — |
| 44 | `Top_Line_Impact` | nvarchar | 50 | YES | — |
| 45 | `Cost_Cutting_Impact` | nvarchar | 50 | YES | — |
| 46 | `Non_Recurring_Impact` | nvarchar | 50 | YES | — |
| 47 | `Total_Impact` | nvarchar | 50 | YES | — |
| 48 | `NII_Impact` | nvarchar | 50 | YES | — |
| 49 | `Fee_Impact` | nvarchar | 50 | YES | — |
| 50 | `OPEX_Impact` | nvarchar | 50 | YES | — |
| 51 | `Provision_Impact` | nvarchar | 50 | YES | — |
| 52 | `Loan_Impact` | nvarchar | 50 | YES | — |
| 53 | `NIM_Impact` | nvarchar | 50 | YES | — |
| 54 | `PBT_Growth_%` | nvarchar | 50 | YES | — |
| 55 | `Core TOI_QoQ` | nvarchar | 50 | YES | — |
| 56 | `PBT_QoQ` | nvarchar | 50 | YES | — |
| 57 | `OPEX_QoQ` | nvarchar | 50 | YES | — |
| 58 | `Provision expense_QoQ` | nvarchar | 50 | YES | — |
| 59 | `Non-recurring income_QoQ` | nvarchar | 50 | YES | — |
| 60 | `Net Interest Income_QoQ` | nvarchar | 50 | YES | — |
| 61 | `Fees Income_QoQ` | nvarchar | 50 | YES | — |
| 62 | `Loan_QoQ` | nvarchar | 50 | YES | — |
| 63 | `NIM_QoQ` | nvarchar | 50 | YES | — |
| 64 | `PBT_Growth_%_QoQ` | nvarchar | 50 | YES | — |
| 65 | `Top_Line_Impact_QoQ` | nvarchar | 50 | YES | — |
| 66 | `Cost_Cutting_Impact_QoQ` | nvarchar | 50 | YES | — |
| 67 | `Non_Recurring_Impact_QoQ` | nvarchar | 50 | YES | — |
| 68 | `NII_Impact_QoQ` | nvarchar | 50 | YES | — |
| 69 | `Fee_Impact_QoQ` | nvarchar | 50 | YES | — |
| 70 | `OPEX_Impact_QoQ` | nvarchar | 50 | YES | — |
| 71 | `Provision_Impact_QoQ` | nvarchar | 50 | YES | — |
| 72 | `Loan_Impact_QoQ` | nvarchar | 50 | YES | — |
| 73 | `NIM_Impact_QoQ` | nvarchar | 50 | YES | — |
| 74 | `Total_Impact_QoQ` | nvarchar | 50 | YES | — |
| 75 | `Core TOI_YoY` | nvarchar | 50 | YES | — |
| 76 | `PBT_YoY` | nvarchar | 50 | YES | — |
| 77 | `OPEX_YoY` | nvarchar | 50 | YES | — |
| 78 | `Provision expense_YoY` | nvarchar | 50 | YES | — |
| 79 | `Non-recurring income_YoY` | nvarchar | 50 | YES | — |
| 80 | `Net Interest Income_YoY` | nvarchar | 50 | YES | — |
| 81 | `Fees Income_YoY` | nvarchar | 50 | YES | — |
| 82 | `Loan_YoY` | nvarchar | 50 | YES | — |
| 83 | `NIM_YoY` | nvarchar | 50 | YES | — |
| 84 | `PBT_Growth_%_YoY` | nvarchar | 50 | YES | — |
| 85 | `Top_Line_Impact_YoY` | nvarchar | 50 | YES | — |
| 86 | `Cost_Cutting_Impact_YoY` | nvarchar | 50 | YES | — |
| 87 | `Non_Recurring_Impact_YoY` | nvarchar | 50 | YES | — |
| 88 | `NII_Impact_YoY` | nvarchar | 50 | YES | — |
| 89 | `Fee_Impact_YoY` | nvarchar | 50 | YES | — |
| 90 | `OPEX_Impact_YoY` | nvarchar | 50 | YES | — |
| 91 | `Provision_Impact_YoY` | nvarchar | 50 | YES | — |
| 92 | `Loan_Impact_YoY` | nvarchar | 50 | YES | — |
| 93 | `NIM_Impact_YoY` | nvarchar | 50 | YES | — |
| 94 | `Total_Impact_YoY` | nvarchar | 50 | YES | — |
| 95 | `Impacts_Capped` | nvarchar | 50 | YES | — |
| 96 | `PERIOD_TYPE` | nvarchar | 50 | YES | — |
| 97 | `Core TOI_Prior_Year` | nvarchar | 50 | YES | — |
| 98 | `PBT_Prior_Year` | nvarchar | 50 | YES | — |
| 99 | `OPEX_Prior_Year` | nvarchar | 50 | YES | — |
| 100 | `Provision expense_Prior_Year` | nvarchar | 50 | YES | — |
| 101 | `Non-recurring income_Prior_Year` | nvarchar | 50 | YES | — |
| 102 | `Net Interest Income_Prior_Year` | nvarchar | 50 | YES | — |
| 103 | `Fees Income_Prior_Year` | nvarchar | 50 | YES | — |
| 104 | `Loan_Prior_Year` | nvarchar | 50 | YES | — |
| 105 | `NIM_Prior_Year` | nvarchar | 50 | YES | — |
| 106 | `Scores_Capped` | nvarchar | 50 | YES | — |
| 107 | `_content_hash` | nvarchar | 50 | YES | — |

---

## `BankingMetrics`

- **Row Count:** 1290
- **Primary Key:** _None detected_

| # | Column | Type | Length/Precision | Nullable | Default |
|---|--------|------|------------------|----------|---------|
| 1 | `TICKER` | nvarchar | 50 | YES | — |
| 2 | `YEARREPORT` | bigint | 19,0 | YES | — |
| 3 | `LENGTHREPORT` | bigint | 19,0 | YES | — |
| 4 | `ACTUAL` | bit | — | YES | — |
| 5 | `DATE` | datetime2 | — | YES | — |
| 6 | `DATE_STRING` | nvarchar | 50 | YES | — |
| 7 | `BANK_TYPE` | nvarchar | 50 | YES | — |
| 8 | `PERIOD_TYPE` | nvarchar | 50 | YES | — |
| 9 | `TOI` | nvarchar | 50 | YES | — |
| 10 | `PBT` | nvarchar | 50 | YES | — |
| 11 | `Net Interest Income` | nvarchar | 50 | YES | — |
| 12 | `OPEX` | nvarchar | 50 | YES | — |
| 13 | `PPOP` | nvarchar | 50 | YES | — |
| 14 | `Provision expense` | nvarchar | 50 | YES | — |
| 15 | `NPATMI` | nvarchar | 50 | YES | — |
| 16 | `Fees Income` | nvarchar | 50 | YES | — |
| 17 | `Net Profit` | nvarchar | 50 | YES | — |
| 18 | `Loan` | nvarchar | 50 | YES | — |
| 19 | `Deposit` | nvarchar | 50 | YES | — |
| 20 | `Total Assets` | nvarchar | 50 | YES | — |
| 21 | `Total Equity` | nvarchar | 50 | YES | — |
| 22 | `Provision on Balance Sheet` | nvarchar | 50 | YES | — |
| 23 | `Write-off` | nvarchar | 50 | YES | — |
| 24 | `LDR` | nvarchar | 50 | YES | — |
| 25 | `CASA` | nvarchar | 50 | YES | — |
| 26 | `NPL` | nvarchar | 50 | YES | — |
| 27 | `ABS NPL` | nvarchar | 50 | YES | — |
| 28 | `GROUP 2` | nvarchar | 50 | YES | — |
| 29 | `CIR` | nvarchar | 50 | YES | — |
| 30 | `NPL Coverage ratio` | nvarchar | 50 | YES | — |
| 31 | `Total Credit Balance` | nvarchar | 50 | YES | — |
| 32 | `Provision/ Total Loan` | nvarchar | 50 | YES | — |
| 33 | `Leverage Multiple` | nvarchar | 50 | YES | — |
| 34 | `Interest Earnings Asset` | nvarchar | 50 | YES | — |
| 35 | `Interest Bearing Liabilities` | nvarchar | 50 | YES | — |
| 36 | `NIM` | nvarchar | 50 | YES | — |
| 37 | `Customer loans` | nvarchar | 50 | YES | — |
| 38 | `Loan yield` | nvarchar | 50 | YES | — |
| 39 | `ROA` | nvarchar | 50 | YES | — |
| 40 | `ROE` | nvarchar | 50 | YES | — |
| 41 | `Deposit balance` | nvarchar | 50 | YES | — |
| 42 | `Deposit yield` | nvarchar | 50 | YES | — |
| 43 | `Fees/ Total asset` | nvarchar | 50 | YES | — |
| 44 | `Individual %` | nvarchar | 50 | YES | — |
| 45 | `NPL Formation Amount` | nvarchar | 50 | YES | — |
| 46 | `New NPL` | nvarchar | 50 | YES | — |
| 47 | `Group 2 Formation` | nvarchar | 50 | YES | — |
| 48 | `New G2` | nvarchar | 50 | YES | — |
| 49 | `Overdue_loan` | nvarchar | 50 | YES | — |
| 50 | `_content_hash` | nvarchar | 50 | YES | — |

---
