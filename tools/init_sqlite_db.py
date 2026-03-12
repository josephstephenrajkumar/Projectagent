import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

# We default to a sensible path if not provided
DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")


def create_database():
    """
    Initializes the SQLite database with the required normalized schema.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Connect (will create the file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Project Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Project (
        project_id TEXT PRIMARY KEY,
        ProjectNumber TEXT,
        OpportunityID TEXT,
        customer VARCHAR(200),
        end_customer VARCHAR(200),
        PMName VARCHAR(200),
        DMName VARCHAR(200),
        country VARCHAR(200),
        startdateContract DATETIME,
        endDateContract DATETIME,
        startdateBaseline DATETIME,
        endDateBaseline DATETIME,
        exchangerate VARCHAR(10),
        MBRReporting_currency VARCHAR(10),
        Proj_Stage VARCHAR(100),
        Prod_Grp VARCHAR(100),
        Portfolio VARCHAR(100),
        Contr_Type VARCHAR(100),
        Rev_Type VARCHAR(100),
        Region VARCHAR(100),
        CMT VARCHAR(100),
        Country_Group VARCHAR(100),
        Project_Owner VARCHAR(200),
        Delivery_Manager VARCHAR(200),
        Q2C_Ops VARCHAR(200),
        Start_Dt DATETIME,
        End_Date DATETIME,
        ActiveCurrency VARCHAR(10),
        Baseline_Rev INTEGER,
        Baseline_Cost INTEGER,
        SEGM_percent FLOAT,
        DEGM_percent FLOAT,
        EGM_variance_percent FLOAT,
        sow_json TEXT,
        resources_json TEXT,
        invoice_json TEXT,
        revenue_json TEXT,
        total_hours_json TEXT,
        total_project_cost FLOAT,
        travel_cost FLOAT,
        other_cost FLOAT
    );
    """)

    # 1b. ProjectWorkPackage Table (FK → Project)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProjectWorkPackage (
        wp_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_name TEXT NOT NULL,
        phase_order INTEGER,
        prerequisites TEXT,
        activities TEXT,
        customer_responsibilities TEXT,
        out_of_scope TEXT,
        risks_mitigations TEXT,
        deliverables TEXT,
        acceptance_criteria TEXT,
        FOREIGN KEY(project_id) REFERENCES Project(project_id)
    );
    """)

    # 2. ProjectWeeklySummary Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProjectWeeklySummary (
        WeeklyID TEXT PRIMARY KEY,
        project_id TEXT,
        date DATETIME,
        Summary VARCHAR(4000),
        overallStatus VARCHAR(25),
        CustomerSatisfaction VARCHAR(25),
        CustomerInteraction VARCHAR(25),
        DeliveryPerformance VARCHAR(25),
        LegalOrContract VARCHAR(25),
        FinancialPerformance VARCHAR(25),
        Resource VARCHAR(25),
        Schedule VARCHAR(25),
        ProductIssues VARCHAR(25),
        ITD_Revenue INTEGER,
        ITD_Cost INTEGER,
        Backlog_Rev INTEGER,
        ETC_Revenue INTEGER,
        ETC_Cost INTEGER,
        EAC_Revenue INTEGER,
        EAC_Cost INTEGER,
        FOREIGN KEY(project_id) REFERENCES Project(project_id)
    );
    """)

    # 3. RAIDitems Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS RAIDitems (
        raidID TEXT PRIMARY KEY,
        project_id TEXT,
        LastupdateDate DATETIME,
        Type VARCHAR(50),
        Category VARCHAR(50),
        owner VARCHAR(100),
        Description TEXT,
        MitigatingAction TEXT,
        DueDate DATETIME,
        ROAM VARCHAR(50),
        StartDate DATETIME,
        EndDate DATETIME,
        Status VARCHAR(25),
        Statusdate DATETIME,
        Status_summary TEXT,
        FOREIGN KEY(project_id) REFERENCES Project(project_id)
    );
    """)

    # 4. MBRitems Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MBRitems (
        mbr_id TEXT PRIMARY KEY,
        project_id TEXT,
        LastupdateDate DATETIME,
        Baseline VARCHAR(25),
        Baseline_date DATETIME,
        ForecastDateMonth DATETIME,
        ForecastAmount FLOAT,
        Status VARCHAR(25),
        FOREIGN KEY(project_id) REFERENCES Project(project_id)
    );
    """)

    conn.commit()
    conn.close()
    
    print(f"✅ SQLite database successfully initialized at {DB_PATH}")
    print("   Tables created: Project, ProjectWeeklySummary, RAIDitems, MBRitems")

if __name__ == "__main__":
    create_database()
