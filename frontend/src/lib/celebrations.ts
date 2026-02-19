import confetti from 'canvas-confetti';

const TEAL = '#14B8A6';
const CORAL = '#F97316';
const AMBER = '#F59E0B';
const GREEN = '#22C55E';

function shouldAnimate(): boolean {
	if (typeof window === 'undefined') return false;
	return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Confetti burst for full marks on a single question */
export function celebrateFullMarks() {
	if (!shouldAnimate()) return;

	confetti({
		particleCount: 60,
		spread: 55,
		origin: { y: 0.7 },
		colors: [TEAL, CORAL, AMBER, GREEN],
		scalar: 0.9,
		gravity: 1.2,
		drift: 0,
		ticks: 120
	});
}

/** Multi-point confetti for session/classification complete */
export function celebrateCompletion() {
	if (!shouldAnimate()) return;

	confetti({
		particleCount: 80,
		spread: 60,
		origin: { y: 0.65 },
		colors: [TEAL, CORAL, AMBER, GREEN, '#A78BFA'],
		scalar: 0.9,
		gravity: 1.2,
		ticks: 130
	});
}
