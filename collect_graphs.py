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


class Graph:
    def __init__(self, name: str):
        self.name = name

        self.nodes = []
        self.links = []


    @classmethod
    def from_file(cls, filepath: str):
        basename = os.path.basename(filepath)
        root, extension = os.path.splitext(basename)

        with open(filepath, "r") as graph_file:
            filecontent = graph_file.readlines()

        graph = cls(name=root)

        for line in filecontent[4:-2]:
            line = line.strip()
            if not wanted_line(line):
                continue

            #if is_edge(line):
            #    print("E: %s" % line)

            if is_node(line):
                graph.nodes.append(node_from_line(line, graph=graph))

        return graph

        #map(split_label, map(remove_aws, filter(wanted_line, filecontent[4:-2]))),

    def __str__(self):
        return "\n".join([
            f'subgraph "cluster_{self.name}" {{',
            f'\tlabel = "{self.name}";',
            '',
            '\t' + '\n\t'.join(map(str, self.nodes)),
            '}',
        ])


class Node:

    node_line = re.compile(r'"\[root\] (?P<name>[^"]*)" \[(?P<attributes>[^]]*)\]')
    attribute_sep = re.compile(r' *, *')
    key_value_sep = re.compile(r' *= *')

    def __init__(self, name: str, graph: Optional[Graph] = None,
                 attributes: Optional[Dict] = None):
        self.name = name
        self.graph = graph

        if attributes:
            self.label = attributes.pop('label')

        self.attributes = attributes

    @classmethod
    def valid_line(cls, line: str) -> bool:
        return False

    @classmethod
    def attributes(cls, line: str):
        return dict(cls.key_value_sep.split(pair)
                    for pair in cls.attribute_sep.split(line))

    def attributes_as_str(self) -> str:
        return ','.join('='.join(p) for p in self.attributes.items())

    def __str__(self) -> str:
        return f'"[{self.graph.name}] {self.name}" [label={self.label},{self.attributes_as_str()}]'


class Resource(Node):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.resource, self.key = self.label.split('.')

    @property
    def label_formatted(self):
        return ('label=<'
                '<table border="0">'
                '<tr><td>'
                f'<font color="gray40" point-size="9">{self.resource}</font>'
                '</td></tr>'
                f'<tr><td>{self.key}</td></tr>'
                '</table>>')

    def __str__(self):
        return f'"[{self.graph.name}] {self.name}" [label={self.label_formatted},{self.attributes_as_str()}]'

    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "aws_' in line


class Variable(Resource):
    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "var.' in line


class Provider(Resource):
    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "provider.' in line


class Data(Node):
    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "data.' in line


class Module(Node):
    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "module.' in line


class Output(Node):
    @classmethod
    def valid_line(cls, line: str) -> bool:
        return 'label = "output.' in line


NODE_CLASSES = [
    Resource,
    Variable,
    Provider,
    Data,
    Module,
    Output,
]


def node_from_line(line: str, graph: Graph):
    for cls in NODE_CLASSES:
        if cls.valid_line(line):
            break
    else:
        raise ValueError()

    match = cls.node_line.fullmatch(line)

    node = cls(name=match['name'], graph=graph,
               attributes=cls.attributes(match['attributes']))

    return node





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
    print("\n".join(map(str, subgraphs)))
    return

    print('digraph root {\n'
          '\tcompound = "true";\n'
          #'\tnewrank = "true";\n'
          '\tsplines = "true";\n'
          '\tgraph[style = solid, fontname = "helvetica", fontsize = 12, rankdir = "LR"]\n',
          '\tedge[arrowsize = 0.6];\n'
          '\tnode[fontname = "helvetica", fontsize = 10]',
          )
    print(subgraphs)
    print(
        #'"[bootstrap] aws_s3_bucket.terraform_state_storage" -> "[xandr-integration] root"'
        '\t"[xandr-integration] provider.terraform (close)"[label="provider.terraform"];\n'
    )
    print("}")


if __name__ == "__main__":
    main()
