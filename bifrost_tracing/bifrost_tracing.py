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
        self.bifrost_input_url = ""
        self.chart_var = ""
        self.visitor = None

    def pre_run_cell(self, info):
        ast_tree = ast.parse(info.raw_cell)
        assignVisitor = AssignVisitor(self.chart_var)
        assignVisitor.visit(ast_tree)
        output_var = assignVisitor.output_var
        bifrost_input = assignVisitor.bifrost_input
        bifrost_input_url = assignVisitor.bifrost_input_url
        chart_var = assignVisitor.chart_var
        if chart_var:
            self.chart_var = chart_var
        if output_var:
            self.plot_output = output_var
        if bifrost_input:
            self.bifrost_input = bifrost_input
            self.bifrost_input_url = ""
        elif bifrost_input_url:
            self.bifrost_input = ""
            self.bifrost_input_url = bifrost_input_url
        self.visitor = assignVisitor
        # print(self.plot_output)
        # print(self.bifrost_input)
        # print(self.bifrost_input_url)

    def post_run_cell(self, result):
        if not self.visitor:
            return

        for new_df in self.visitor.new_dfs:
            columns = get_ipython().run_cell(new_df + ".columns").result
            if new_df in self.bifrost_table:
                columns_set = set(columns)
                table_set = set(self.bifrost_table[new_df].keys())
                for new_col in columns_set - table_set:
                    self.bifrost_table[new_df][new_col] = 0
            else:
                self.bifrost_table[new_df] = {col: 0 for col in columns}
        self.visitor = None


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
    def __init__(self, chart_var):
        self.new_dfs = set()
        self.output_var = None
        self.bifrost_input = None
        self.bifrost_input_url = None
        self.chart_var = chart_var

    def visit_Module(self, node):
        self.generic_visit(node)

    def visit_Assign(self, node):
        nameVisitor = NameVisitor()
        for target in node.targets:
            nameVisitor.visit(target)
        names = nameVisitor.names
        attributeVisitor = AttributeVisitor()
        attributeVisitor.visit(node.value)
        attributes = ".".join(attributeVisitor.attributes)
        # df_mask = "pd.DataFrame" in attributes
        # plot_mask = "bifrost.plot" in attributes
        if "DataFrame" in attributes:
            self.new_dfs.add(*names)

        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "Chart"
        ):
            self.chart_var = node.targets[0].id
            if isinstance(node.value.args[0], ast.Constant):
                self.bifrost_input_url = node.value.args[0].value
            elif isinstance(node.value.args[0], ast.Name):
                self.bifrost_input = node.value.args[0].id
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == self.chart_var
            and "plot" in attributes
        ):
            self.output_var = names[-1] if len(names) else None


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
