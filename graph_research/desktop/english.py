"""English presentation of reviewed native contracts; registry schemas stay intact."""
import json
from html import escape
from .i18n import register_translations

TOOL_TITLES={
    'graph_property_scan':'Graph-family property experiment','graph_property_verify':'Independent graph-property verification',
    'graph_counterexample_round':'Counterexample search round','graph_counterexample_verify':'Independent counterexample verification',
    'generate_hypergraph':'Hypergraph construction','hypergraph_spectrum':'Hypergraph spectral radius',
    'graph_spectrum':'Graph numerical spectrum','graph_invariants':'Graph invariants',
    'graph_characteristic_polynomial':'Graph characteristic polynomial','matching_polynomial':'Matching generating polynomial',
    'matrix_analysis':'Numerical matrix analysis','polynomial_roots':'Real polynomial roots','quotient_matrix':'Quotient matrix',
    'tensor_spectrum':'Tensor spectral radius','combinatorial_calculation':'Combinatorial calculation','graph_edit':'Graph transformations',
    'exact_matrix_operation':'Exact matrix calculation','tensor_operation':'Tensor operations','graph_construction':'Graph construction',
    'graph_symmetry':'Graph symmetry and quotients','graph_spectral_analysis':'Graph spectral analysis','compare_graphs':'Graph comparison',
    'graph_enumeration':'Graph enumeration','hypergraph_structure':'Hypergraph structural analysis','hypergraph_transform':'Hypergraph transformations',
    'hypergraph_quotient_spectrum':'Hypergraph symmetry reduction','directed_graph_spectrum':'Directed graph spectrum',
    'linear_recurrence':'Linear recurrences','integer_linear_system':'Integer linear systems',
    'hypergraph_tensor_charpoly':'Hypergraph tensor characteristic polynomial','tensor_charpoly':'Tensor characteristic polynomial',
    'hypergraph_plot':'Hypergraph structure drawing','hypergraph_editor':'Interactive layout','hypergraph_tikz':'Hypergraph TikZ',
    'graph_tikz':'Graph TikZ','hypergraph_schematic':'Hypergraph paper schematic','weighted_graph_spectrum':'Weighted graph matrices and spectra',
    'graph_recipe':'Parameterized graph construction','hypergraph_path_analysis':'Hypergraph internal-path analysis',
    'graph_batch_study':'Batch graph study','symbolic_analysis':'Symbolic sums and series','block_matrix_analysis':'Block and companion matrices',
    'graph_class_certificate':'Generalized line-graph certificates','graph_energy_study':'Exact energy comparison',
    'research_environment':'Optional research environment','combinatorial_plot':'Lattice paths and chessboards',
    'graph_layout':'Graph layout and coordinates'}

SUMMARIES={
    'graph_property_scan':'Scan bounded non-isomorphic atlas graphs, trees or a supplied collection. Exactly compute simple spectrum, all-ones controllability and Wronskian vertices, preserving pagination scope and evidence.',
    'graph_property_verify':'Independently reconstruct exact rational matrix, polynomial GCDs and Krylov rank from raw graph data using Fraction arithmetic; compare the complete stored certificate.',
    'graph_counterexample_round':'Screen bounded connected simple graphs with fixed vertex and edge counts. Floating estimates do not certify a counterexample; independently verify a promising candidate.',
    'graph_counterexample_verify':'Verify strict adjacency-spectral improvement from raw edges: exact polynomial roots for up to 12 vertices, independently checked rational Rayleigh/Collatz bounds for larger graphs up to 128 vertices and 1024 edges.',
    'generate_hypergraph':'Construct uniform loose paths, stars, cycles and the listed pendant-path research families. Lengths count edges; choose a family before filling its arguments.',
    'hypergraph_spectrum':'Compute the α-spectral radius, positive Perron vector and optional weighted incidence matrix of a nonempty uniform positive-weight hypergraph. For α<1 the hypergraph must be connected; α=1 is the degree-diagonal endpoint.',
    'graph_spectrum':'Compute eigenvalues and spectral radius of a supported matrix of an undirected unweighted graph. Distance matrices require connectedness; choose the matrix definition explicitly.',
    'graph_invariants':'Compute vertex/edge counts, degree sequence, connected components, diameter where defined and other basic invariants of the specified graph. Preserve isolated vertices using n.',
    'graph_characteristic_polynomial':'Compute an exact characteristic polynomial for the selected graph matrix, subject to the documented graph-size limit.',
    'matching_polynomial':'Compute the matching generating polynomial of an unweighted simple graph, counting matchings by size. This is not a tensor characteristic polynomial.',
    'matrix_analysis':'Analyze a finite numeric matrix: shape, rank, determinant and applicable eigenvalue information. Enter a rectangular JSON array of rows.',
    'polynomial_roots':'Isolate and report real roots of a polynomial within the requested interval, under the tool degree and arithmetic limits.',
    'quotient_matrix':'Compute a matrix quotient for the given vertex partition and check equitability. Groups must partition the required indices.',
    'tensor_spectrum':'Numerically compute a Perron spectral radius for a nonnegative tensor satisfying the solver assumptions. Inspect convergence and residual information; this does not enumerate all eigenvalues.',
    'combinatorial_calculation':'Evaluate integer partitions, arithmetic matrices, cycle-type counts, standard group cycle indices, Cayley graphs or rook polynomials. Fill arguments for the selected operation.',
    'graph_edit':'Transform an undirected simple graph using the selected operation. Preserve isolated vertices. Results include reusable graph specifications; replacement operations use separate internal copies.',
    'exact_matrix_operation':'Exact matrix algebra with SymPy: row reduction, inverse, determinant, characteristic polynomial, elementary transformations or determinant row splitting. Use explicit coefficients and supported expressions.',
    'tensor_operation':'Inspect or transform a tensor: symmetrization, index transpose, entrywise powers or properties. Entrywise powers are not tensor-composition powers.',
    'graph_construction':'Construct theta, caterpillar, cactus, Hamming or bounded random cycle-rank graphs. The same argument name may have different meanings across families.',
    'graph_symmetry':'Compute graph symmetries, orbits and supported quotient information within the enumeration budget. Results respect the specified graph structure.',
    'graph_spectral_analysis':'Analyze graph energy, graph angles, spectral projectors or exact α-characteristic polynomials. Choose the operation and its matrix/input conventions explicitly.',
    'compare_graphs':'Compare two graphs for isomorphism, cospectrality or bounded non-induced subgraph counts. For counting, the left graph is the host and the right graph is the pattern.',
    'graph_enumeration':'Enumerate bounded cycles, simple paths, Hamiltonian cycles or nonisomorphic degree-sequence realizations. Search and output limits apply.',
    'hypergraph_structure':'Analyze incidence, distance, line graphs, orbits, tensor eigen-equations or matching polynomials. Tensor branches require uniform hypergraphs; a structural drawing may be non-uniform.',
    'hypergraph_transform':'Attach paths/hyperedges, expand or subdivide edges, clone or merge vertices, or extract induced subhypergraphs. Check the selected operation’s structural prerequisites.',
    'hypergraph_quotient_spectrum':'Use symmetry orbits to reduce a connected positive-weight uniform hypergraph spectral problem, then verify the original equations and residual.',
    'directed_graph_spectrum':'Compute directed adjacency, out-degree Laplacian, directed α or Hermitian adjacency spectra. General directed matrices may have complex eigenvalues.',
    'linear_recurrence':'Solve a linear recurrence with coefficients[i] multiplying a(n+i) and forcing on the right. Supply consecutive initial values from start, with count equal to the order. Check returned conditions/status.',
    'integer_linear_system':'Solve matrix*x=rhs over integers, allowing specified integer symbols. Conditional solutions are valid only when their returned conditions hold.',
    'hypergraph_tensor_charpoly':'Compute the exact ordinary characteristic polynomial of a uniform hypergraph A/L/Q/α tensor by resultant elimination. Includes multiplicities and zero roots; estimate size before expensive cases.',
    'tensor_charpoly':'Compute a small tensor’s ordinary characteristic polynomial using exact elimination. This is not an E-characteristic or matching polynomial. Matrix-size, degree and time limits apply.',
    'hypergraph_plot':'Draw a graph or possibly non-uniform hypergraph using unfilled curves through member vertices. Export graphics using explicit styles and optional coordinates.',
    'hypergraph_editor':'Prepare a draggable structure layout. Save graph coordinates for reuse; editing positions does not change incidence.',
    'hypergraph_tikz':'Export TikZ for a possibly non-uniform hypergraph, retaining supported weights, labels and coordinates. TeX compilation is separate.',
    'graph_tikz':'Export TikZ for a graph, retaining supported direction, weights, labels and coordinates. Generating source requires no TeX compiler.',
    'hypergraph_schematic':'Export symbolic paper diagrams or expand them after assigning parameters. Unspecified path lengths are schematic and cannot directly be used for numerical calculations.',
    'weighted_graph_spectrum':'Construct weighted real/complex or directed matrices and their spectra. Choose the degree convention explicitly; distinguish Hermitian energy from a general spectral-modulus sum.',
    'graph_recipe':'Build parameterized graphs/hypergraphs from an initial structure, explicit integer parameters, construction steps and structural assertions. Returned graph specifications can feed later tools.',
    'hypergraph_path_analysis':'Validate an oriented loose internal path, branches and ambiguities; extract incidence or weighted-incidence submatrices. Explicit edge order resolves ambiguous paths.',
    'graph_batch_study':'Run a bounded list of graph/hypergraph/recipe/weighted cases and export comparison data and optional figures. Inspect calculation and export status separately.',
    'symbolic_analysis':'Perform controlled symbolic summation or local series expansion with SymPy. Inspect conditions, unevaluated/divergent status and the remainder term.',
    'block_matrix_analysis':'Extract/reorder matrix blocks, display block-product contributions or build polynomial companion blocks. This is not a Jordan decomposition; exact size and polynomial restrictions apply.',
    'graph_class_certificate':'Perform bounded exact generalized line-graph recognition with a replayable positive or exhaustive negative certificate. Budget exhaustion is unresolved, not a negative certificate.',
    'graph_energy_study':'Compare graph energies over a finite integer parameter domain using exact root isolation and root-count checks. Unseparated intervals are unresolved; no infinite-domain theorem is claimed.',
    'research_environment':'Detect optional plotting packages and TeX programs, and report integration requirements. Detection does not install packages, run a compiler or implement full implicit 3D plotting.',
    'combinatorial_plot':'Draw stepwise lattice paths, paths from right-step indices, rectangles or numeric chessboards. Path steps: 0 up, 1 right. Chessboard rows run bottom-to-top; nonzero entries are filled.',
    'graph_layout':'Compute graph layouts or adjust coordinates. Fixed spring layouts need all initial positions. Transform order: scale, counterclockwise rotation in degrees, then translation. Overlaps may prevent preview.'}

DETAILS={
    'edges':'Edge/member lists; retain isolated vertices with the explicit vertex list/count.',
    'n':'Total vertex count, including isolated vertices; use the selected family’s documented interpretation.',
    'vertices':'Explicit vertex labels/indices in the order required by the selected operation.',
    'weights':'Weights in edge order; the number must match the edge count. Hypergraph Perron tools require positive real weights.',
    'vertex_degrees':'Degree-diagonal entries in vertex order. They must satisfy the selected solver’s compatibility conditions.',
    'alpha':'α in [0,1]. For hypergraph Perron computations α=1 is a separate degree-diagonal endpoint.',
    'positions':'Complete coordinates, e.g. [{"vertex":0,"xy":[0,0]}]. Use original vertex identities.',
    'initial_vector':'Strictly positive initial values in vertex order; length must match the vertex count.',
    'tolerance':'Target relative residual; acceptance also uses the solver’s independent verification criteria.',
    'max_iterations':'Total iteration budget, including continuation, failed stages and numerical refinement.',
    'matrix':'Choose the matrix/tensor convention explicitly; the option tooltip explains its meaning.',
    'operation':'Select an operation before filling its branch-specific arguments.',
    'parameters':'Named integer/symbol parameters or values, as required by the selected tool.',
    'kind':'Choose an ordinary graph family or an explicit edge list; n retains isolated vertices.',
    'family':'Choose the construction family. Lengths count edges for hypergraph families.',
    'coefficients':'For recurrences, coefficients[i] multiplies a(n+i); for polynomials, use the specified coefficient order.',
    'forcing':'Right-hand side of the recurrence, expressed in the selected index variable.',
    'initial_values':'Consecutive recurrence values starting at start, one per recurrence order.',
    'groups':'Groups of vertex/matrix indices forming the requested partition; equitability is checked where applicable.',
    'seed':'Local random seed for reproducibility; it does not change global random state.',
    'power':'Connect distinct vertex pairs whose original shortest-path distance is at most this exponent.',
    'edit_edges':'Original edges selected for deletion, subdivision or replacement, depending on the operation.',
    'replacement':'Graph specification used as a replacement or product factor; check endpoint mapping.',
    'endpoints':'Two replacement-graph vertices identified with the endpoints of the original edge.',
    'right_steps':'Zero-based indices of right steps; all other steps go up.',
    'board':'0/1 board: 1 permits a rook, 0 forbids it. Coefficients count nonattacking rook placements.',
    'bounds':'Rectangle bounds [xmin,ymin,xmax,ymax].',
    'graph_document':'Complete graph document including identities, direction, weights, coordinates and display style.',
    'edge_indices':'Explicit ordered hyperedge indices for the oriented loose-path analysis.',
    'estimate_only':'Estimate exact-elimination size without computing the characteristic polynomial.',
    'steps':'Explicit step list. For lattice paths 0 means up and 1 means right; graph recipes use structured construction steps.',
    'actions':'Structured elementary row/column operations; no executable Python callbacks.',
    'assertions':'Structural properties to check after construction; failure is reported explicitly.',
    'left':'Left graph/matrix. In subgraph counting this graph is the host.',
    'right':'Right graph/matrix. In subgraph counting this graph is the pattern.',
    'side':'Right: g→g·s; left: g→s·g; two-sided takes both. Duplicate arcs and loops are omitted.',
    'variable':'Variable used for the polynomial, summation, series or recurrence, according to the tool.',
    'row_labels':'Display labels in row order; they do not change the numeric matrix.',
    'column_labels':'Display labels in column order; they do not change the numeric matrix.'}
DETAILS.update({'angle':'Counterclockwise rotation angle in degrees, about the origin.',
    'scale':'Uniform scale factor applied about the origin before rotation and translation.',
    'offset':'Translation [dx,dy] applied after scaling and rotation.',
    'lower':'Inclusive summation/real-root lower bound, as defined by the selected tool.',
    'upper':'Inclusive summation upper bound; symbolic endpoints must use the supported syntax.',
    'center':'Series expansion center in the selected variable.',
    'order':'Series truncation order; inspect the returned remainder term.',
    'start':'Starting vertex for path enumeration, or starting index for recurrence initial values.',
    'rhs':'Right-hand-side vector of matrix*x=rhs; dimensions must match.',
    'arcs':'Directed arcs as ordered endpoint pairs; direction is significant.',
    'data':'Explicit numeric tensor entries with consistent dimensions.',
    'degree_mode':'Choose whether weighted degree sums signed real weights or their absolute values.',
    'symbolic_alpha':'Keep α symbolic for supported exact-polynomial branches.',
    'rank':'Tensor order, or target hyperedge size in the corresponding transformation.',
    'k':'Uniformity, partition part count, or graph-family parameter; check the selected tool/family.',
    'm':'Number of hyperedges or backbone edges, according to the selected construction.',
    'length':'Number of edges in the requested path/cycle.',
    'lengths':'Path/cycle lengths counted in edges, in the selected family’s order.',
    'weighted_incidence':'Return the weighted point–edge incidence matrix when the Perron solution permits it.'})

OPERATION_HELP={
    'power':'Join distinct pairs at original shortest-path distance ≤ power; for power=2 also join vertices at distance 2.',
    'complement':'Complement the simple graph on the same vertex set; no loops are added.',
    'line_graph':'Make each original edge a vertex, adjacent when the original edges intersect.',
    'delete_vertices':'Remove the selected vertices and all their incident edges.',
    'delete_edges':'Remove selected edges while retaining their endpoint vertices.',
    'add_edges':'Add the listed edges without deleting isolated vertices.',
    'core':'Take the core_k-core by repeatedly removing vertices of degree below core_k.',
    'relabel':'Use the supplied new vertex labels without changing incidence.',
    'subdivide_edges':'Insert subdivisions new vertices into each selected original edge.',
    'replace_edge':'Replace one selected edge using an independent graph and the chosen replacement endpoints.',
    'replace_edges':'Replace each selected edge with its own replacement-graph copy; preserve isolated vertices.',
    'partial_product':'Cartesian product on the selected induced subgraph, reconnecting product vertices to original external neighbors.',
    'seidel_switch':'Switch adjacency across the selected vertex-set cut, retaining within-part adjacency.',
    'rref':'Compute reduced row echelon form and pivot columns exactly.',
    'inverse':'Compute the inverse; the matrix must be square and nonsingular.',
    'determinant':'Compute the determinant of a square matrix.',
    'charpoly':'Compute the exact characteristic polynomial with algebraic multiplicities.',
    'entrywise_power':'Raise each tensor entry to exponent; this is not a tensor-composition power.',
    'transpose':'Permute tensor index directions according to the supplied order.',
    'symmetrize':'Average tensor entries over index permutations.',
    'orbits':'Compute vertex orbits under structure-preserving automorphisms, within the search limit.',
    'isomorphic':'Check structure-preserving graph isomorphism; compare compatible graph inputs.',
    'cospectral':'Compare the spectra under the chosen matrix convention.',
    'subgraph_count':'Count non-induced copies of the right pattern graph inside the left host graph.',
    'paths':'Enumerate simple paths using start, end and length under the result limit.',
    'cycles':'Enumerate cycles of the requested length under the result limit.',
    'hamilton':'Enumerate Hamiltonian cycles under the search and output limits.',
    'degree_realizations':'Enumerate nonisomorphic graph realizations of a graphical degree sequence.',
    'matching_poly':'Compute a matching polynomial, not the tensor characteristic polynomial.',
    'equations':'Generate tensor eigen-equations; generating them does not solve the full spectrum.',
    'laplacian_equations':'Generate degree-minus-adjacency tensor eigen-equations for a uniform hypergraph.',
    'spring':'Spring layout; fixed_vertices requires complete initial coordinates.',
    'spectral':'Use Laplacian spectral coordinates. Coordinates may overlap or be non-unique.',
    'tree':'Use a hierarchical tree layout with the specified root, under its structural requirements.',
    'transform':'Scale about the origin, rotate counterclockwise by angle degrees, then translate by offset.',
    'align_horizontal':'Align only the selected vertices horizontally; leave other coordinates unchanged.',
    'align_vertical':'Align only the selected vertices vertically; leave other coordinates unchanged.',
    'partition_number':'Count partitions of n, using k parts when requested.',
    'cycle_index':'Compute the standard cycle index of the complete finite permutation group.',
    'cycle_type_count':'Count permutations having the specified cycle-type partition.',
    'rook_polynomial':'Count nonattacking rook placements on the allowed 0/1 board; coefficients are in ascending degree.',
    'cayley_graph':'Build generator arcs with the selected left/right/two-sided multiplication; omit duplicate arcs and loops.',
    'grid_path':'Read steps in order: 0 goes up and 1 goes right, starting at the origin.',
    'lattice_path':'Create total_steps steps; zero-based right_steps go right, all others go up.',
    'chessboard':'Draw nonzero matrix squares; rows run bottom-to-top and columns left-to-right.',
    'rectangle':'Draw [xmin,ymin,xmax,ymax], optionally filled.',
    'summation':'Symbolically sum the expression over the requested bounds; inspect conditions and unevaluated status.',
    'series':'Expand at center through the requested order, retaining the remainder term.',
    'extract':'Extract all matrix blocks using the specified row/column block sizes.',
    'permute':'Reorder whole row/column blocks according to the given block orders.',
    'multiply':'Compute the product as sums of block contributions; inner dimensions must match.',
    'companion_blocks':'Build polynomial companion diagonal blocks; this is not a Jordan decomposition.',
    'export':'Export the symbolic scene as SVG/TikZ without treating unspecified lengths as concrete data.',
    'expand':'Assign all required parameters and expand the symbolic scene to a concrete hypergraph.',
    'attach_star':'Attach new hyperedges sharing the specified root set, retaining original isolated vertices and weights.',
    'attach_path':'Attach a pendant loose path at the selected vertex, respecting uniformity.',
    'induced':'Keep the selected vertices and the appropriate contained hyperedges.',
    'merge':'Identify the specified vertices under the operation’s incidence restrictions.',
    'expand_edges':'Expand hyperedges to the requested uniform size.',
    'subdivide':'Subdivide the selected hyperedge under the construction constraints.',
    'clone_all':'Clone vertices into their original incident hyperedges.',
    'clone_cartesian':'Expand incident edge memberships using Cartesian combinations of clones.'}

INPUT_NOTES={
    'generate_hypergraph':'Use m/k or lengths for basic families; left_lengths/right_lengths for gee/gev/gvv, pendant_length for ca/cva, and edge_paths/vertex_paths for gwg. Lengths count edges and the families preserve k.',
    'hypergraph_spectrum':'Every edge has the same size. For α<1 the hypergraph must be connected. Use α in [0,1]; 1 is the degree-diagonal endpoint. Weights follow edge order and vertex_degrees follows vertex order; omitted values use defaults.',
    'graph_edit':'core uses core_k; relabel uses labels; subdivide_edges uses edit_edges/subdivisions; replace_edge uses exactly one edit_edges pair, replacement and endpoints. replace_edges accepts multiple edges with independent copies. partial_product uses vertices and replacement. Reuse graph_spec with integer-indexed tools.',
    'graph_construction':'Choose family first: theta uses three lengths; caterpillar uses n and attachments; cactus uses cycle lengths and seed; hamming uses k and q; random_k_cyclic uses n, k and seed.',
    'graph_spectral_analysis':'Select operation. alpha_charpoly can use symbolic_alpha=true; other branches use their corresponding numeric arguments.',
    'graph_enumeration':'paths uses start/end/length; cycles uses length; degree_realizations uses degrees. Reaching limit does not prove enumeration is complete.',
    'hypergraph_structure':'Incidence and other structural branches accept non-uniform edges. equations only generates equations; it does not solve them. Tensor branches still require uniformity.',
    'hypergraph_transform':'Choose operation: attach_path uses vertex/count/rank; attach_star uses roots/count/rank with shared roots; expand_edges uses count; cloning uses vertex/count; merge uses groups; subdivide uses edge_index/count; induced uses vertices. Check each argument’s limits.',
    'linear_recurrence':'coefficients[i] multiplies a(n+i); forcing is the right-hand side. Supply consecutive initial values from start, one per order. For example [-1,-1,1] with [0,1] gives the Fibonacci recurrence.',
    'integer_linear_system':'Solve matrix*x=rhs over integers, including parameters. A conditional result is valid only when its returned conditions hold.',
    'hypergraph_tensor_charpoly':'Uniform hypergraphs only. For an empty edge list also provide n and rank; otherwise rank can be inferred. For matrix=alpha use a rational α or symbolic_alpha. estimate_only=true estimates size without returning a computed polynomial.',
    'tensor_charpoly':'data contains nested axes of a cubic tensor, not an edge list. A 2×2 array is order two. estimate_only=true estimates size only.',
    'tensor_spectrum':'data is a dense nonnegative cubic tensor with equal axis lengths, not a hyperedge list. A 2D matrix represents an order-two tensor.',
    'tensor_operation':'Each nested data level is an axis. exponent is used only for entrywise_power, not tensor/matrix multiplication.',
    'exact_matrix_operation':'Enter matrix rows as integers or decimals. elementary uses actions; split_row uses row_index/row_terms and adds the remainder automatically. Fraction strings, symbols and complex entries are not accepted here; decimals are exact decimal rationals.',
    'combinatorial_calculation':'Partition branches use n/k/parts. cycle_index/cayley_graph use zero-based permutation image arrays and generate the full group. Cayley side selects left/right/both; n/arcs feed directed spectra. Rook board is rectangular 0/1, with 1 allowed and 0 forbidden; at most 10 per dimension.',
    'combinatorial_plot':'Choose an operation. Stepwise paths use 0 for up and 1 for right; right_steps is zero-based. Chessboard matrix rows run bottom-to-top, with nonzero entries filled. Rectangle bounds are [xmin,ymin,xmax,ymax].',
    'graph_layout':'positions is [{"vertex":0,"xy":[0,0]},...] and must cover all vertices. Fixed spring layout also needs fixed_vertices; alignment selects vertices. Transform order is origin scaling, counterclockwise degrees, then translation. Reuse positions in dragging or TikZ.'}

COMMON_NOTES={
    '标准图族填kind和n即可；自定义图选kind=edges，并给n和edges。n包含孤立点，顶点编号为0..n-1。':'Standard graphs use kind and n. For custom graphs choose kind=edges with n and edges. n includes isolated vertices; indices are 0..n−1.',
    '简单图的每条边写成两个顶点，例如[[0,1],[1,2]]；绘图后可在结果中调整布局。':'Each simple edge has two endpoints, e.g. [[0,1],[1,2]]. Adjust the layout beside the drawing result.',
    '边表每项列出该边的成员；如需孤立点，vertices填写全部顶点。绘图/导出可以使用字符串标签。':'Each edge lists its members. Specify all vertices to retain isolated ones. Drawing/export accepts string labels.',
    'matrix按行输入；各行长度一致。可填0.5等小数，不使用Python表达式或分数字符串。':'Enter equal-length matrix rows. Decimals such as 0.5 are accepted; Python expressions and fraction strings are not.',
    'blocks是从0开始的矩阵行列索引分组，必须构成完整划分；不等价时不能把商谱视为原谱的可靠子集。':'blocks must completely partition the zero-based matrix indices. Without equitability, the quotient spectrum is not a guaranteed subset of the original spectrum.',
    'coefficients按最高次到常数项填写，中间缺项补0；例如[1,0,-1]表示x²-1，区间端点需a≤b。':'Coefficients run from highest degree to the constant, using 0 for missing powers. [1,0,-1] is x²−1; interval endpoints require a≤b.',
    'arcs中的[u,v]表示u→v，顺序有意义；n给出总顶点数，标签为0..n-1。':'An arc [u,v] means u→v; order matters. n counts all vertices with indices 0..n−1.',
    'left和right各填一个图的JSON对象，例如{"kind":"path","n":3}；不是直接填边表。':'left and right each contain a graph JSON object, e.g. {"kind":"path","n":3}, rather than a bare edge list.',
    'positions可省略使用自动布局；手填时每项为{"vertex":标签,"xy":[x,y]}，必须覆盖全部顶点且坐标不能全相同。':'Omit positions for automatic layout. Otherwise use {"vertex":label,"xy":[x,y]} entries for all vertices; coordinates cannot all coincide.'}


def _format(schema):
    kind=schema.get('type','JSON')
    if isinstance(kind,list):kind=' or '.join(kind)
    messages=[{'array':'JSON array, e.g. [0,1]. Nested arrays use [[...],[...]].',
               'object':'JSON object with quoted keys, e.g. {"key":1}.',
               'boolean':'Boolean true or false; the displayed choice preserves the raw boolean.',
               'integer':'Integer input.','number':'Finite numeric input.','string':'Text input; expressions use the tool’s restricted syntax.'}.get(kind,'JSON input.')]
    for key,label in [('minimum','Minimum'),('maximum','Maximum'),('minItems','Minimum items'),('maxItems','Maximum items'),('minLength','Minimum length'),('maxLength','Maximum length')]:
        if key in schema:messages.append(label+': '+str(schema[key])+'.')
    if 'enum' in schema:messages.append('Choose one of: '+json.dumps(schema['enum'],ensure_ascii=False)+'.')
    return ' '.join(messages)


def register_registry(registry):
    """Register English help for the native UI, not for unknown extension metadata."""
    from graph_research.rendering.results import TITLES,LABELS
    from graph_research.tools.input_guides import input_guide,NOTES
    from .localization import parameter_title,option_presentation
    entries={TITLES[name]:title for name,title in TOOL_TITLES.items()}
    overrides={'order':'Vertex count','size':'Edge count','rank':'Rank','rho':'Spectral radius','relative_residual':'Relative residual',
               'degree':'Polynomial degree','perron_vector':'Perron vector','weighted_incidence':'Weighted incidence matrix',
               'quotient':'Quotient matrix','shape':'Shape','elapsed_seconds':'Elapsed time (s)','arithmetic':'Arithmetic',
               'vertices':'Vertices','nodes':'Vertices','edges':'Edges','alpha':'α','code_in_file':'Code saved to file'}
    for key,value in LABELS.items():entries.setdefault(value,overrides.get(key,key.replace('_',' ').capitalize()))
    for definition in registry.catalog():
        if definition.get('documentation',{}).get('coverage')!='reviewed_native':continue
        name=definition['name'];guide=input_guide(definition);summary=SUMMARIES[name]
        entries[definition['description']]=summary;entries[guide['summary']]=summary
        for note in guide['notes']:
            if note in COMMON_NOTES:entries[note]=COMMON_NOTES[note]
            elif note==NOTES.get(name) and name in INPUT_NOTES:entries[note]=INPUT_NOTES[name]
        for field in guide['fields']:
            parameter=field['name'];schema=definition['parameters']['properties'][parameter]
            title=parameter_title(definition,parameter)
            # Titles are translated by the fixed vocabulary, with raw IDs retained.
            description=DETAILS.get(parameter,'Argument '+parameter+'.')+' '+_format(schema)
            source=schema.get('description','')
            if source:
                entries[source]=description;entries[source.split('。')[0][:105]]=description
            entries[field['format']]=_format(schema)
            entries[field['omission']]='Required: provide this argument.' if parameter in definition['parameters'].get('required',[]) else 'Optional: disabled fields are omitted; enabled fields use their entered value.'
            for value in schema.get('enum',[]):
                label,hint=option_presentation(definition,parameter,value)
                if parameter in ('operation','family') and hint not in entries:
                    entries[hint]=OPERATION_HELP.get(str(value),SUMMARIES[name])
    entries.update({escape(source):escape(english) for source,english in list(entries.items()) if source!=escape(source)})
    register_translations(entries)
