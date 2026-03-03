<div class="page">
	<div class="container">
		<header class="page-header">
			<h1>Privacy Policy</h1>
			<p class="subtitle">Last updated: 3 March 2026</p>
		</header>

		<div class="content">
			<section>
				<h2>1. Overview</h2>
				<p>
					Topic Tracker ("we", "us", "our") is an AI-powered exam paper analysis tool that helps
					students identify weak areas and track revision progress. This policy explains what data we
					collect, how we use it, and your rights.
				</p>
			</section>

			<section>
				<h2>2. Data We Collect</h2>

				<h3>Account information</h3>
				<p>
					When you sign in with Google or email, we receive your email address and display name via
					Supabase Authentication. We do not receive or store your Google password.
				</p>

				<h3>Exam content</h3>
				<p>
					Questions you submit (typed text or uploaded PDFs) are processed to classify them by topic.
					The extracted question text and classification results are stored in our database linked to
					your account.
				</p>

				<h3>Guest sessions</h3>
				<p>
					If you use the app without signing in, a random ID is stored in your browser's
					<code>localStorage</code> to associate your sessions. This data is not linked to any
					personal identity unless you later create an account, at which point it is migrated to your
					account.
				</p>

				<h3>Usage data</h3>
				<p>
					We do not use third-party analytics trackers. Standard server logs (timestamp,
					request path) may be retained for up to 30 days for security and debugging purposes.
				</p>
			</section>

			<section>
				<h2>3. How We Use Your Data</h2>
				<ul>
					<li>To classify exam questions against specification topics</li>
					<li>To display your revision history and analytics</li>
					<li>To authenticate your account securely</li>
					<li>To migrate guest sessions to your account on sign-up</li>
				</ul>
				<p>We do and will not sell, rent, or share your personal data with third parties for marketing.</p>
			</section>

			<section>
				<h2>4. Third-Party Services</h2>
				<ul>
					<li>
						<strong>Supabase</strong> — authentication and database hosting. Supabase processes your
						email and session tokens.
						<a href="https://supabase.com/privacy" target="_blank" rel="noopener noreferrer"
							>Supabase Privacy Policy</a
						>.
					</li>
					<li>
						<strong>Google OAuth</strong> — optional sign-in method. Only your email and public
						profile name are shared with us.
						<a
							href="https://policies.google.com/privacy"
							target="_blank"
							rel="noopener noreferrer">Google Privacy Policy</a
						>.
					</li>
					<li>
						<strong>Google Gemini API</strong> — used to extract questions from uploaded PDFs. PDF
						content is sent to Google's API for processing and is subject to
						<a
							href="https://ai.google.dev/gemini-api/terms"
							target="_blank"
							rel="noopener noreferrer">Google's API Terms</a
						>.
					</li>
				</ul>
			</section>

			<section>
				<h2>5. Data Retention</h2>
				<p>
					Your account data and exam sessions are retained for as long as your account is active. You
					may delete your account and all associated data at any time by contacting us. Guest session
					data with no associated account may be deleted after 90 days of inactivity.
				</p>
			</section>

			<section>
				<h2>6. Your Rights</h2>
				<p>You have the right to:</p>
				<ul>
					<li>Access the personal data we hold about you</li>
					<li>Request correction of inaccurate data</li>
					<li>Request deletion of your account and data</li>
					<li>Withdraw consent at any time (e.g. by deleting your account)</li>
				</ul>
				<p>To exercise any of these rights, contact us at the address below.</p>
			</section>

			<section>
				<h2>7. Cookies</h2>
				<p>
					We use only essential cookies and browser storage required for authentication (Supabase
					session tokens) and guest session tracking (<code>localStorage</code>). We do not use
					advertising or tracking cookies.
				</p>
			</section>

			<section>
				<h2>8. Children's Privacy</h2>
				<p>
					If you create an account with topic tracker, you must be at least 13 years old as this collects your email address. We do not knowingly collect personal data from children under 13. If we become aware that we have collected data from a child under 13, we will delete it immediately. The app may be used without an account at any age.
				</p>
			</section>

			<section>
				<h2>9. Changes to This Policy</h2>
				<p>
					We may update this policy from time to time. The date at the top of this page reflects the
					latest revision. Continued use of the service after changes constitutes acceptance of the
					updated policy.
				</p>
			</section>

			<section>
				<h2>10. Contact</h2>
				<p>
					If you have questions about this policy or wish to exercise your data rights, please open an
					issue or contact us via the project repository at <a href="https://github.com/kdlegum/topic-classifier" target="_blank" rel="noopener noreferrer">https://github.com/kdlegum/topic-classifier</a>.
				</p>
			</section>
		</div>
	</div>
</div>

<style>
	.page {
		padding: 2rem 1rem 4rem;
	}

	.container {
		max-width: 720px;
		margin: 0 auto;
	}

	.page-header {
		margin-bottom: 2.5rem;
		padding-bottom: 1.5rem;
		border-bottom: 2px solid var(--color-border);
	}

	h1 {
		font-family: var(--font-heading);
		font-size: 2rem;
		color: var(--color-text);
		margin: 0 0 0.5rem;
	}

	.subtitle {
		color: var(--color-text-muted);
		font-size: 0.9rem;
		margin: 0;
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	section {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	h2 {
		font-family: var(--font-heading);
		font-size: 1.15rem;
		color: var(--color-text);
		margin: 0;
	}

	h3 {
		font-size: 0.95rem;
		font-weight: 700;
		color: var(--color-text);
		margin: 0.25rem 0 0;
	}

	p {
		color: var(--color-text-secondary);
		line-height: 1.7;
		margin: 0;
	}

	ul {
		color: var(--color-text-secondary);
		line-height: 1.7;
		margin: 0;
		padding-left: 1.4rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	a {
		color: var(--color-primary);
		text-decoration: none;
	}

	a:hover {
		color: var(--color-primary-hover);
		text-decoration: underline;
	}

	code {
		font-size: 0.875em;
		background: var(--color-surface-alt);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-sm);
		padding: 0.1em 0.4em;
		color: var(--color-text);
	}
</style>
