"""Paper schematics, isolated from concrete graphs and numerical tensors."""
from .document import SchematicDocument, template, from_graph, compress_path, expand
from .tikz import to_tikz, to_svg, save

__all__=['SchematicDocument','template','from_graph','compress_path','expand','to_tikz','to_svg','save']
