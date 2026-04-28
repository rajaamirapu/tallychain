# TallyChain

Blockchain-powered double-entry accounting system with a Python desktop UI (tkinter) and a REST API (FastAPI). Designed for Indian businesses with built-in GST support, but flexible enough for any tax regime.

## Features

- **Chart of Accounts** -- pre-seeded with 25+ standard accounts (Assets, Liabilities, Equity, Income, Expense, Bank, Tax)
- **Double-Entry Vouchers** -- Payment, Receipt, Journal, Sales, Purchase, Contra, Debit/Credit Notes
- **GST Invoicing** -- Sales & Purchase invoices with CGST/SGST/IGST breakdowns, HSN/SAC codes
- **Financial Reports** -- Trial Balance, Profit & Loss, Balance Sheet, Cash Flow, Day Book, Outstanding Receivables/Payables (all with Print support)
- **Blockchain Audit Trail** -- every posted voucher is chained into an immutable ledger with SHA-256 hashes
- **Role-Based Access** -- Admin, Accountant, Auditor, Viewer roles with granular permissions
- **Taxation Module** -- manage GST/tax rates, view tax summaries
- **Bank Reconciliation** -- import bank statements and match against vouchers
- **REST API** -- full FastAPI backend with JWT authentication

## Requirements

- Python 3.10+
- tkinter (included with most Python installations; on Ubuntu: `sudo apt install python3-tk`)

## Installation

```bash
git clone https://github.com/rajaamirapu/tallychain.git
cd tallychain
pip install -r requirements.txt
```

## Quick Start

### Desktop Application

```bash
python app.py
```

This opens the login window. Use the default credentials:

| Username | Password    | Role  |
|----------|-------------|-------|
| `admin`  | `Admin@123` | Admin |

On first launch the app automatically seeds:
- Default chart of accounts (25+ accounts)
- Standard GST tax rates
- Admin user

### REST API

```bash
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Usage Guide

### 1. Setting Up Company Profile

Navigate to **Admin** (sidebar) and configure your company:
- Company name, GSTIN, PAN, address
- Fiscal year start (default: April 1)
- Currency and tax regime (GST / GAAP / Generic)

### 2. Chart of Accounts

Navigate to **Accounts** from the sidebar.

The system comes pre-seeded with a standard chart of accounts:

| Code Range | Category          | Examples                         |
|------------|-------------------|----------------------------------|
| 1001-1400  | Assets            | Cash in Hand, Bank Account, Stock, Fixed Assets |
| 2000-2400  | Liabilities       | Sundry Creditors, Loans, GST/TDS Payable |
| 3000-3100  | Equity            | Capital Account, Retained Earnings |
| 4000-4200  | Income            | Sales, Service Income, Other Income |
| 5000-5500  | Expenses          | Purchase, Salaries, Rent, Depreciation |

**Creating an account:**
1. Click **+ New Account**
2. Fill in Account Code, Name, Type, Opening Balance, and Balance Type (Dr/Cr)
3. Optionally add GSTIN for party accounts
4. Click **Create Account**

**Editing an account:**
1. Select an account in the table and click **Edit Account**, or double-click the row
2. Modify any field (code, name, type, balance, GSTIN, active status)
3. Click **Save Changes**

**Viewing a ledger:**
1. Select an account and click **View Ledger**
2. The ledger shows all transactions with running balance

### 3. Recording Vouchers (Journal Entries)

Navigate to **Vouchers** from the sidebar.

Every financial transaction is recorded as a voucher with debit and credit lines that must balance (double-entry).

**Creating a voucher:**
1. Click **+ New Voucher**
2. Select the voucher type:
   - **Payment** -- money going out (e.g., paying rent)
   - **Receipt** -- money coming in (e.g., customer payment)
   - **Journal** -- general adjustments
   - **Sales** -- recording a sale
   - **Purchase** -- recording a purchase
   - **Contra** -- transfers between cash/bank accounts
3. Enter the date, narration, and line items
4. Each line must specify an account, debit amount, or credit amount
5. **Total debits must equal total credits** -- the system enforces this

**Example -- Recording a sale of Rs 10,000:**
- Line 1: Debit *Sundry Debtors* (1100) -- Rs 10,000
- Line 2: Credit *Sales* (4000) -- Rs 10,000

**Example -- Recording rent payment of Rs 5,000:**
- Line 1: Debit *Rent* (5400) -- Rs 5,000
- Line 2: Credit *Bank Account* (1002) -- Rs 5,000

### 4. How to Balance the Balance Sheet

The Balance Sheet is automatically generated from your chart of accounts. To ensure it balances:

#### Step 1: Enter Opening Balances

When creating accounts, set the correct **opening balance** and **balance type** (Dr or Cr):
- Assets: Opening balance is typically **Dr** (debit)
- Liabilities: Opening balance is typically **Cr** (credit)
- Equity: Opening balance is typically **Cr** (credit)

The accounting equation must hold: **Assets = Liabilities + Equity**

#### Step 2: Record All Transactions as Balanced Vouchers

Every voucher must have equal debits and credits. The system enforces this, so your books stay balanced automatically. For example:

| Transaction              | Debit Account    | Credit Account     | Amount   |
|--------------------------|------------------|--------------------|----------|
| Capital invested         | Bank Account     | Capital Account    | 5,00,000 |
| Purchased goods          | Purchase         | Sundry Creditors   | 1,00,000 |
| Made a sale              | Sundry Debtors   | Sales              | 2,00,000 |
| Paid rent                | Rent             | Bank Account       | 25,000   |
| Received payment         | Bank Account     | Sundry Debtors     | 1,50,000 |
| Paid supplier            | Sundry Creditors | Bank Account       | 80,000   |

#### Step 3: Generate and Verify the Balance Sheet

1. Go to **Reports** > **Balance Sheet** tab
2. Set the "As on" date
3. Click **Generate**

The report shows:
- **Assets** section with individual balances and total
- **Liabilities & Equity** section with individual balances and total
- **Status**: "BALANCED" (Assets = Liabilities + Equity) or "UNBALANCED"

If the balance sheet is unbalanced:
- Check the **Trial Balance** (Reports > Trial Balance) -- total debits should equal total credits
- Look for unbalanced voucher entries in the **Day Book**
- Verify opening balances are correctly set (Dr vs Cr)

#### Step 4: Print Reports

Click the **Print** button next to any report to open the browser's print dialog. You can print to paper or save as PDF.

### 5. Creating Invoices

Navigate to **Invoices** from the sidebar.

1. Click **+ New Invoice**
2. Select invoice type (Sales, Purchase, Credit Note, Debit Note)
3. Choose the party (customer/supplier) account
4. Add line items with description, HSN/SAC code, quantity, rate, and tax rate
5. The system auto-calculates CGST, SGST, IGST based on the place of supply
6. Click **Create Invoice** -- this also generates the corresponding journal voucher

### 6. Financial Reports

Navigate to **Reports** from the sidebar. Six reports are available:

| Report            | Purpose                                           |
|-------------------|---------------------------------------------------|
| Trial Balance     | Verify that total debits = total credits           |
| Profit & Loss     | Income minus expenses for a period                 |
| Balance Sheet     | Assets vs Liabilities + Equity at a point in time  |
| Cash Flow         | Operating, investing, and financing cash movements |
| Day Book          | Chronological list of all transactions             |
| Outstanding       | Receivables and payables with aging                |

For each report:
1. Set the date range (or "as on" date)
2. Click **Generate** to view the report
3. Click **Print** to open the browser print dialog

### 7. Taxation (GST)

Navigate to **Taxation** from the sidebar.

- View and manage GST rates (CGST, SGST, IGST)
- View tax summary reports for filing

### 8. Blockchain Verification

Navigate to **Blockchain** from the sidebar.

Every posted voucher is recorded in an immutable blockchain. Each block contains:
- The voucher data
- A SHA-256 hash
- The previous block's hash

Use the blockchain panel to verify the integrity of your accounting records.

### 9. Audit Trail

Navigate to **Audit** from the sidebar.

Every action (create, update, delete, login) is logged with:
- Timestamp, user, action type
- Before/after snapshots for data changes
- Status (success/failure)

## User Roles & Permissions

| Role       | Accounts | Vouchers | Invoices | Reports | Tax | Blockchain | Audit | Admin |
|------------|----------|----------|----------|---------|-----|------------|-------|-------|
| Admin      | Full     | Full     | Full     | Full    | Full| Full       | Full  | Full  |
| Accountant | Full     | Full     | Full     | Full    | Full| Read       | --    | --    |
| Auditor    | Read     | Read     | Read     | Full    | Read| Full       | Full  | --    |
| Viewer     | Read     | Read     | Read     | Read    | Read| --         | --    | --    |

## API Endpoints

| Method | Endpoint                         | Description              |
|--------|----------------------------------|--------------------------|
| POST   | `/api/auth/register`             | Register a new user      |
| POST   | `/api/auth/login`                | Login (returns JWT token)|
| GET    | `/api/accounts`                  | List all accounts        |
| POST   | `/api/accounts`                  | Create an account        |
| PUT    | `/api/accounts/{id}`             | Update an account        |
| GET    | `/api/accounts/{id}/balance`     | Get account balance      |
| GET    | `/api/accounts/{id}/ledger`      | Get ledger statement     |
| POST   | `/api/vouchers`                  | Create a voucher         |
| GET    | `/api/vouchers`                  | List vouchers            |
| POST   | `/api/invoices`                  | Create an invoice        |
| GET    | `/api/invoices`                  | List invoices            |
| GET    | `/api/blockchain`                | View blockchain          |
| POST   | `/api/blockchain/verify`         | Verify blockchain        |

All API endpoints (except auth) require a JWT token in the `Authorization: Bearer <token>` header.

## Project Structure

```
tallychain/
  app.py              # Desktop UI entry point
  main.py             # FastAPI REST API entry point
  requirements.txt    # Python dependencies
  auth/               # Authentication & RBAC
  database/           # DB engine & Pydantic models
  modules/            # Business logic (ledger, invoicing, reporting, taxation)
  ui/                 # Tkinter UI panels
  audit/              # Audit trail module
  blockchain/         # Blockchain implementation
```

## License

See repository for license details.
