# How To Speak About DSD Notification In Interview

---

## YOUR 30-SECOND PITCH

> "I built real-time push notifications for DSD shipments. When a supplier delivers to a store, SUMO push alerts go to the receiving team's devices with the vendor name, trailer number, and ETA. Only ENROUTE and ARRIVED events trigger notifications - we deliberately filter the other three event types to avoid fatigue. 1,200+ associates across 300+ stores, 35% improvement in replenishment timing."

---

## WHEN TO USE THIS STORY

| They Ask About... | Use This |
|-------------------|----------|
| "Tell me about all your projects" | Quick mention as third project |
| "User-facing impact" | 1,200 associates getting real-time alerts |
| "Notification system design" | Full DSD architecture |
| "How do you think about users?" | Notification fatigue filtering |

---

## THE KEY INSIGHT TO SHARE

> "The most important design decision was what NOT to notify. DSD has 5 event types but only 2 require associate action. Sending 5 notifications per delivery would cause fatigue. This taught me: in notification systems, restraint is more important than coverage."

---

## NUMBERS TO DROP

| Number | How to Say It |
|--------|---------------|
| 1,200+ associates | "...over twelve hundred store associates receive alerts..." |
| 300+ stores | "...across 300+ store locations..." |
| 35% improvement | "...35% improvement in replenishment timing..." |
| 5 event types, 2 notify | "...five event types but only two trigger notifications..." |
| ENROUTE + ARRIVED | "...ENROUTE gives prep time, ARRIVED means go to dock now..." |

---

## PIVOT TECHNIQUES

**From this to Kafka audit:**
> "The DSD endpoints are actually audited by the logging system I built. Every supplier API call is captured for compliance. Want me to walk through that architecture?"

**From this to Spring Boot 3:**
> "DSD runs on cp-nrti-apis which I migrated to Spring Boot 3. That migration was a bigger technical challenge - 158 files, zero downtime."

**From this if they drill too deep:**
> "The DSD notification was one part of a larger system. The more technically interesting challenge was the audit logging architecture or the DC Inventory API design. Which would you like to hear about?"

---

## GOOGLEYNESS STORY: Putting Users First

> "I could have notified associates on all 5 DSD events. More notifications seems like better coverage. But I thought about the ASSOCIATE's experience - getting 5 alerts per delivery, multiple times a day, across multiple suppliers? They'd stop paying attention. I deliberately limited notifications to the 2 events that require action: ENROUTE (prepare) and ARRIVED (go now). Restraint in design is user empathy."

---

*This is a supporting story, not your primary. Keep it to 30 seconds unless they ask for more.*
