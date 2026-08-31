function bindStars(root) {
	root.querySelectorAll(".star").forEach(star => {
		star.addEventListener("click", async event => {
			star.classList.add("loading");
			event.preventDefault();
			const agentid = star.dataset.agentid;
			const wasStarred = star.dataset.starred == "True";
			const toStar = !wasStarred;

			try {
				const response = await fetch(`/people/${agentid}/starred`, {
					method: 'PUT',
					body: toStar
				});
				if (response.status !== 200) {
					throw `Returned ${response.status} status code`;
				}
				star.dataset.starred = await response.text();
				star.classList.remove("loading");
				star.classList.add("changed", "changed-transition");
				setTimeout(() => star.classList.remove("changed"), 500);
				setTimeout(() => star.classList.remove("changed-transition"), 5000);
			}
			catch (error) {
				star.classList.remove("loading");
				star.classList.add("failed");
				console.error("Failed to update star", error);
			}
		});
	});
}

function bindContentLinks(root) {
	root.querySelectorAll(".content a").forEach(link => {
		link.target = "_blank";
	});
	root.querySelectorAll(".agenttable .name a").forEach(link => {
		link.href += "#giftideas";
	});
}

bindStars(document);
bindContentLinks(document);


class LanguageSelector extends HTMLElement {
	constructor() {
		super();
		const shadow = this.attachShadow({ mode: 'closed' });
		const languages = JSON.parse(this.getAttribute("languages"));
		const currentLanguage = this.getAttribute("current-language");
		const endpoint = this.getAttribute("endpoint");
		const csrfToken = document.cookie
			.split('; ')
			.find((row) => row.startsWith('csrftoken='))
			?.split('=')[1];

		const style = document.createElement('style');
		style.textContent = `
			:host {
				float: right;
				font-size: smaller;
				color: #ccc;
			}
			a {
				cursor: pointer;
				font-weight: normal;
				text-decoration: none;
			}
			a:hover {
				text-decoration: underline;
			}
			a.current {
				font-weight: bold;
				color: #cfc;
			}
			a.loading {
				opacity: 0.2;
				cursor: wait;
			}
		`;
		shadow.append(style);

		const languageList = document.createElement('span');

		languages.forEach(language => {
			if (languageList.firstChild) languageList.append(" | ");
			const languageLink = document.createElement('a');
			languageLink.append(language.code);
			languageLink.setAttribute("title", language.name_local);
			const isCurrent = (language.code == currentLanguage);
			if (isCurrent) languageLink.classList.add("current");
			languageLink.addEventListener("click", async event => {
				languageLink.classList.add("loading");
				await fetch(endpoint, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/x-www-form-urlencoded',
						'X-CSRFToken': csrfToken,
					},
					body: `language=${language.code}`,
				});
				navigation.reload();

				/* 
					TODO: Could probably do some more error handling here.
					However, django's setlang endpoint tends to fail silently,
					so quite hard to detect.
				*/
			});
			languageList.append(languageLink);
		});

		shadow.append(languageList);
	}
}
customElements.define('language-selector', LanguageSelector);

const searchForm = document.querySelector("#contact-search-form");
if (searchForm) {
	const searchInput = searchForm.querySelector("input[name=q]");
	const searchError = document.getElementById("contact-search-error");
	let debounceTimer;
	let requestSeq = 0;

	// The plain <form> submit button is only needed as a no-JS fallback —
	// once this debounced auto-search logic is running, it's redundant
	// clutter (results already update as you type).
	const submitButton = searchForm.querySelector("button[type=submit]");
	if (submitButton) submitButton.hidden = true;

	// pushHistory=false and an explicit url are used by the popstate/pageshow
	// handlers below, which are re-fetching a URL the browser already
	// navigated to rather than producing a new one from the input's current
	// value.
	const fetchResults = async ({ pushHistory = true, url = null } = {}) => {
		const targetUrl = url || new URL(window.location.href);
		if (!url) {
			if (searchInput.value) {
				targetUrl.searchParams.set("q", searchInput.value);
			} else {
				targetUrl.searchParams.delete("q");
			}
			targetUrl.searchParams.delete("page");

			// Typing (debounced) and pressing Enter (submit) both funnel through
			// here. If the debounced fetch already landed this exact query
			// before Enter was pressed, there's nothing left to do — most
			// importantly, don't push a second identical history entry, which
			// is what breaks the back button after "type, pause, then Enter".
			if (pushHistory && targetUrl.toString() === window.location.href) return;
		}

		// Debouncing only stops overlapping fetches from being *scheduled*; it
		// doesn't stop an earlier one still in flight. Under ordinary network
		// jitter a later request's response can arrive before an earlier one's,
		// so track which fetch is the most recent and drop any response that's
		// no longer current.
		const thisRequest = ++requestSeq;
		try {
			const response = await fetch(targetUrl);
			if (!response.ok) {
				throw `Returned ${response.status} status code`;
			}
			const html = await response.text();
			if (thisRequest !== requestSeq) return;
			const newResults = new DOMParser().parseFromString(html, "text/html").querySelector("#search-results");
			const oldResults = document.querySelector("#search-results");
			if (newResults && oldResults) {
				oldResults.replaceWith(newResults);
				bindStars(newResults);
				bindContentLinks(newResults);
			}
			if (pushHistory) {
				history.pushState({}, "", targetUrl);
			}
			if (searchError) searchError.hidden = true;
		}
		catch (error) {
			console.error("Failed to update contact search results", error);
			if (thisRequest === requestSeq && searchError) {
				searchError.textContent = searchError.dataset.errorText;
				searchError.hidden = false;
			}
		}
	};

	searchForm.addEventListener("submit", event => {
		event.preventDefault();
		clearTimeout(debounceTimer);
		fetchResults();
	});

	searchInput.addEventListener("input", () => {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(fetchResults, 300);
	});

	// A search's pushState doesn't itself re-render the page, so without this,
	// Back/Forward change the URL but leave #search-results showing whatever
	// was last fetched — the page silently desyncs from the address bar.
	const syncFromLocation = () => {
		clearTimeout(debounceTimer);
		const url = new URL(window.location.href);
		searchInput.value = url.searchParams.get("q") || "";
		fetchResults({ pushHistory: false, url });
	};
	window.addEventListener("popstate", syncFromLocation);
	// Some browsers (notably ones using the back/forward cache) restore a
	// page from bfcache without firing popstate, leaving #search-results
	// stuck on whatever was showing when the page was frozen. `pageshow`
	// with event.persisted is the standard way to catch that case too.
	window.addEventListener("pageshow", event => {
		if (event.persisted) syncFromLocation();
	});
}