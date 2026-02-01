import { getCurrentUser, signOut, onAuthChange } from "./auth.js";

/**
 * Render the navigation header
 * @param {string} containerId - ID of the container element to render nav into
 */
export async function renderNav(containerId) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`Nav container '${containerId}' not found`);
    return;
  }

  const user = await getCurrentUser();
  container.innerHTML = createNavHtml(user);

  // Attach event listeners
  const logoutBtn = container.querySelector("#nav-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      await signOut();
      window.location.href = "/";
    });
  }

  // Subscribe to auth changes to update nav
  onAuthChange(async (user) => {
    container.innerHTML = createNavHtml(user);
    // Re-attach logout listener after re-render
    const logoutBtn = container.querySelector("#nav-logout");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        await signOut();
        window.location.href = "/";
      });
    }
  });
}

function createNavHtml(user) {
  const currentPath = window.location.pathname;

  const isClassify = currentPath === "/classify" || currentPath === "/classify.html";
  const isHistory = currentPath === "/history" || currentPath === "/history.html";

  const userDisplay = user ? user.email : "Guest";

  return `
    <nav class="main-nav">
      <div class="nav-brand">
        <a href="/classify">Topic Tracker</a>
      </div>
      <div class="nav-links">
        <a href="/classify" class="${isClassify ? "active" : ""}">Classify</a>
        <a href="/history" class="${isHistory ? "active" : ""}">My Sessions</a>
      </div>
      <div class="nav-user">
        <span class="user-display">${userDisplay}</span>
        ${user
          ? `<a href="#" id="nav-logout" class="nav-btn">Log out</a>`
          : `<a href="/" class="nav-btn">Log in</a>`
        }
      </div>
    </nav>
  `;
}
