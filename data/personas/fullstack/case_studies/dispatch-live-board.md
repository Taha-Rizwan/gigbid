---
evidence_id: fullstack:case:dispatch-live-board
title: Live dispatch board for a freight company
project: Cargoline Freight - Live dispatch board for a freight company
client_industry: logistics
date: 2022-10
skills:
- real-time applications
- maps
- websockets-style push updates
outcome: dispatchers handle twice the loads per shift; phone calls to drivers down
  60%
synthetic: true
generator:
  model: openai/gpt-oss-120b
  prompt_version: persona_v1
  seed: 451610570
---

# Live dispatch board for a freight company

I was approached by a mid‑size logistics carrier that needed a modern control room for their dispatch team. Their old spreadsheet‑based system forced operators to pick up the phone for every status change, and they struggled to keep up with the growing volume of shipments.

**Challenge**
- Provide an at‑a‑glance view of every vehicle on a map, updating the moment a driver checks in.
- Reduce the reliance on phone calls for location and ETA confirmations.
- Support multiple dispatch consoles without any lag or data conflict.
- Keep the solution maintainable for a small engineering crew.

**Approach**
- I set up a persistent connection between the browser and the server so that any driver status change is broadcast instantly to all open dashboards. This means trucks and loads move on the map the moment a driver updates.
- To keep the system scalable, I spun up several server instances that share updates through a message channel, ensuring every console sees the same live data.
- The front‑end renders the map and overlays each vehicle’s icon, coloring them by status and attaching a tooltip with cargo details. Users can filter by route, driver, or priority load.
- I used **Node.js** to handle the high‑frequency events and manage the message bus, and **React** to build a responsive UI that reacts to each incoming update without a full page refresh.
- For the geographic layer I integrated a vector‑based map service, enabling smooth panning and zooming even with dozens of moving markers.
- Redis pub/sub was employed as the lightweight broker that routes messages between the server nodes, guaranteeing low latency.
- The codebase follows a modular pattern, separating the real‑time layer from the business logic, which makes future feature additions – like predictive ETA or driver performance analytics – straightforward.

**Impact**
- Dispatch operators now see every load’s location in real time, allowing them to reassign assets on the fly and balance workloads efficiently.
- Phone calls to drivers dropped by 60%, freeing up the communications team for higher‑value tasks.
- The team reported handling roughly twice the number of loads per shift, directly boosting revenue without additional hires.
- The solution has been running smoothly for over a year, with minimal maintenance overhead, and the client plans to roll it out to additional regional hubs.
