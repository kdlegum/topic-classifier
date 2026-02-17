/** Check if the user prefers reduced motion */
export function shouldAnimate(): boolean {
	if (typeof window === 'undefined') return false;
	return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Shared easing and duration constants */
export const DURATIONS = {
	fast: 150,
	normal: 300,
	slow: 500,
	stagger: 50
} as const;

export const EASINGS = {
	ease: 'ease',
	easeOut: 'cubic-bezier(0.16, 1, 0.3, 1)',
	spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
} as const;
