---
evidence_id: fullstack:case:patient-booking-portal
title: Online booking portal for a clinic network
project: Lumen Health - Online booking portal for a clinic network
client_industry: healthcare
date: 2019-10
skills:
- web applications
- booking systems
- API design
outcome: 40% of bookings moved online in six months; no-shows down 18%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 2059431108
---

# Online booking portal for a clinic network

### The problem
Lumen Health was still handling most of its clinic appointments over the phone or via a clunky legacy portal. Staff spent hours juggling spreadsheets, double‑booking happened frequently, and patients often forgot their slots, leading to a high no‑show rate. The leadership wanted a modern solution that would let users choose a time, lock it instantly so nobody else could take it, and send a reminder the day before to keep appointments solid.

### What I did
I designed a single‑page interface where users browse available windows, pick a slot, and confirm with a click. The moment a slot is selected, the system reserves it in the database, preventing any other user from grabbing the same time—this lock‑out mechanism eliminated double bookings. After confirmation, a background job queues a text message that goes out the day before the appointment, nudging patients and reducing forgetfulness. To keep the UI snappy I used a component library that updates the calendar in real time as slots fill, and I wrote server‑side endpoints that handle the reservation logic and send the SMS alerts. I stored all appointment data in a relational database, which let us enforce uniqueness constraints on time slots and run quick queries for availability. Throughout the project I collaborated with product managers and QA to iterate on the flow, adding features like rescheduling links and admin dashboards for staff to see daily bookings at a glance.

### Results
Within six months of launch, 40% of the network’s appointments were being booked through the new portal, freeing up call‑center time for more complex support tasks. The reminder texts proved effective: no‑shows dropped by 18%, translating to a noticeable uptick in clinic utilization and revenue. The client praised the smooth user experience and the reduction in manual scheduling overhead, and the solution became the blueprint for future rollout across additional locations.
