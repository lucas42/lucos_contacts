lucos.addMenuItem('Admin', 'http://contacts.l42.eu/admin');
lucos.addMenuItem('My Page', '/agents/me');

lucos.waitFor('ready', function _contactsDOMReady() {
	if (document.getElementById('title')) document.body.removeChild(document.getElementById('title'));
});
