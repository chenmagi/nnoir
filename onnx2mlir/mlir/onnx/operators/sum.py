import functools
from mlir.edges import *
from .utils import *

class OpSum(Op):

    def __init__(self, node):
        super().__init__(node)

    def get_dummy_output(self, env):
        xs = map(lambda x: env[x], self.node.input)
        return functools.reduce(lambda a,b: a+b, xs)

    def to_Edge(self, env, constants):
        if len(self.node.input) != 2:
            raise UnsupportedONNXOperation(self.node, '# of inputs must be 2')
        return [ Add(list(self.node.input), list(self.node.output)) ]
