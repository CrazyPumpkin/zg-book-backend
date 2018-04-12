class KwargsContextMixin:
    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "kwagrs": self.kwargs
        }
