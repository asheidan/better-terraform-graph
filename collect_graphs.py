#!/usr/bin/env python3

# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import itertools
import re
import sys
import os.path
from typing import Dict
from typing import Optional


label_re = re.compile(r'label = "(.*)\.([^."]*)"')
label_format = ('label=<'
                '<table border="0">'
                '<tr><td>'
                r'<font color="gray40" point-size="9">\1</font>'
                '</td></tr>'
                r'<tr><td>\2</td></tr>'
                '</table>>')

unwanted_patterns = (
    re.compile(r'^.* -> "\[[^]]*\] provider\.aws'),  # aws_provider_link
    re.compile(r'^.* -> "\[[^]]*\] var\.default_tags'),  # default_tags_link

    re.compile(r'^.*] provider\.aws \(close\)'),
    re.compile(r'^.*] meta\.count-boundary \(EachMode fixup\)'),

    re.compile(r'^.*] root" -> '),
)


class Node:

    node_line = re.compile(r'"\[root\] (?P<name>[^"]*)" \[(?P<attributes>[^]]*)\]')
    attribute_sep = re.compile(r' *, *')
    key_value_sep = re.compile(r' *= *')

    def __init__(self, name: str, attributes: str, graph):
        self.name = name
        self.graph = graph

        attribute_map = self._parse_attributes(attributes)

        self.label = attribute_map.pop('label')

        self.attributes = attribute_map

    @classmethod
    def valid_line(cls, line: str) -> Optional[re.Match]:
        # print(cls.__name__)
        return cls.node_line.fullmatch(line)

    @classmethod
    def from_match(cls, match, graph):
        return cls(**match.groupdict(), graph=graph)

    def _parse_attributes(self, line: str):
        return dict(self.key_value_sep.split(pair)
                    for pair in self.attribute_sep.split(line))

    def attributes_as_str(self) -> str:
        return ','.join('='.join(p) for p in self.attributes.items())

    def __str__(self) -> str:
        return f'"[{self.graph.name}] {self.name}" [label={self.label},{self.attributes_as_str()}]'


class Resource(Node):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        label_parts = self.label[1:-1].split('.')
        self.resource, self.key = label_parts[-2:]

        if self.resource.startswith('aws_'):
            self.resource = self.resource[4:]

        self.is_data = len(label_parts) == 3 and label_parts[0] == 'data'

        if len(label_parts) == 4:
            self.module_name = label_parts[1]

    @property
    def label_formatted(self):
        type_indicator = '<font color="gray60" point-size="9">data.</font>' if self.is_data else ''
        return ('<'
                '<table border="0">'
                '<tr><td>'
                f'{type_indicator}'
                f'<font color="gray40" point-size="9">{self.resource}</font>'
                '</td></tr>'
                f'<tr><td>{self.key}</td></tr>'
                '</table>>')

    def __str__(self):
        return f'"[{self.graph.name}] {self.name}" [label={self.label_formatted},{self.attributes_as_str()}]'


class Variable(Resource):
    node_line = re.compile(r'"\[root\] (?P<name>var\.[^"]*)" \[(?P<attributes>[^]]*)\]')


class Provider(Resource):
    @classmethod
    def valid_line(cls, line: str) -> Optional[re.Match]:
        return 'label = "provider.' in line


class Output(Node):
    @classmethod
    def valid_line(cls, line: str) -> Optional[re.Match]:
        return 'label = "output.' in line


class Edge:
    edge_line = re.compile(r'"\[root\] (?P<from_name>[^"]*)" -> "\[root\] (?P<to_name>[^"]*)"')

    def __init__(self, from_name, to_name, graph):
        self.from_name = from_name
        self.to_name = to_name

        self.graph = graph

    def __str__(self):
        return f'"[{self.graph.name}] {self.from_name}":e -> "[{self.graph.name}] {self.to_name}":w'

    @classmethod
    def valid_line(cls, line: str) -> Optional[re.Match]:
        # print(cls.__name__)
        return cls.edge_line.fullmatch(line)

    @classmethod
    def from_match(cls, match, graph):
        return cls(**match.groupdict(), graph=graph)


class Graph:

    module_line = re.compile(r'"\[root\] module\.(?P<module_name>[^.]*)\.(?P<name>[^"]*)" \[(?P<attributes>[^]]*)\]')

    NODE_CLASSES = [
        Resource,
        Variable,
        Provider,
        Output,
    ]
    def __init__(self, name: str):
        self.name = name

        self.nodes = []
        self.edges = []
        self.modules = {}


    @classmethod
    def from_file(cls, filepath: str):
        basename = os.path.basename(filepath)
        root, _extension = os.path.splitext(basename)

        with open(filepath, "r") as graph_file:
            filecontent = graph_file.readlines()

        graph = cls(name=root)

        for line in filecontent[4:-2]:
            line = line.strip()
            # print(line)
            if not wanted_line(line):
                continue

            match = Edge.valid_line(line)
            if match:
                edge = Edge.from_match(match, graph=graph)
                graph.edges.append(edge)

                continue

            node = None
            module = None

            match = cls.module_line.fullmatch(line)
            if match:
                module_name = match['module_name']
                if module_name in graph.modules:
                    module = graph.modules[module_name]
                else:
                    module = Graph(name=graph.name + "-" + module_name)
                    graph.modules[module_name] = module

            for node_class in [Variable, Resource]:
                match = node_class.valid_line(line)
                if match:
                    node = node_class.from_match(match, graph=graph)
                    break


            if node:
                if module:
                    module.nodes.append(node)
                else:
                    graph.nodes.append(node)

        return graph

        #map(split_label, map(remove_aws, filter(wanted_line, filecontent[4:-2]))),

    def __str__(self):
        return "\n".join([
            f'subgraph "cluster_{self.name}" {{',
            f'\tlabel = "{self.name}";',
            '',
            '\t' + '\n\t'.join(map(str, self.modules.values())),
            '',
            '\t' + '\n\t'.join(map(str, self.nodes)),
            '',
            '\t' + '\n\t'.join(map(str, self.edges)),
            '}',
        ])


def wanted_line(line: str) -> bool:
    if any(p.match(line) for p in unwanted_patterns):
        return False

    return True

    #match = aws_provider_link.match(line)
    #if match:
    #    print(match, file=sys.stderr)
    #if aws_provider_link.match(line):
    #    return False


def is_edge(line: str) -> bool:
    return ' -> ' in line

def is_node(line: str) -> bool:
    match = re.compile(r'"\[root\] [^"]*" \[[^]]*\]').fullmatch(line)
    return match is not None


def split_label(line: str) -> str:
    #match = label_re.match(line)
    return label_re.sub(label_format, line)


def remove_aws(line: str) -> str:
    return line.replace("aws_", "")




def main() -> None:
    subgraphs = [Graph.from_file(filepath) for filepath in sys.argv[1:]]

    print('digraph root {\n'
          '\tcompound = "true";\n'
          #'\tnewrank = "true";\n'
          '\tsplines = "true";\n'
          '\tgraph[style = solid, fontname = "helvetica", fontsize = 12, rankdir = "LR"]\n',
          '\tedge[arrowsize = 0.6];\n'
          '\tnode[fontname = "helvetica", fontsize = 10]',
          )
    print("\n".join(map(str, subgraphs)))
    print(
        #'"[bootstrap] aws_s3_bucket.terraform_state_storage" -> "[xandr-integration] root"'
        '\t"[xandr-integration] provider.terraform (close)"[label="provider.terraform"];\n'
    )
    print("}")


if __name__ == "__main__":
    main()
