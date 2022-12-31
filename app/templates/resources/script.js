document.querySelectorAll(".star").forEach(star => {
	star.addEventListener("click", async event => {
		star.classList.add("loading");
		event.preventDefault();
		const agentid = star.dataset.agentid;
		const wasStarred = star.dataset.starred == "True";
		const toStar = !wasStarred;

		try {
			const response = await fetch(`/agents/${agentid}/starred`, {
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


class LanguageSelector extends HTMLElement {
	constructor() {
		super();
		const shadow = this.attachShadow({mode: 'closed'});
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