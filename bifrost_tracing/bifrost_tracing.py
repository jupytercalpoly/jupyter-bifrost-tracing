"""Main module."""
from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic, line_magic
from IPython.core.extensions import ExtensionManager
from IPython import get_ipython

import ast


# keep it here for reactive cells later??
@magics_class
class BifrostTracing(Magics):
    @line_magic
    def line_tracing(self, line):
        return line

    @cell_magic
    def tracing(self, line, cell):
        return line, cell


class BifrostWatcher(object):
    def __init__(self, ip):
        self.shell = ip
        self.last_x = None
        self.bifrost_table = {}
        self.plot_output = ""
        self.bifrost_input = ""
        self.visitor = None

    def post_run_cell(self, result):
        if not result.error_in_exec:
            ast_tree = ast.parse(result.info.raw_cell)

            callVisitor = CallVisitor()
            callVisitor.visit(ast_tree)
            print(f"args={callVisitor.args}")
            # assignVisitor = AssignVisitor()
            # assignVisitor.visit(ast_tree)

        # for new_df in assignVisitor.new_dfs:
        #     columns = get_ipython().run_cell(new_df + '.columns').result
        #     print(columns)
        #     if new_df in self.bifrost_table:
        #         columns_set = set(columns)
        #         table_set = set(self.bifrost_table[new_df].keys())
        #         for new_col in (columns_set - table_set):
        #             self.bifrost_table[new_df][new_col] = 0
        #     else:
        #         self.bifrost_table[new_df] = {col: 0 for col in columns}


class AttributeVisitor(ast.NodeVisitor):
    def __init__(self):
        self.attributes = []

    def visit_Attribute(self, node):
        if isinstance(node, ast.Attribute):
            self.visit(node.value)
            self.attributes.append(node.attr)


class NameVisitor(ast.NodeVisitor):
    def __init__(self):
        self.names = []

    def visit_Name(self, node):
        self.names.append(node.id)


class AssignVisitor(ast.NodeVisitor):
    def __init__(self):
        self.new_dfs = []
        self.output_var = None
        self.bifrost_input = None

    def visit_Module(self, node):
        self.generic_visit(node)

    def visit_Assign(self, node):
        nameVisitor = NameVisitor()
        for target in node.targets:
            nameVisitor.visit(target)
        names = nameVisitor.names
        attributeVisitor = AttributeVisitor()
        attributeVisitor.visit(node.value)
        attributes = attributeVisitor.attributes
        df_mask = [call == "pd.DataFrame" for call in attributes]
        plot_mask = "bifrost.plot" in attributes
        if "DataFrame" in attributes:
            self.new_dfs.extend(names)
        if "bifrost.plot" in attributes:
            self.output_var = names[-1] if len(names) else None
            nameVisitor = NameVisitor()
            nameVisitor.visit(node)
            self.bifrost_input = nameVisitor.names[-1]


class SubscriptVisitor(ast.NodeVisitor):
    def visit_Subscript(self, node: ast.Subscript):
        self.subscripts = []
        self.subscripts.append([node.value.id, node.slice.value])


class CallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.args = []

    def visit_Module(self, node):
        self.generic_visit(node)

    def visit_Call(self, node):
        # NP cases
        attributeVisitor = AttributeVisitor()
        attributeVisitor.visit(node.func)
        print(attributeVisitor.attributes)
        if attributeVisitor.attributes[0] in [
            "np.mean",
            "np.std",
            "np.sum",
            "numpy.mean",
            "numpy.std",
            "numpy.sum",
        ]:
            args = node.args
            if len(args) != 0:
                self.get_args(args[0])
            else:
                # check keywords
                keywords = node.keywords
                for keyword in keywords:
                    if keyword.arg == "a":
                        self.get_args(keyword.value)

    """value: either ast.Subscript or ast.Attribute"""

    def get_args(self, value):
        # case arg is df['one']
        if isinstance(value, ast.Subscript):
            subscriptVisitor = SubscriptVisitor()
            subscriptVisitor.visit(value)
            self.args.append(
                f"{subscriptVisitor.subscripts[0][0]}.{subscriptVisitor.subscripts[0][1]}"
            )

        # case arg is df.one
        elif isinstance(value, ast.Attribute):
            attributeVisitor = AttributeVisitor()
            attributeVisitor.visit(value)
            df, column = attributeVisitor.attributes[0].split(".")
            self.args.append(f"{df}.{column}")


# some_var = ...bifrost.plot()
def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


def load_ipython_extension(ipython):
    ipython.register_magics(BifrostTracing)
    vw = BifrostWatcher(ipython)
    ipython.events.register("pre_run_cell", vw.pre_run_cell)
    ipython.events.register("post_run_cell", vw.post_run_cell)
    return vw


Watcher = load_ipython_extension(get_ipython())
