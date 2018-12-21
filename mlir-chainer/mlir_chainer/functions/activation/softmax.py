from chainer.functions.activation.softmax import Softmax
from mlir_chainer.patch import patched_function_apply, patched_function_call
import mlir.edges as MLIR

if hasattr(Softmax, 'apply'):
    Softmax.apply = patched_function_apply(Softmax.apply)
else:
    Softmax.__call__ = patched_function_call(Softmax.__call__)

def to_mlir_node(self, inputs, outputs):
    return MLIR.Softmax(inputs, outputs, axis=self.axis)
Softmax.to_mlir_node = to_mlir_node