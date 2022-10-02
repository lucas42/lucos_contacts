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