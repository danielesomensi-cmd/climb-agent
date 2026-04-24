"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { trackEvent } from "@/lib/analytics";

type FaqEntry = {
  id: string;
  question: string;
  answer: string;
};

const FAQS: FaqEntry[] = [
  {
    id: "cancel",
    question: "Can I cancel anytime?",
    answer:
      "Yes. You can cancel your subscription from Settings at any point. You keep access until the end of the billing period.",
  },
  {
    id: "after_trial",
    question: "What happens after the free trial?",
    answer:
      "You'll be billed $4.99 or $9.99 based on the tier you selected. Cancel before day 15 to avoid any charge.",
  },
  {
    id: "why_founding",
    question: "Why Founding Climber?",
    answer:
      "The first 20 subscribers lock their price at $4.99/month forever, as a thank-you for backing climb-agent early. When the 20 spots fill, this tier disappears.",
  },
  {
    id: "refund",
    question: "What if I'm not happy?",
    answer:
      "Email Daniele directly. If climb-agent isn't working for you in the first 30 days, full refund.",
  },
];

export function PaywallFAQ() {
  return (
    <section className="px-6 pb-8">
      <h2 className="mb-4 text-lg font-semibold text-fg">Questions?</h2>
      <Accordion
        type="single"
        collapsible
        onValueChange={(value) => {
          if (value) trackEvent("faq_expanded", { question_id: value });
        }}
      >
        {FAQS.map(({ id, question, answer }) => (
          <AccordionItem key={id} value={id}>
            <AccordionTrigger className="text-left text-sm font-medium text-fg">
              {question}
            </AccordionTrigger>
            <AccordionContent className="text-sm text-fg-secondary">
              {answer}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}
