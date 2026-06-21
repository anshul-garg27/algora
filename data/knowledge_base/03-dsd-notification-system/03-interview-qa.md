# Interview Q&A - DSD Notification System

---

## Q1: "Tell me about the DSD notification system."

> "I built real-time push notifications for Direct Store Delivery. When suppliers like Pepsi deliver to a Walmart store, our system sends SUMO push notifications to store associates. Before this, associates discovered deliveries through periodic checks - hours of delay. After: real-time alerts within seconds.
>
> The system captures 5 event types - Planned, Started, Enroute, Arrived, Completed - but only ENROUTE and ARRIVED trigger notifications, because those are the states where associates need to act. Each notification includes the commodity type, trailer number, and for ENROUTE, the ETA window in the store's local timezone."

---

## Q2: "How did you measure the 35% improvement?"

> "We measured replenishment timing as the gap between the ARRIVED event timestamp and the inventory scan timestamp. Before notifications, this gap averaged hours because associates discovered deliveries during periodic checks. After real-time push alerts, they responded within minutes. The 35% represents the reduction in this end-to-end lag. The business operations team tracked this through operational dashboards. My contribution was the technical pipeline - from supplier API to associate device."

**Follow-up: "35% of what exactly?"**
> "35% reduction in the time between goods arriving at the dock and goods being scanned into inventory. The business team measured pre vs post notification deployment."

---

## Q3: "What is SUMO?"

> "SUMO is Walmart's internal push notification platform for associate devices - similar to Firebase Cloud Messaging but internal. We call SUMO's V3 Mobile Push API with a notification payload and audience targeting. The audience specifies countryCode, domain (STORE vs DC vs HomeOffice), siteId (specific store number), and roles (receiving team). This ensures the right associates at the right store get the notification."

---

## Q4: "Why only ENROUTE and ARRIVED, not all events?"

> "Notification fatigue. If we sent 5 notifications per shipment per store, associates would start ignoring them. ENROUTE gives them preparation time - 'delivery coming in 30 min, clear the dock.' ARRIVED means 'go to the dock now.' PLANNED and STARTED are informational only - no associate action needed. COMPLETED means it's already done."

---

## Q5: "How does the targeting work?"

> "Three levels: Domain → Site → Roles. Domain is STORE (not DC or Home Office). Site is the specific store number from the shipment destination. Roles come from CCM config - we target the receiving team roles, not all store associates. A delivery to Store 4236 only notifies associates at Store 4236 with the receiving role."

---

## Q6: "What if SUMO is down?"

> "The notification fails silently - we catch SignatureHandleException and log the error. The API response to the supplier is NOT affected. The DSD event is still persisted to Kafka regardless of SUMO success. We also have a feature flag (isSumoEnabled) that can disable SUMO notifications without redeployment if there's a widespread issue."

---

## Q7: "What was the hardest part?"

> "ETA timezone handling. Suppliers send timestamps in UTC. But associates need 'ETA between 2:00 PM and 3:00 PM' in their LOCAL timezone. Different stores are in different timezones. We built a store-to-timezone mapping and convert UTC to local AM/PM format before building the notification body. Getting this right for stores across multiple timezones was tricky."

---

## Q8: "How does this connect to the audit logging system?"

> "The DSD API endpoint POST /directShipmentCapture is one of the endpoints audited by our common library. Every supplier call - successful or failed - is captured asynchronously and stored in GCS as Parquet. Suppliers can query their DSD API interactions in BigQuery. So the audit system and DSD system work together - DSD captures the shipment events, audit captures the API interactions."

---

## Q9: "What would you do differently?"

> "Three things. First, add delivery confirmation - currently we notify on arrival but don't track when the associate actually processes it. A confirmation button in the notification would close the loop. Second, add retry for failed SUMO calls - currently we log and move on. Third, add notification analytics - track open rates to measure if associates are actually reading notifications."

---

## STAR Story: DSD Notification

> **Situation:** "Walmart associates at 300+ stores were discovering DSD deliveries through periodic checks, causing hours of delay in shelving goods."
>
> **Task:** "Build a real-time notification system to alert associates immediately when deliveries are enroute or arrive."
>
> **Action:** "I integrated with Walmart's SUMO push notification platform. Built the notification service with event-type filtering - only ENROUTE and ARRIVED trigger alerts to avoid fatigue. Implemented commodity-type mapping so notifications say 'Beverage delivery' not just 'DSD delivery.' Added CCM-configurable role targeting so only receiving team gets notified. Used feature flags for safe rollout."
>
> **Result:** "1,200+ associates across 300+ stores receive real-time delivery alerts. 35% improvement in stock replenishment timing as measured by the operations team."
>
> **Learning:** "Notification design is about restraint - knowing what NOT to notify is as important as knowing what to notify. Five events, but only two matter for action."

---

## Quick Answers

**"Why not SMS?"** → "SUMO targets associate devices directly by store and role. SMS would require phone numbers and can't target by role."

**"Why CCM for roles?"** → "Stores reorganize. Role names change. CCM means no code change when roles update."

**"Why Kafka AND SUMO?"** → "Kafka for persistence and audit trail. SUMO for real-time push. If SUMO fails, the event is still in Kafka."

**"What's the notification latency?"** → "Under 5 seconds from API call to associate device, depending on SUMO platform and device connectivity."

---

*Practice the 30-sec pitch and the 35% measurement answer out loud!*
