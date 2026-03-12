## Content Negotiation utility functions

# Mapping MIME types to rdflib serialization format
RDF_FORMATS = {
	"text/turtle": "turtle",
	"application/ld+json": "json-ld",
	"application/rdf+xml": "xml",
	"application/n-triples": "nt",
	"application/xml": "xml",  # Sometimes used for RDF/XML
}

def parse_accept_header(request):
	"""
	Parses an Accept header and returns a list of (mime, qvalue) sorted by qvalue descending.
	"""
	accept = request.headers.get('Accept', '')
	parts = accept.split(",")
	mimes = []
	for part in parts:
		subparts = part.split(";")
		mime = subparts[0].strip()
		q = 1.0
		for sub in subparts[1:]:
			if sub.strip().startswith("q="):
				try:
					q = float(sub.strip()[2:])
				except ValueError:
					pass
		mimes.append((mime, q))
	mimes.sort(key=lambda tup: tup[1], reverse=True)
	return mimes


def negotiate_response_format(request):
	"""
	Determines the best response format based on the Accept header.

	Returns a tuple of (format, rdf_info) where:
	  - format is one of "json", "rdf", or "html"
	  - rdf_info is a (rdflib_format, content_type) tuple when format is "rdf", else None

	Priority: json > rdf > html. Explicit q-values are respected.
	*/* falls through to "html".
	"""
	parsed = parse_accept_header(request)
	json_weight = 0
	html_weight = 0
	rdf_weight = 0
	best_rdf_mime = None

	for mime, q in parsed:
		if mime == "application/json":
			if q > json_weight:
				json_weight = q
		elif mime == "text/html":
			if q > html_weight:
				html_weight = q
		elif mime in RDF_FORMATS:
			if q > rdf_weight:
				rdf_weight = q
				best_rdf_mime = mime

	if json_weight > 0 and json_weight >= html_weight and json_weight >= rdf_weight:
		return "json", None

	if rdf_weight > 0 and rdf_weight >= html_weight:
		rdflib_format = RDF_FORMATS[best_rdf_mime]
		return "rdf", (rdflib_format, best_rdf_mime)

	return "html", None
