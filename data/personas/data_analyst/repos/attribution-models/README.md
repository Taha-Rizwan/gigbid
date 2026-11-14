# Attribution Models Repository  

## Purpose  
- Turn raw GA4 export events into a clean, daily‑updated table of marketing channels and their acquisition costs.  
- Enable a client to see which channels deliver the lowest cost‑per‑acquisition (CPA) and re‑allocate spend accordingly.  

## How it works  
- **Ingestion** – GA4 export lives in a BigQuery dataset (`raw_events`).  
- **Transformation** – dbt models (`models/`) parse the raw events, assign each hit to a marketing channel and calculate the daily spend per channel.  
- **Cost calculation** – a final view (`sql/channel_cost.sql`) joins the channel counts with the daily spend to produce `channel_acquisition_cost`.  
- **Refresh** – the dbt run is scheduled to run every morning via Cloud Scheduler (or any cron).  

## Setup  
1. Clone the repo.  
2. Install dbt (>=1.6) and the BigQuery adapter:  

   ```bash
   pip install dbt-bigquery
   ```  

3. Create a BigQuery service‑account key and set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to its path.  
4. Define the target dataset in `profiles.yml` (or use the default `analytics`).  

## Usage  

```bash
# Run the whole pipeline
dbt run --profiles-dir .

# Test the models
dbt test --profiles-dir .
```  

The final table `analytics.channel_acquisition_cost` can be connected to Looker Studio for visualisation.
