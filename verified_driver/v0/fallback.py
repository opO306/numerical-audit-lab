"""No stronger production path is registered for V0."""
class FallbackRegistry:
    def resolve(self,reason,context):
        return None
