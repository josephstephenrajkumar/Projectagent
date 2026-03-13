# OpenClaw SQL Database Schema

This document outlines the SQLite database structure used in the OpenClaw project. The database is stored at `./data/openclaw.db` by default.

## Tables

### 1. `Project`
The core table containing project metadata and financial totals.

| Column | Type | Description |
| :--- | :--- | :--- |
| `project_id` | TEXT (PK) | Unique identifier (UUID). |
| `ProjectNumber` | TEXT | Unique internal project code. |
| `OpportunityID` | TEXT | Linked CRM/Contract ID. |
| `customer` | VARCHAR(200) | Customer name. |
| `end_customer` | VARCHAR(200) | End customer name. |
| `PMName` | VARCHAR(200) | Project Manager name. |
| `DMName` | VARCHAR(200) | Delivery Manager name. |
| ... | ... | (Other metadata fields: country, dates, currencies) |
| `sow_json` | TEXT | JSON blob of Statement of Work details. |
| `resources_json` | TEXT | JSON blob of resource allocations. |
| `total_project_cost` | FLOAT | Total calculated cost. |

### 2. `ProjectWorkPackage`
Contains details of specific phases/work packages linked to a project.

| Column | Type | Description |
| :--- | :--- | :--- |
| `wp_id` | TEXT (PK) | Unique identifier. |
| `project_id` | TEXT (FK) | Reference to `Project.project_id`. |
| `phase_name` | TEXT | Name of the work package phase. |
| `scope` | TEXT | Detailed scope text. |
| `deliverables` | TEXT | List of deliverables. |
| ... | ... | (Other phase-specific text fields) |

### 3. `ProjectWeeklySummary`
Tracks weekly health and status updates.

| Column | Type | Description |
| :--- | :--- | :--- |
| `WeeklyID` | TEXT (PK) | Unique identifier. |
| `project_id` | TEXT (FK) | Reference to `Project.project_id`. |
| `date` | DATETIME | Reporting date. |
| `overallStatus` | VARCHAR(25) | Green/Amber/Red status. |
| `FinancialPerformance`| VARCHAR(25) | Financial health indicator. |

### 4. `RAIDitems`
RAID (Risks, Assumptions, Issues, Dependencies) log.

| Column | Type | Description |
| :--- | :--- | :--- |
| `raidID` | TEXT (PK) | Unique identifier. |
| `project_id` | TEXT (FK) | Reference to `Project.project_id`. |
| `Type` | VARCHAR(50) | Risk, Issue, etc. |
| `Description` | TEXT | Full description. |
| `DueDate` | DATETIME | Target resolution date. |
| `Status` | VARCHAR(25) | Open, Closed, etc. |

### 5. `MBRitems`
Management Business Review (MBR) forecast items.

| Column | Type | Description |
| :--- | :--- | :--- |
| `mbr_id` | TEXT (PK) | Unique identifier. |
| `project_id` | TEXT (FK) | Reference to `Project.project_id`. |
| `ForecastAmount` | FLOAT | Forecasted revenue/cost. |
| `ForecastDateMonth` | DATETIME | Target month. |

## Relationships
- All tables (`ProjectWorkPackage`, `ProjectWeeklySummary`, `RAIDitems`, `MBRitems`) have a **Many-to-One** relationship with `Project` via the `project_id` foreign key.
