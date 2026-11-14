-- View: channel_acquisition_cost
-- Purpose: Combine daily new‑user counts with channel spend to compute CAC.
-- Dependencies: models/channel_assignments.sql, raw spend table `marketing_spend.daily_spend`

create or replace view `analytics.channel_acquisition_cost` as
with new_users as (
    select
        event_date,
        channel,
        count(distinct user_id) as new_users
    from `{{ var('project') }}.analytics.channel_events`
    group by event_date, channel
),

spend as (
    select
        spend_date,
        channel,
        sum(spend_amount) as spend
    from `{{ var('project') }}.marketing_spend.daily_spend`
    group by spend_date, channel
)

select
    n.event_date as date,
    n.channel,
    n.new_users,
    s.spend,
    case when n.new_users = 0 then null else s.spend / n.new_users end as acquisition_cost
from new_users n
left join spend s
  on n.event_date = s.spend_date
 and n.channel = s.channel
order by date desc, channel;
