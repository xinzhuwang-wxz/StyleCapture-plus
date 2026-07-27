# M0 neutral interview script

Use this script only for people who may fit the 3-7 day travel cohort. Do not ask leading "would you use AI?" questions. Do not introduce the pixel world, Feed, try-on, or app concept before the offer is recorded.

## Screener

1. Are you 18 or older?
2. Do you have a real overnight trip departing in 7-30 days?
3. How many calendar days and nights is the trip?
4. Is the trip 3-7 days long?
5. Are you willing to show low-sensitivity proof of the trip with name, order number, ID, exact lodging, and contact data redacted, then have the proof deleted after qualification?
6. Do you own at least 8 garments or accessories that could cover this trip? Can you identify 8-12 of them without uploading a full wardrobe?
7. Are you a team member, direct family member, prior pro trialist, or paid professional creator? If creator, tag the source so the creator share can be capped at <=20%.

Reject the candidate if the trip is a single-day occasion, outside 7-30 days, not 3-7 days, not a real travel plan, lacks proof, lacks owned garments, or is team/direct family/pro trialist.

## Current behavior

Ask neutrally and record a concise coded answer:

1. Walk me through the last time you planned what to wear and pack for a multi-day trip.
2. What are you already doing for this upcoming trip?
3. What have you saved, bought, returned, listed, asked, or written down for it?
4. What would go wrong if the plan is bad?
5. On a 0-10 scale, how painful is this trip outfit/packing problem right now?
6. Why that number, not one point lower?

Do not coach a higher score. If the pain question is skipped, keep the participant in the appropriate exclusion/denominator state rather than imputing an answer.

## Wardrobe import tolerance

1. For this one trip, would you select only the clothes you might actually bring?
2. What is the maximum item count you would tolerate before the result feels like too much work?
3. Are 8 slot-covering items acceptable as the minimum, with 12-30 recommended for a stronger plan?
4. Which items must be included or excluded?
5. Which constraints are hard: weather, warmth, walking, dress code, luggage, photos, repeats, washing, shoes, bags, or accessories?

## Offer

Only after qualification, pain, current workaround, evidence of action, and wardrobe tolerance are recorded, show the complete concierge plan and the identical offer:

> For this trip result, the price is one ¥12 refundable deposit. It includes Day 2-7, all alternatives, cross-day deduplicated packing, gaps, and weather revisions for this trip. If we cannot deliver the plan or you cancel the trip, the deposit is refunded. This is not an iOS external payment link and does not unlock any App Store product.

Record only:

- `paid`
- `declined`
- `refunded`

Willingness, oral promises, "I would pay," creator barter, group owner access, or equivalent commitments are not `real_paid`.

## Post-trip follow-up

Run only after `trip_end+7d`.

1. Did you use at least one planned main Look?
2. Did you use at least one planned alternative Look?
3. Did you make a replacement that preserved the original hard constraints? Which hard constraints stayed true?
4. What did you not use?
5. What failed or felt untrustworthy?
6. Would you request another paid trip plan under the same terms?

Non-response, unclear use, and explicit no-use are not execution numerator successes.
