<script lang="ts">
	import katex from 'katex';
	import {
		formatScripts,
		preprocessMatrices,
		stashRichContent,
		restoreRichContent
	} from '$lib/formatText';

	let { text = '', onchange }: { text: string; onchange?: (newText: string) => void } = $props();

	let editing = $state(false);
	let editText = $state('');
	let renderDiv: HTMLDivElement | undefined = $state();
	let textareaEl: HTMLTextAreaElement | undefined = $state();

	function renderMath() {
		if (!renderDiv) return;

		// Convert [ 1 2; 3 4 ] matrix notation into LaTeX before processing
		const processed = preprocessMatrices(text);

		// Stash tables, images, and legacy placeholders BEFORE LaTeX splitting
		// so they don't get broken by the LaTeX regex or escaped by formatScripts
		const { text: withTokens, items } = stashRichContent(processed);

		// Build HTML from text, rendering LaTeX segments with KaTeX
		let html = '';
		let lastIndex = 0;
		const combined = [...withTokens.matchAll(/\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)/g)];
		combined.sort((a, b) => a.index! - b.index!);

		for (const match of combined) {
			const start = match.index!;
			if (start > lastIndex) {
				html += formatScripts(withTokens.slice(lastIndex, start));
			}

			const isDisplay = match[0].startsWith('\\[');
			const latex = isDisplay ? match[1] : match[2];

			try {
				html += katex.renderToString(latex, {
					displayMode: isDisplay,
					throwOnError: false
				});
			} catch {
				html += `<span class="katex-error">${escapeHtml(match[0])}</span>`;
			}

			lastIndex = start + match[0].length;
		}

		if (lastIndex < withTokens.length) {
			html += formatScripts(withTokens.slice(lastIndex));
		}

		// Restore stashed tables, images, and badges into the final HTML
		html = restoreRichContent(html, items);

		renderDiv.innerHTML = html;
	}

	function escapeHtml(str: string): string {
		return str
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}


	$effect(() => {
		if (!editing) {
			// Re-run whenever text changes or we exit editing
			text;
			// Use tick to ensure renderDiv is in DOM
			requestAnimationFrame(() => renderMath());
		}
	});

	function startEditing() {
		editText = text;
		editing = true;
		requestAnimationFrame(() => {
			if (textareaEl) {
				textareaEl.focus();
				autoResize(textareaEl);
			}
		});
	}

	function finishEditing() {
		editing = false;
		if (editText !== text && onchange) {
			onchange(editText);
		}
	}

	function autoResize(ta: HTMLTextAreaElement) {
		ta.style.height = 'auto';
		ta.style.height = ta.scrollHeight + 'px';
	}
</script>

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" />

{#if editing}
	<textarea
		class="editable-question-text"
		bind:this={textareaEl}
		bind:value={editText}
		oninput={() => textareaEl && autoResize(textareaEl)}
		onblur={finishEditing}
	></textarea>
{:else}
	<div
		class="rendered-math"
		role="button"
		tabindex="-1"
		bind:this={renderDiv}
		onclick={startEditing}
		onkeydown={(e) => {
			if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				startEditing();
			}
		}}
	></div>
{/if}

<style>
	.rendered-math {
		cursor: text;
		padding: 8px;
		border: 1px solid transparent;
		border-radius: 6px;
		white-space: pre-wrap;
		word-break: break-word;
		line-height: 1.6;
		min-height: 2em;
	}

	.rendered-math:hover {
		border-color: #d0d0d0;
		background: #fafafa;
	}

	textarea.editable-question-text {
		width: 100%;
		padding: 8px;
		border: 1px solid #4a90d9;
		border-radius: 6px;
		font-family: inherit;
		font-size: inherit;
		line-height: 1.6;
		resize: none;
		overflow: hidden;
		box-sizing: border-box;
		outline: none;
	}

	:global(.katex-error) {
		color: #cc0000;
		font-family: monospace;
	}

	:global(.question-diagram) {
		max-width: 100%;
		height: auto;
		display: block;
		margin: 8px 0;
	}

	:global(.question-table-wrap) {
		white-space: normal;
	}

	:global(.question-table-wrap table) {
		border-collapse: collapse;
		margin: 8px 0;
	}

	:global(.question-table-wrap td, .question-table-wrap th) {
		border: 1px solid #ddd;
		padding: 6px 10px;
	}

	:global(.question-table-wrap th) {
		background: #f5f5f5;
		font-weight: 600;
	}

	:global(.placeholder-badge) {
		display: inline-block;
		padding: 2px 8px;
		background: #f0f0f0;
		border: 1px solid #ddd;
		border-radius: 4px;
		color: #666;
		font-size: 0.85em;
		font-style: italic;
	}
</style>
