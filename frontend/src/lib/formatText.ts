/** Escape HTML entities, then convert ^{text} to <sup> and _{text} to <sub>. */
export function formatScripts(str: string): string {
	const escaped = str
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
	return escaped
		.replace(/\^{([^}]*)}/g, '<sup>$1</sup>')
		.replace(/\^(\S)/g, '<sup>$1</sup>')
		.replace(/_{([^}]*)}/g, '<sub>$1</sub>')
		.replace(/_(\S)/g, '<sub>$1</sub>');
}

/** Convert [ 1 2; 3 4 ] matrix notation into LaTeX \(...\) so KaTeX can render it. */
export function preprocessMatrices(str: string): string {
	return str.replace(
		/\[\s*((?:-?\d+(?:\.\d+)?(?:\s+-?\d+(?:\.\d+)?)*)\s*(?:;\s*(?:-?\d+(?:\.\d+)?(?:\s+-?\d+(?:\.\d+)?)*)\s*)+)\]/g,
		(_, content: string) => {
			const rows = content.split(';').map((row) => row.trim().split(/\s+/).join(' & '));
			return `\\(\\begin{bmatrix} ${rows.join(' \\\\ ')} \\end{bmatrix}\\)`;
		}
	);
}
