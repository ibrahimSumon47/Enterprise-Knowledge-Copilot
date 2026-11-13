# 90-second demo

Live: https://enterprise-knowledge-copilot-wine.vercel.app

Open the site in a clean browser profile. Light theme is the default.

| Time | Screen | What to say |
| --- | --- | --- |
| 0:00 | Home | “This is a knowledge copilot over company documents. A visitor can open the sample workspace without an account.” |
| 0:08 | Click **Open sample workspace** | “One click signs in as a read-only guest, so the documents stay read-only and nothing needs setting up.” |
| 0:14 | Chat, ask *How do I submit an expense receipt?* | “The answer is short, and every sentence points at a passage.” |
| 0:25 | Open the source under the answer | “The passage, the document title, the section and the licence. This is the part a reviewer actually checks.” |
| 0:38 | Ask *What is the home address of the CEO?* | “The documents do not cover it, so it refuses. It offers the closest documents instead of a dead end.” |
| 0:50 | Admin → Unanswered (signed in as an administrator) | “That refusal is already in the gap queue, with the role that asked and the reason. An admin can close it once a document is added.” |
| 1:05 | Library | “The sample workspace is labelled, and only the documents this role may read are listed.” |
| 1:15 | Admin → Quality | “Answer quality and response times live here for administrators; the customer-facing site never shows them.” |
| 1:25 | Close | “Citations, permissions in the query, and a queue for the gaps. That is the product.” |

Notes for recording:

- The first answer after a quiet period may take a few seconds while the free API instance warms; the ten-minute keep-warm workflow keeps that rare.
- Sign in as `admin@ekc.local` for the admin screens; the password is the deployment secret, never in this repository.
- Record at 1440×900; the layout also holds at 768 and 375.
