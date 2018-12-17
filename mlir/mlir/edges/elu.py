import chainer.functions as F
from .edge import Edge
import numpy as np

class ELU(Edge):
    def __init__(self, inputs, outputs, **params):
        required_params = {'alpha'}
        optional_params = set()
        super(ELU, self).__init__(inputs, outputs, params, required_params, optional_params)
    def run(self, x):
        R = x.copy()
        v = R < 0
        R[v] = self.params['alpha'] * (np.exp(R[v]) - 1)
        return R
