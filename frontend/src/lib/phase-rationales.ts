/** Phase rationales — static educational content for the Plan page (A141). */

export interface PhaseRationale {
  title: string;
  subtitle?: string;
  text: string;
  duration_note?: string;
  common_mistake?: string;
  what_to_expect?: string;
}

export const PERIODIZATION_RATIONALE: PhaseRationale = {
  title: "Why your plan is structured this way",
  text: "Your training follows a proven 4-phase cycle: build your aerobic base, develop strength, convert it to power endurance, then peak for performance. Each phase targets different physiological adaptations in the order your body needs them. Research across 35+ studies shows periodized training produces significantly better strength gains than random training. Our model combines H\u00f6rst\u2019s climbing-specific phase sequence with daily undulating variation \u2014 you get the benefits of structured progression and stimulus variety.",
};

/** Keyed by phase_id (matches vocabulary_v1.md and macrocycle output). */
export const PHASE_RATIONALES: Record<string, PhaseRationale> = {
  base: {
    title: "Endurance Base",
    subtitle: "Building your aerobic foundation",
    text: "Think of this as base miles for a runner \u2014 essential groundwork. Your forearm capillaries need at least 6 weeks of sustained low-intensity work to grow new blood vessels (angiogenesis) and build new mitochondria. These adaptations let you deliver more oxygen and clear waste products faster \u2014 the difference between pumping out on the crux and cruising through it.",
    duration_note: "6 weeks minimum \u2014 cutting it short means incomplete vascular adaptation.",
    common_mistake: "Going too hard. If you feel ANY pump during ARC, you\u2019re above the 25% MVC threshold and switching from aerobic to anaerobic \u2014 which defeats the purpose.",
    what_to_expect: "High volume, low intensity. Lots of easy climbing, technique drills, and general conditioning. It will feel easy \u2014 that\u2019s the point.",
  },
  strength_power: {
    title: "Strength & Power",
    subtitle: "Neural horsepower",
    text: "Your capillaries are built \u2014 now we\u2019re adding the neural horsepower to use them. This phase pushes your nervous system to recruit more muscle fibers simultaneously. High intensity, low volume. By the end, your max hang should increase by 5-10%, which translates directly to holding smaller holds longer.",
    duration_note: "3-4 weeks. Neural adaptations happen faster than structural ones.",
    common_mistake: "Adding volume. This phase is about quality, not quantity. Stop any set when speed or form drops.",
    what_to_expect: "Fewer sets, heavier loads. Max hangs, limit bouldering, weighted pull-ups. Sessions feel intense but short.",
  },
  power_endurance: {
    title: "Power Endurance",
    subtitle: "Putting it all together",
    text: "Now we convert your base and strength into the ability to perform sustained hard moves on a route. This phase trains your body to recover between hard sequences while staying on the wall. The intensity varies within each session \u2014 hard problems mixed with easier ones to train the recovery-under-load system.",
    duration_note: "3-4 weeks. Your body is learning to buffer lactate and recover between cruxes.",
    common_mistake: "Going all-out on every problem. The varied intensity is intentional \u2014 easy problems between hard ones allow partial recovery.",
    what_to_expect: "Interval-style climbing, route repetitions, sustained sessions. You\u2019ll feel pumped \u2014 that\u2019s the training stimulus.",
  },
  performance: {
    title: "Performance",
    subtitle: "Send season",
    text: "Everything you\u2019ve built comes together now. Volume drops, intensity stays high, and the focus shifts to climbing at your limit. This is when you attempt your project, try hard onsights, and push your grade. Your body is at peak readiness \u2014 use it.",
    duration_note: "1-2 weeks. Short and sharp \u2014 you\u2019re spending fitness, not building it.",
    common_mistake: "Training through it. This is NOT the time to add conditioning or hangboard volume. Climb hard, rest well.",
    what_to_expect: "Fewer sessions, maximum effort on the wall. Project attempts. Outdoor days if possible.",
  },
  deload: {
    title: "Deload",
    subtitle: "Recovery is training",
    text: "Your body consolidates all the gains from the last macrocycle during this week. Growth hormone surges during deep sleep, tendons repair microdamage, and your nervous system resets. Skipping deload is the fastest path to overtraining and injury.",
    duration_note: "1 week. Non-negotiable.",
    common_mistake: "Feeling guilty and sneaking in hard sessions. Light movement is fine \u2014 hard training undermines everything you just built.",
    what_to_expect: "Easy climbing, mobility work, maybe a rest day or two. You may feel restless \u2014 that\u2019s normal and means the previous phase worked.",
  },
};
