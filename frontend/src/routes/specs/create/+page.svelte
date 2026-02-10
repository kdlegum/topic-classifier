<script lang="ts">
	import { goto } from '$app/navigation';
	import { createSpec, type TopicInput } from '$lib/api';

	let qualification = $state('');
	let subject = $state('');
	let examBoard = $state('');
	let specCode = $state('');
	let description = $state('');
	let optionalModules = $state(false);
	let hasMath = $state(false);

	let topics: TopicInput[] = $state([
		{ strand: '', topic_name: '', subtopics: [{ subtopic_name: '', description: '' }] }
	]);

	let isSubmitting = $state(false);
	let errorMsg = $state('');

	function addTopic() {
		topics = [
			...topics,
			{ strand: '', topic_name: '', subtopics: [{ subtopic_name: '', description: '' }] }
		];
	}

	function removeTopic(idx: number) {
		topics = topics.filter((_, i) => i !== idx);
	}

	function addSubtopic(topicIdx: number) {
		topics[topicIdx].subtopics = [
			...topics[topicIdx].subtopics,
			{ subtopic_name: '', description: '' }
		];
	}

	function removeSubtopic(topicIdx: number, subIdx: number) {
		topics[topicIdx].subtopics = topics[topicIdx].subtopics.filter((_, i) => i !== subIdx);
	}

	function validate(): string | null {
		if (!qualification.trim()) return 'Qualification is required.';
		if (!subject.trim()) return 'Subject is required.';
		if (!examBoard.trim()) return 'Exam board is required.';
		if (!specCode.trim()) return 'Spec code is required.';
		if (topics.length === 0) return 'At least one topic is required.';

		for (let i = 0; i < topics.length; i++) {
			const t = topics[i];
			if (!t.strand.trim()) return `Topic ${i + 1}: strand is required.`;
			if (!t.topic_name.trim()) return `Topic ${i + 1}: topic name is required.`;
			if (t.subtopics.length === 0)
				return `Topic ${i + 1}: at least one subtopic is required.`;

			for (let j = 0; j < t.subtopics.length; j++) {
				const s = t.subtopics[j];
				if (!s.subtopic_name.trim())
					return `Topic ${i + 1}, Subtopic ${j + 1}: name is required.`;
				if (!s.description.trim())
					return `Topic ${i + 1}, Subtopic ${j + 1}: description is required.`;
			}
		}
		return null;
	}

	async function handleSubmit() {
		errorMsg = '';
		const validationError = validate();
		if (validationError) {
			errorMsg = validationError;
			return;
		}

		isSubmitting = true;
		try {
			await createSpec({
				qualification: qualification.trim(),
				subject: subject.trim(),
				exam_board: examBoard.trim(),
				spec_code: specCode.trim(),
				optional_modules: optionalModules,
				has_math: hasMath,
				description: description.trim() || undefined,
				topics: topics
			});
			goto('/specs');
		} catch (err: any) {
			errorMsg = err.message || 'Failed to create specification.';
		} finally {
			isSubmitting = false;
		}
	}

	function getTopicNumber(idx: number): string {
		return String(idx + 1);
	}

	function getSubtopicId(topicIdx: number, subIdx: number): string {
		return `${topicIdx + 1}${String.fromCharCode(97 + subIdx)}`;
	}
</script>

<svelte:head>
	<title>Create Specification - Topic Tracker</title>
</svelte:head>

<main class="page-content create-spec-page">
	<a href="/specs" class="back-link">&larr; Back to Specifications</a>

	<h1>Create Specification</h1>
	<p>Define a custom specification with topics and subtopics.</p>

	{#if errorMsg}
		<div class="error-banner">{errorMsg}</div>
	{/if}

	<!-- Basic Info -->
	<div class="form-section">
		<h2>Basic Information</h2>
		<div class="form-grid">
			<div class="form-field">
				<label for="qualification">Qualification <span class="required">*</span></label>
				<input id="qualification" type="text" placeholder='e.g. "A Level"' bind:value={qualification} />
			</div>
			<div class="form-field">
				<label for="subject">Subject <span class="required">*</span></label>
				<input id="subject" type="text" placeholder='e.g. "Computer Science"' bind:value={subject} />
			</div>
			<div class="form-field">
				<label for="exam-board">Exam Board <span class="required">*</span></label>
				<input id="exam-board" type="text" placeholder='e.g. "OCR"' bind:value={examBoard} />
			</div>
			<div class="form-field">
				<label for="spec-code">Spec Code <span class="required">*</span></label>
				<input id="spec-code" type="text" placeholder='e.g. "H446"' bind:value={specCode} />
			</div>
		</div>
		<div class="form-field">
			<label for="description">Description (optional)</label>
			<textarea id="description" rows="2" placeholder="Brief description of the specification..." bind:value={description}></textarea>
		</div>
		<div class="form-field checkbox-field">
			<label>
				<input type="checkbox" bind:checked={optionalModules} />
				Has optional modules (students choose strands)
			</label>
		</div>
		<div class="form-field checkbox-field">
			<label>
				<input type="checkbox" bind:checked={hasMath} />
				Contains math notation (uses enhanced OCR pipeline)
			</label>
		</div>
	</div>

	<!-- Content Builder -->
	<div class="form-section">
		<div class="section-header">
			<h2>Topics & Subtopics</h2>
			<button type="button" class="btn-add-topic-main" onclick={addTopic}>+ Add Topic</button>
		</div>

		{#each topics as topic, tIdx}
			<div class="topic-card">
				<div class="topic-header">
					<span class="topic-number">Topic {getTopicNumber(tIdx)}</span>
					{#if topics.length > 1}
						<button type="button" class="btn-remove-topic" onclick={() => removeTopic(tIdx)}>Remove Topic</button>
					{/if}
				</div>

				<div class="topic-fields">
					<div class="form-field">
						<label for="strand-{tIdx}">Strand <span class="required">*</span></label>
						<input id="strand-{tIdx}" type="text" placeholder='e.g. "Paper 1"' bind:value={topics[tIdx].strand} />
					</div>
					<div class="form-field">
						<label for="topic-name-{tIdx}">Topic Name <span class="required">*</span></label>
						<input id="topic-name-{tIdx}" type="text" placeholder='e.g. "Programming"' bind:value={topics[tIdx].topic_name} />
					</div>
				</div>

				<div class="subtopics-section">
					<div class="subtopics-header">
						<strong>Subtopics</strong>
					</div>
					{#each topic.subtopics as sub, sIdx}
						<div class="subtopic-row">
							<span class="subtopic-id">{getSubtopicId(tIdx, sIdx)}</span>
							<div class="subtopic-fields">
								<input
									type="text"
									placeholder="Subtopic name"
									bind:value={topics[tIdx].subtopics[sIdx].subtopic_name}
								/>
								<input
									type="text"
									placeholder="Description (used for classification matching)"
									bind:value={topics[tIdx].subtopics[sIdx].description}
								/>
							</div>
							{#if topic.subtopics.length > 1}
								<button type="button" class="btn-remove-sub" onclick={() => removeSubtopic(tIdx, sIdx)} title="Remove subtopic">&times;</button>
							{/if}
						</div>
					{/each}
					<button type="button" class="btn-add-sub" onclick={() => addSubtopic(tIdx)}>+ Add Subtopic</button>
				</div>
			</div>
		{/each}
	</div>

	<button type="button" class="btn-submit" onclick={handleSubmit} disabled={isSubmitting}>
		{isSubmitting ? 'Creating...' : 'Create Specification'}
	</button>
</main>

<style>
	.create-spec-page {
		max-width: 800px;
	}

	.create-spec-page p {
		color: #666;
		margin: 4px 0 24px;
	}

	.error-banner {
		background: #fdecea;
		color: #8b0000;
		padding: 10px 16px;
		border-radius: 6px;
		margin-bottom: 20px;
		font-size: 0.9rem;
		border: 1px solid #f5c6cb;
	}

	.form-section {
		margin-bottom: 32px;
	}

	.form-section h2 {
		font-size: 1.15rem;
		margin-bottom: 16px;
		padding-bottom: 8px;
		border-bottom: 1px solid #eee;
	}

	.form-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		margin-bottom: 12px;
	}

	.form-field {
		margin-bottom: 12px;
	}

	.form-field label {
		display: block;
		font-weight: 600;
		font-size: 0.9rem;
		margin-bottom: 4px;
	}

	.required {
		color: #d32f2f;
	}

	.form-field input[type='text'],
	.form-field textarea {
		width: 100%;
		padding: 8px 12px;
		font-size: 0.95rem;
		border: 1px solid #ddd;
		border-radius: 6px;
	}

	.form-field input[type='text']:focus,
	.form-field textarea:focus {
		outline: none;
		border-color: #0077cc;
		box-shadow: 0 0 0 2px rgba(0, 119, 204, 0.15);
	}

	.checkbox-field label {
		display: flex;
		align-items: center;
		gap: 8px;
		font-weight: normal;
		cursor: pointer;
	}

	.checkbox-field input[type='checkbox'] {
		width: auto;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16px;
		padding-bottom: 8px;
		border-bottom: 1px solid #eee;
	}

	.section-header h2 {
		margin: 0;
		padding: 0;
		border: none;
	}

	.btn-add-topic-main {
		padding: 6px 16px;
		font-size: 0.85rem;
		background: #0077cc;
		color: white;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		width: auto;
	}

	.btn-add-topic-main:hover {
		background: #005fa3;
	}

	.topic-card {
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		padding: 16px 20px;
		margin-bottom: 16px;
		background: #fafafa;
	}

	.topic-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
	}

	.topic-number {
		font-weight: 700;
		font-size: 0.95rem;
		color: #0077cc;
	}

	.btn-remove-topic {
		padding: 4px 12px;
		font-size: 0.8rem;
		background: none;
		border: 1px solid #ddd;
		border-radius: 4px;
		color: #d32f2f;
		cursor: pointer;
		width: auto;
	}

	.btn-remove-topic:hover {
		background: #fdecea;
		border-color: #f5c6cb;
	}

	.topic-fields {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}

	.subtopics-section {
		margin-top: 16px;
	}

	.subtopics-header {
		font-size: 0.9rem;
		margin-bottom: 8px;
	}

	.subtopic-row {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin-bottom: 8px;
	}

	.subtopic-id {
		font-family: monospace;
		font-size: 0.85rem;
		color: #888;
		min-width: 28px;
		padding-top: 10px;
	}

	.subtopic-fields {
		flex: 1;
		display: flex;
		gap: 8px;
	}

	.subtopic-fields input {
		flex: 1;
		padding: 8px 12px;
		font-size: 0.9rem;
		border: 1px solid #ddd;
		border-radius: 6px;
	}

	.subtopic-fields input:focus {
		outline: none;
		border-color: #0077cc;
		box-shadow: 0 0 0 2px rgba(0, 119, 204, 0.15);
	}

	.btn-remove-sub {
		background: none;
		border: none;
		color: #999;
		font-size: 1.2rem;
		cursor: pointer;
		padding: 6px 8px;
		width: auto;
		line-height: 1;
	}

	.btn-remove-sub:hover {
		color: #d32f2f;
	}

	.btn-add-sub {
		padding: 4px 12px;
		font-size: 0.8rem;
		background: none;
		border: 1px dashed #bbb;
		border-radius: 4px;
		color: #666;
		cursor: pointer;
		width: auto;
	}

	.btn-add-sub:hover {
		border-color: #0077cc;
		color: #0077cc;
	}

	.btn-submit {
		padding: 14px 32px;
		font-size: 1.05rem;
		background: #0077cc;
		color: white;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		width: 100%;
		margin-top: 8px;
	}

	.btn-submit:hover {
		background: #005fa3;
	}

	.btn-submit:disabled {
		background: #999;
		cursor: not-allowed;
	}

	@media (max-width: 600px) {
		.form-grid,
		.topic-fields {
			grid-template-columns: 1fr;
		}

		.subtopic-fields {
			flex-direction: column;
		}
	}
</style>
