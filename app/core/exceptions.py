class CVOptimizerError(Exception):
    pass


class ParseError(CVOptimizerError):
    pass


class ValidationError(CVOptimizerError):
    pass


class ContextError(CVOptimizerError):
    pass


class MatchError(CVOptimizerError):
    pass


class RewriteError(CVOptimizerError):
    pass


class JobNotFoundError(CVOptimizerError):
    pass
