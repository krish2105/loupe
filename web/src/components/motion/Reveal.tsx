"use client";

import { motion, useReducedMotion, type Variants } from "motion/react";

/**
 * The entrance reveal.
 *
 * Only transform and opacity animate (§7.3) — anything else drops frames during
 * scroll. Under reduced motion the element renders with no animation at all
 * rather than a faster one, so the content is simply there.
 */

const variants: Variants = {
  hidden: { opacity: 0, y: 12 },
  shown: { opacity: 1, y: 0 },
};

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();

  if (reduce) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      variants={variants}
      initial="hidden"
      animate="shown"
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
