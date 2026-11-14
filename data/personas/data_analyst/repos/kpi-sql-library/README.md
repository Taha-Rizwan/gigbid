# kpi-sql-library

Reusable SQL views for common e‑commerce key performance indicators.

## Purpose
- Provide a single source of truth for **Revenue**, **Average Order Value (AOV)** and **Repeat Purchase Rate**.  
- Enable analysts to spin‑up a new dashboard in minutes rather than days.  
- Keep the definitions consistent across every client engagement.

## How it works
- Each KPI is defined as a dbt model (`*.sql`) that builds on a base `orders` table.  
- The models use PostgreSQL window functions to calculate aggregates efficiently.  
- A small `schema.yml` file declares tests and documentation for the views.  

## Setup
1. Clone the repository.  
2. Install dbt (PostgreSQL profile) – e.g. `pip install dbt-postgres`.  
3. Create a `.env` file with your connection details (or set the variables in your environment):  

   ```bash
   export DBT_PROFILE_TARGET=dev
   export DBT_USER=your_user
   export DBT_PASSWORD=your_password
   export DBT_HOST=your_host
   export DBT_DBNAME=your_db
   ```

4. Run `dbt deps && dbt seed && dbt run` from the project root.

## Usage
```bash
# Build all KPI views
dbt run --models kpi_*

# Test the definitions
dbt test --models kpi_*
```

The resulting views (`kpi_revenue`, `kpi_aov`, `kpi_repeat_rate`) can be queried directly or added to a BI tool such as Metabase or Looker.

---

*The library was created for a legal‑tech client in August 2022 and is licensed under the MIT licence.*
