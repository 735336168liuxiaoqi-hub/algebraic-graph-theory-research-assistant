from graph_research.hypergraphs import Hypergraph


class NativeBackend:
    """Drop-in mathematical backend for the original JSON experiment pipeline."""
    def __call__(self, request):
        graph = Hypergraph(request["edges"])
        result = graph.alpha_spectrum(request["alpha"], seed=request.get("seed", 42))
        if request.get("weighted_incidence", False):
            matrix = graph.weighted_incidence_from_result(result)
            result["weighted_incidence"] = matrix.tolist()
            result["weighted_incidence_display"] = matrix.tolist()
            result["weighted_incidence_note"] = "Native full-precision values; no legacy rounding"
        return result
