<svelte:head>
	<title>How It Works - Topic Tracker</title>
</svelte:head>

<!-- todo: Add more help content for each individual page-->

<div class="page-content help-page">
	<h1>What is this website for?</h1>

	<h3 class="intro">
		On Topic Tracker, you can make a personal collection of questions from past papers and use them to revise effectively!
	</h3>

	<h1>How to Use</h1>

	<div class="steps">
		<div class="step">
			<div class="step-number">1</div>
			<div class="step-body">
				<h3>Upload questions or select a Past Paper</h3>
				<p>
					Go to <strong>Classify</strong> and choose your exam board and specification.
					Then either upload a past paper PDF, paste questions, or select a past paper from the list.
				</p>
			</div>
		</div>

		<div class="step">
			<div class="step-number">2</div>
			<div class="step-body">
				<h3>AI classifies each question</h3>
				<p>
					The system uses AI to match each question to the most relevant topics and subtopics
					from your specification. You'll see the top predictions ranked by confidence.
				</p>
			</div>
		</div>

		<div class="step">
			<div class="step-number">3</div>
			<div class="step-body">
				<h3>Review and correct</h3>
				<p>
					Check the predicted topics. If something's wrong, you can correct it - 
					pick the right topic from the spec using the quick-select buttons or the dropdown.
				</p>
			</div>
		</div>

		<div class="step">
			<div class="step-number">4</div>
			<div class="step-body">
				<h3>Track your marks</h3>
				<p>
					Enter the marks you scored on each question. Topic Tracker will calculate
					your performance by topic so you can see where you're strong and where you need work.
				</p>
			</div>
		</div>

		<div class="step">
			<div class="step-number">5</div>
			<div class="step-body">
				<h3>See your weak spots</h3>
				<p>
					Head to <strong>Analytics</strong> to see a breakdown of your performance by topic
					across all the papers you've done. Focus your revision where it matters most.
				</p>
			</div>
		</div>

		<div class="step">
			<div class="step-number">6</div>
			<div class="step-body">
				<h3>Revise with targeted practice</h3>
				<p>
					Go to <strong>Revision</strong> to practise questions from your weak topics.
					It pulls questions from past papers you've done and prioritises the ones you
					scored lowest on, so you're always working on what needs the most attention.
				</p>
			</div>
		</div>
	</div>

	<div class="faq">
		<h2>Common Questions</h2>

		<details>
			<summary>How do I mark my work?</summary>
			<p>Topic Tracker doesn't mark your work for you. If you use a past paper, it will get the mark scheme pdf for you. Click the mark scheme button to open the mark scheme in a new tab to check your answers.</p>
		</details>

		<details>
			<summary>Which exam boards are supported?</summary>
			<p>Currently most major OCR, Edexcel and AQA GCSE and A Level specifications. Check the <strong>Specs</strong> page to browse available specifications and their topic structures. You can still use the website for all exam boards by using the no specification option, or you can make your own spec in the <strong>Specs</strong> page.</p>
		</details>

		<details>
			<summary>Do I need to create an account?</summary>
			<p>No, you can use Topic Tracker as a guest. Your sessions are saved locally. If you sign in later, your guest sessions will be migrated to your account so nothing is lost.</p>
		</details>

		<details>
			<summary>How does the AI classification work?</summary>
			<p>Each question is compared against every subtopic in your specification using semantic similarity. The system finds the subtopics whose descriptions most closely match the meaning of the question, not just keyword matching.</p>
		</details>

		<details>
			<summary>What if the AI gets a topic wrong?</summary>
			<p>You can correct any prediction. Click the quick-select button next to a prediction to choose it, or use "Choose topic manually" to pick the exact subtopic from the spec hierarchy.</p>
		</details>

		<details>
			<summary>Can I upload scanned papers?</summary>
			<p>Yes. PDFs are processed with OCR to extract the text, then an AI model identifies individual questions from the document. It works with both digital and scanned papers.</p>
		</details>

		<details>
			<summary>What are optional modules / strands?</summary>
			<p>Some specifications (like OCR Computer Science) have optional modules. You can select which modules you're studying in the Classify page, and the system will only classify against those topics.</p>
		</details>

		<details>
			<summary>What is your privacy policy?</summary>
			<p>See our <a href="/privacy">Privacy Policy</a> for more information. In summary, I do not collect any data except from local storage to save your progress and your email for those who made an account - this is why under 13s may not make an account, but they can use the website as a guest.</p>
		</details>
	</div>
</div>

<style>
	.help-page {
		max-width: 700px;
	}

	.intro {
		font-size: 1.1rem;
		color: var(--color-text-primary);
		margin-bottom: 36px;
		line-height: 1.7;
	}

	.steps {
		display: flex;
		flex-direction: column;
		gap: 20px;
		margin-bottom: 48px;
	}

	.step {
		display: flex;
		gap: 16px;
		align-items: flex-start;
		padding: 18px 20px;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-sm);
	}

	.step-number {
		flex-shrink: 0;
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--color-primary);
		color: white;
		font-weight: 700;
		font-size: 1rem;
		border-radius: 50%;
	}

	.step-body h3 {
		margin: 0 0 4px;
		font-size: 1rem;
	}

	.step-body p {
		margin: 0;
		color: var(--color-text-secondary);
		font-size: 0.95rem;
		line-height: 1.6;
	}

	.faq {
		margin-bottom: 48px;
	}

	.faq h2 {
		margin-bottom: 16px;
	}

	details {
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-md);
		margin-bottom: 8px;
		overflow: hidden;
	}

	summary {
		padding: 14px 18px;
		font-weight: 600;
		font-size: 0.95rem;
		cursor: pointer;
		list-style: none;
		display: flex;
		align-items: center;
		gap: 10px;
		transition: background var(--transition-fast);
	}

	summary:hover {
		background: var(--color-surface-alt);
	}

	summary::before {
		content: '+';
		flex-shrink: 0;
		width: 22px;
		height: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--color-primary);
		border: 1.5px solid var(--color-border);
		border-radius: 50%;
		transition: transform var(--transition-fast), background var(--transition-fast);
	}

	details[open] summary::before {
		content: '\2212';
		background: var(--color-primary);
		color: white;
		border-color: var(--color-primary);
	}

	summary::-webkit-details-marker {
		display: none;
	}

	details p {
		padding: 0 18px 14px 50px;
		margin: 0;
		color: var(--color-text-secondary);
		font-size: 0.93rem;
		line-height: 1.6;
	}
</style>
