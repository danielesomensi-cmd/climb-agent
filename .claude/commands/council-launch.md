---
description: Run Council with the pre-loaded climb-agent launch timing + pricing question
---

Run /council with this question:

climb-agent: launch timing + pricing strategy

WHAT IS CLIMB-AGENT:
A deterministic AI-powered climbing training app for intermediate/advanced climbers (lead 7a-8b+, boulder 6C-8B). Core value: "Given my goal, my weaknesses, and my available time — what should I train today?"
- Engine: Horst 4-3-2-1 periodization + DUP. Assessment -> macrocycle -> weekly plan -> session resolver -> closed-loop feedback.
- No LLM at runtime: 100% rule-based, deterministic, testable.
- Stack: Python/FastAPI (Railway) + Next.js 14 PWA (Vercel). Auth: Clerk. DB: Supabase JSONB.
- Status: ~1,550 tests passing. 185 exercises. 50 endpoints. 31 pages. Zero P1 bugs. Pre-public-beta.

CURRENT STATE:
- 3 active beta testers (Christie, Vato, Alexis) + founder (Daniele, lead 8a/8a+, boulder 7C)
- Stripe integration planned but NOT yet implemented (14-day trial, EUR 9.99/month draft)
- Supabase migration planned but not done (current: JSONB on Railway, works fine at current scale)
- Team: solo developer, bootstrapped, no funding, no marketing budget
- Target: climbers who train seriously, 3-5x/week, goal-oriented, mostly gym-based

MARKET CONTEXT:
- No direct competitor does full periodized programming + closed-loop adaptation for climbers
- Nearest: generic training apps (TrainingPeaks), manual coaching (expensive), YouTube plans (unstructured)
- Community: climbing is a niche but passionate sport. Reddit (r/climbharder ~150k), Instagram, YouTube are the channels
- Price sensitivity: serious climbers pay EUR 20-40/month for a gym membership. Coaching costs EUR 80-200/month.

THE TWO DECISIONS:

1. LAUNCH TIMING: Should we launch publicly (with Stripe) now, or wait until Supabase migration is complete?
   - "Now" = Stripe integration takes ~1-2 weeks. Supabase migration is 4-6 weeks of high-risk work.
   - Risk of launching on current JSONB: data grows ~260KB/year per user — manageable for first 6-12 months.
   - Risk of waiting: losing momentum, delaying revenue, Supabase migration might surface new bugs.

2. PRICING: What's the right model?
   - Current draft: 14-day free trial -> EUR 9.99/month
   - Alternative A: Freemium (first macrocycle free, then pay)
   - Alternative B: EUR 9.99/month but EUR 79/year (save 34%)
   - Alternative C: Higher price (EUR 14.99/month) to signal quality in a niche market
   - Solo founder constraint: can't do annual plans without significant upfront tax/accounting complexity in Luxembourg
