from util import hook
from util.execute import eval_py


@hook.command
def python(inp):
    """python <prog> -- Executes <prog> as Python code."""

    return eval_py(inp)
