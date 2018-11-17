# -*- coding: utf-8 -*-
import msgpack
import sys
import six
import numpy

def function_label(edge):
    ret = '{{%s|' % edge[b'name'].decode()
    ret += '|'.join(map(lambda v: '<' + v.decode() + '>', reversed(edge[b'inputs'])))
    if (b'W' in edge[b'params']):
        ret += '|W'
    if (b'b' in edge[b'params']):
        ret += '|b'
    ret += '}'
    def find_params(params):
        for k,v in params.items():
            if type(v) is dict: # assert W or b
                array = numpy.load(six.BytesIO(v[b'ndarray']))
                yield k.decode() + " shape: " + str(array.shape)
            else:
                yield k.decode() + ": " + str(v)
    params_str = '&#92;n'.join(find_params(edge[b'params']))
    if params_str != "":
        ret += '|{%s}' % params_str
    ret += '|{%s}}' % '|'.join(map(lambda v: '<' + v.decode() + '>', reversed(edge[b'outputs'])))
    return ret

def function_name(edge):
    in_edges = ''.join(map(lambda v: v.decode(), reversed(edge[b'inputs'])))
    out_edges = ''.join(map(lambda v: v.decode(), reversed(edge[b'outputs'])))
    return "%s_%s_%s" % (edge[b'name'].decode(), in_edges, out_edges)

def node_name(node):
    return "%s %s" % (node[b'name'].decode(), tuple(node[b'shape']))

def to_dot(mlir, rankdir = 'TB'):
    inputs = mlir[b'mlir'][b'model'][b'inputs']
    outputs = mlir[b'mlir'][b'model'][b'outputs']
    nodes = mlir[b'mlir'][b'model'][b'nodes']
    edges = mlir[b'mlir'][b'model'][b'edges']

    ret = 'digraph graphname { rankdir=%s;\n' % rankdir
    ret += '  subgraph input {\n'
    for i, var in enumerate(inputs):
        attribute = { 'xlabel' : 'input%d = %s' % (i, var.decode()),
                      'shape' : 'point' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "    %s [%s];\n" % (var.decode(), ",".join(attributes))
    ret += '  }\n'
    ret += '  subgraph output {\n'
    for i, var in enumerate(outputs):
        attribute = { 'xlabel' : 'output%d = %s' % (i, var.decode()),
                      'shape' : 'point' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "    %s [%s];\n" % (var.decode(), ",".join(attributes))
    ret += '  }\n'
    for node in nodes:
        if node[b'name'] in inputs:
            continue
        if node[b'name'] in outputs:
            continue
        attribute = { 'xlabel' : node_name(node),
                      'shape' : 'point' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "  %s [%s];\n" % (node[b'name'].decode(), ",".join(attributes))
    for edge in edges:
        # output function
        attribute = { 'label' : function_label(edge),
                      'shape': 'record',
                      'style' : 'filled',
                      'fillcolor' : 'aquamarine' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "  %s [%s];\n" % (function_name(edge), ",".join(attributes))
        # output edges
        for from_node in edge[b'inputs']:
            ret += '  %s -> %s:%s[constraint=false];' % (from_node.decode(), function_name(edge), from_node.decode())
            ret += '  %s -> %s[color="transparent"];\n' % (from_node.decode(), function_name(edge))
        for to_node in edge[b'outputs']:
            ret += '  %s:%s -> %s[constraint=false];' % (function_name(edge), to_node.decode(), to_node.decode())
            ret += '  %s -> %s[color="transparent"];\n' % (function_name(edge), to_node.decode())

    ret += '  { rank = same; \n'
    for var in inputs:
        attribute = { 'xlabel' : var.decode(),
                      'shape' : 'point' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "    %s;\n" % (var.decode())
    ret += '  }\n'
    ret += '  { rank = same; \n'
    for var in outputs:
        attribute = { 'xlabel' : var.decode(),
                      'shape' : 'point' }
        attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                      in attribute.items()]
        ret += "    %s;\n" % (var.decode())
    ret += '  }\n'
    ret += "}"
    return ret

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: python mlir_drawer.py mlir_file")
        exit()
    mlir_file = sys.argv[1]
    with open(mlir_file, 'rb') as f:
        mlir = msgpack.unpackb(f.read())
        result = to_dot(mlir)
        six.print_(result)