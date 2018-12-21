import heapq
import msgpack
import chainer
import numpy as np
from chainer import variable
from chainer import function_node
import chainer.functions as F

class Node(object):
    def __init__(self, node, no = None):
        self.no = no
        self.node = node
        self.in_edges = None
        self.out_edges = None
    def __hash__(self):
        return id(self.node).__hash__()
    def __eq__(self, r):
        return self.node is r.node
    def add_in_edge(self, from_node):
        if self.in_edges is None: self.in_edges = []
        self.in_edges.append(from_node)
    def add_out_edge(self, to_node):
        if self.out_edges is None: self.out_edges = []
        self.out_edges.append(to_node)
    def is_type_of(self, cls):
        return isinstance(self.node, cls)

class Graph(object):
    def __init__(self, model, input_variables, output_variables):
        self.input_variables = []
        self.output_variables = []
        self.nodes = set()
        self.model = model

        push_count = [0]
        candidates = []
        def add_candidate(candidate):
            heapq.heappush(candidates, (push_count[0], candidate))
            push_count[0] += 1

        n2N = {}
        created_order = [0]
        def create_node(node):
            if id(node) in n2N:
                return n2N[id(node)]
            else:
                n2N[id(node)] = Node(node, created_order[0])
                created_order[0] += 1
                return n2N[id(node)]

        out2link = {}
        for child in model.children():
            if hasattr(child, 'chainer_output_variables'):
                out2link.update({id(o): child for o in child.chainer_output_variables})

        # Create graph
        seen_edges = set()
        for o in output_variables:
            add_candidate(o)
            o_node = create_node(o)
            self.nodes.add(o_node)
            self.output_variables.append(o_node)
        while candidates:
            _, candidate = heapq.heappop(candidates)
            if isinstance(candidate, variable.Variable):
                creator = None
                if id(candidate) in out2link:
                    creator = out2link[id(candidate)]
                else:
                    creator = candidate.creator
                if hasattr(creator, 'caller') and creator.caller is not None:
                    creator = creator.caller
                if creator is not None and (id(creator), id(candidate)) not in seen_edges:
                    add_candidate(creator)
                    seen_edges.add((id(creator), id(candidate)))
                    creator_node = create_node(creator)
                    candidate_node = create_node(candidate)
                    candidate_node.add_in_edge(creator_node)
                    creator_node.add_out_edge(candidate_node)
                    self.nodes.add(creator_node)
            else:
                for input_ in reversed(candidate.chainer_input_variables):
                    if input_ is not candidate and (id(input_), id(candidate)) not in seen_edges:
                        add_candidate(input_)
                        seen_edges.add((id(input_), id(candidate)))
                        input_node = create_node(input_)
                        candidate_node = create_node(candidate)
                        candidate_node.add_in_edge(input_node)
                        input_node.add_out_edge(candidate_node)
                        self.nodes.add(input_node)
        for i in input_variables:
            self.input_variables.append(create_node(i))

        # Topological sorting
        visited = set()
        sorted_nodes = []
        def visit(node):
            if node not in visited:
                visited.add(node)
                if node.out_edges is not None:
                    for n in node.out_edges:
                        visit(n)
                sorted_nodes.insert(0, node)
        for node in sorted(self.nodes, key=lambda n: n.no):
            visit(node)
        for no, node in enumerate(sorted_nodes):
            node.no = no

    def to_mlir(self, name=None):
        def _node(node):
            return { b'name': self._variable_elem_name(node),
                     b'dtype': node.node.dtype.str, # TODO: エンディアンとかが入り込むのでfloatとかでいい
                     b'shape': node.node.shape }
        def _function(node):
            return node.node.to_mlir_node(
                list(map(self._variable_elem_name, reversed(node.in_edges))),
                list(map(self._variable_elem_name, node.out_edges))
            ).dump()

        sorted_nodes = sorted(self.nodes, key=lambda n: n.no)
        inputs = map(_node, filter(lambda node: isinstance(node.node, variable.Variable), sorted_nodes))
        nodes = map(_node, filter(lambda node: isinstance(node.node, variable.Variable), sorted_nodes))
        edges = map(_function, filter(lambda node: not isinstance(node.node, variable.Variable), sorted_nodes))
        mlir = { b'mlir':
                 { b'version' : 0,
                   b'model' :
                   { b'name': name or self.model.__class__.__name__,
                     b'generator':
                     { b'name' : 'chainer',
                       b'version': chainer.__version__ },
                     b'inputs': list(map(self._variable_elem_name, self.input_variables)),
                     b'outputs': list(map(self._variable_elem_name, self.output_variables)),
                     b'nodes': list(nodes),
                     b'edges': list(edges) } } }
        return msgpack.packb(mlir)

    def _variable_elem_name(self, node):
        return "v%s%d" % ('' if node.node.name is None else node.node.name, node.no)

    def _variable_name(self, node):
        return "v%s%d %s" % ('' if node.node.name is None else node.node.name, node.no, node.node.shape)

    def _function_name(self, node):
        in_edges = '|'.join(map(lambda v: '<' + self._variable_elem_name(v) + '>', reversed(node.in_edges)))
        out_edges = '|'.join(map(lambda v: '<' + self._variable_elem_name(v) + '>', reversed(node.out_edges)))
        params = node.node.to_mlir_node()[b'params']
        aps = params.keys()
        def find_params(params):
            for k,v in params.items():
                if type(v) is dict and b'ndarray' in v:
                    yield k.decode()
                elif type(v) is dict:
                    yield k.decode()
                else:
                    yield str(v)
        return "{{%s}|%s %s|{%s}}" % (in_edges, type(node.node).__name__, ' '.join(find_params(params)), out_edges)

    def to_dot(self, variable_style = None, function_style = None, rankdir = 'TB'):
        ret = 'digraph graphname { rankdir=%s;\n' % rankdir
        ret += '  subgraph input {\n'
        for i, node in enumerate(self.input_variables):
            attribute = { 'xlabel' : 'input%d = %s' % (i, self._variable_name(node)),
                          'shape' : 'point' }
            attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                          in attribute.items()]
            ret += "    %s [%s];\n" % (id(node.node), ",".join(attributes))
        ret += '  }\n'
        ret += '  subgraph output {\n'
        for i, node in enumerate(self.output_variables):
            attribute = { 'xlabel' : 'output%d = %s' % (i, self._variable_name(node)),
                          'shape' : 'point' }
            attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                          in attribute.items()]
            ret += "    %s [%s];\n" % (id(node.node), ",".join(attributes))
        ret += '  }\n'
        for node in self.nodes:
            if node in self.input_variables:
                continue
            if node in self.output_variables:
                continue
            # assert isinstance(node.node, (variable.Variable, function.Function))
            if isinstance(node.node, variable.Variable):
                attribute = { 'xlabel' : self._variable_name(node),
                              'shape' : 'point' }
                attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                              in attribute.items()]
                ret += "  %s [%s];\n" % (id(node.node), ",".join(attributes))
            elif isinstance(node.node, function_node.FunctionNode):
                attribute = { 'label' : self._function_name(node),
                              'shape': 'record',
                              'style' : 'filled',
                              'fillcolor' : 'aquamarine' }
                attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                              in attribute.items()]
                ret += "  %s [%s];\n" % (id(node.node), ",".join(attributes))
            else:
                attribute = { 'label' : self._function_name(node),
                              'shape': 'record',
                              'style' : 'filled',
                              'fillcolor' : 'cyan' }
                attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                              in attribute.items()]
                ret += "  %s [%s];\n" % (id(node.node), ",".join(attributes))
        for from_node in self.nodes:
            if from_node.out_edges is None: continue
            for to_node in from_node.out_edges:
                if isinstance(from_node.node, variable.Variable):
                    ret += '  %s -> %s:%s;\n' % (id(from_node.node), id(to_node.node), self._variable_elem_name(from_node))
                else:
                    ret += '  %s:%s -> %s;\n' % (id(from_node.node), self._variable_elem_name(to_node), id(to_node.node))


        ret += '  { rank = same; \n'
        for node in self.input_variables:
            attribute = { 'xlabel' : self._variable_name(node),
                          'shape' : 'point' }
            attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                          in attribute.items()]
            ret += "    %s;\n" % (id(node.node))
        ret += '  }\n'
        ret += '  { rank = same; \n'
        for node in self.output_variables:
            attribute = { 'xlabel' : self._variable_name(node),
                          'shape' : 'point' }
            attributes = ["%s=\"%s\"" % (k, v) for (k, v)
                          in attribute.items()]
            ret += "    %s;\n" % (id(node.node))
        ret += '  }\n'
        ret += "}"
        return ret

    def _variable_elem_name(self, node):
        return "v%s%d" % ('' if node.node.name is None else node.node.name, node.no)