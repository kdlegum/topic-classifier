import { API_BASE } from '$lib/api';

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

export type StashedContent = {
	text: string;
	items: string[];
};

/**
 * Stash HTML tables, markdown images, and legacy placeholders as tokens
 * so they survive HTML escaping and LaTeX splitting.
 * Tokens use \x00RCH<n>\x00 — no underscores (formatScripts turns _ into <sub>).
 */
export function stashRichContent(str: string): StashedContent {
	const items: string[] = [];

	// Stash <table>...</table> blocks
	str = str.replace(/<table\b[^>]*>[\s\S]*?<\/table>/gi, (match) => {
		const idx = items.length;
		items.push(`<div class="question-table-wrap">${match}</div>`);
		return `\x00RCH${idx}\x00`;
	});

	// Stash ![alt](url) images
	str = str.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt: string, url: string) => {
		const idx = items.length;
		const fullUrl = url.startsWith('/') ? `${API_BASE}${url}` : url;
		const safeAlt = alt
			.replace(/&/g, '&amp;')
			.replace(/"/g, '&quot;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;');
		items.push(
			`<img src="${fullUrl}" alt="${safeAlt}" class="question-diagram" loading="lazy">`
		);
		return `\x00RCH${idx}\x00`;
	});

	// Stash legacy [DIAGRAM] / [DIAGRAM: text] / [TABLE] as styled badges
	str = str.replace(/\[DIAGRAM(?::\s*([^\]]*))?\]/g, (_, desc?: string) => {
		const idx = items.length;
		const label = desc ? `Diagram: ${desc}` : 'Diagram';
		items.push(`<span class="placeholder-badge">${label}</span>`);
		return `\x00RCH${idx}\x00`;
	});
	str = str.replace(/\[TABLE\]/g, () => {
		const idx = items.length;
		items.push('<span class="placeholder-badge">Table</span>');
		return `\x00RCH${idx}\x00`;
	});

	return { text: str, items };
}

/** Restore stashed rich content tokens back into the final HTML. */
export function restoreRichContent(html: string, items: string[]): string {
	return html.replace(/\x00RCH(\d+)\x00/g, (_, idx: string) => items[parseInt(idx)]);
}
