class ComponentError(Exception):
    """Base exception for all Manual-To-UML errors."""
    pass

class ParseError(ComponentError):
    """Raised when there's an error parsing the Guard DSL."""
    def __init__(self, message: str, position: int = -1):
        super().__init__(f"{message} (position: {position})")
        self.message = message
        self.position = position
        
class MtuValidationError(ComponentError):
    """Raised when there's an IBR validation logic failure not caught by Pydantic."""
    pass
