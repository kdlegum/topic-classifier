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

	const colors = [TEAL, CORAL, AMBER, GREEN, '#A78BFA'];
	const duration = 1500;
	const end = Date.now() + duration;

	function frame() {
		confetti({
			particleCount: 3,
			angle: 60,
			spread: 55,
			origin: { x: 0, y: 0.6 },
			colors,
			scalar: 0.8,
			ticks: 100
		});
		confetti({
			particleCount: 3,
			angle: 120,
			spread: 55,
			origin: { x: 1, y: 0.6 },
			colors,
			scalar: 0.8,
			ticks: 100
		});

		if (Date.now() < end) {
			requestAnimationFrame(frame);
		}
	}

	frame();
}
